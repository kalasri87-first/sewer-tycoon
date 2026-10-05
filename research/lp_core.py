"""LP relaxation of the network, shared by lp_bound.py and beam.py.

Per time step (dt hours), for each tank i:
    S[k] = S[k-1] + dt*(inflow + Q[i-1] - Q[i]) - W            (mass balance, ML)
    Q    <= rating of a fully open gate at mid-step storage   (concave -> tangent lines)
    W    >= dt * weir overflow at mid-step head above crest   (convex  -> tangent lines)
    0 <= S <= storage at 6 m (tanks may surcharge above the 5 m crest while spilling)
Works: B >= dt*(Q4 - 20).  Objective: min sum W + sum B.

Gates may pass any flow between zero and the fully-open rating, changed every step, so
(up to discretisation) no 5-level hourly plan can do better than this LP. The first
version (lp_bound.py's original) capped storage at the crest, which forbade the temporary
surcharge SWMM allows and so was NOT a valid bound; see LOG.md.
"""
import math
import sys
from pathlib import Path

import numpy as np
from scipy.optimize import linprog
from scipy.sparse import coo_matrix

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from stormline.build_model import CAP_ML, CD, CREST, GATE_H, HOURS, ML_PER_H, QMAX_MLH, WORKS_MLH, inflow_mlh  # noqa: E402

G = 9.81
WIDTH = [QMAX_MLH[i] * ML_PER_H / (CD * GATE_H * math.sqrt(2 * G * (CREST - GATE_H / 2))) for i in range(4)]
AREA_M2 = [c * 1000.0 / CREST for c in CAP_ML]           # tank plan area
SMAX = [c * 6.0 / CREST for c in CAP_ML]                 # storage at 6 m max depth
WEIR = 1.84 * 100.0 / ML_PER_H                           # ML/h per m^1.5 of head (transverse, 100 m)


def _rating_tangents(i):
    out = []
    for d0 in np.linspace(1.0, 6.0, 16):
        f0 = CD * WIDTH[i] * GATE_H * math.sqrt(2 * G * (d0 - GATE_H / 2)) / ML_PER_H
        slope_d = CD * WIDTH[i] * GATE_H * G / math.sqrt(2 * G * (d0 - GATE_H / 2)) / ML_PER_H
        a = slope_d * CREST / CAP_ML[i]                  # per ML of storage
        out.append((a, f0 - a * d0 * CAP_ML[i] / CREST))
    return out


def _weir_tangents(i):
    """Lower tangents of overflow(S) = WEIR*((S-CAP)/A)^1.5 for S >= CAP, as (a, b): W/dt >= a*S + b."""
    out = []
    per_ml = 1000.0 / AREA_M2[i]                         # m of head per ML above crest
    for h0 in [0.0, 0.005, 0.01, 0.02, 0.03, 0.05, 0.075, 0.1, 0.15, 0.2, 0.3, 0.5, 0.75, 1.0]:
        g0 = WEIR * h0 ** 1.5
        slope_h = 1.5 * WEIR * h0 ** 0.5
        a = slope_h * per_ml
        s0 = CAP_ML[i] + h0 / per_ml
        out.append((a, g0 - a * s0))
    return out


RT = [_rating_tangents(i) for i in range(4)]
WT = [_weir_tangents(i) for i in range(4)]


def solve(h0=0, S0=(0, 0, 0, 0), sph=4, full=False):
    """LP lower bound on spill from hour h0 to 12 starting with storages S0 (ML)."""
    n = (HOURS - h0) * sph
    if n == 0:
        return (0.0, None) if full else 0.0
    dt = 1.0 / sph
    nv = 13 * n
    iS = lambda i, k: i * n + k            # noqa: E731
    iQ = lambda i, k: 4 * n + i * n + k    # noqa: E731
    iW = lambda i, k: 8 * n + i * n + k    # noqa: E731
    iB = lambda k: 12 * n + k              # noqa: E731
    r, c_, v, beq = [], [], [], []
    row = 0
    for i in range(4):
        for k in range(n):
            t = h0 + k // sph
            r += [row, row, row]
            c_ += [iS(i, k), iQ(i, k), iW(i, k)]
            v += [1.0, dt, 1.0]
            rhs = inflow_mlh(i, t) * dt
            if k > 0:
                r.append(row); c_.append(iS(i, k - 1)); v.append(-1.0)
            else:
                rhs += S0[i]
            if i > 0:
                r.append(row); c_.append(iQ(i - 1, k)); v.append(-dt)
            beq.append(rhs)
            row += 1
    Aeq = coo_matrix((v, (r, c_)), shape=(row, nv)).tocsr()
    r, c_, v, bub = [], [], [], []
    row = 0

    def mid_constraint(var, coef_var, i, k, a, b):
        # coef_var*var - a*(S[k-1]+S[k])/2 <= b   (S[-1] = S0)
        nonlocal row
        r.extend([row, row]); c_.extend([var, iS(i, k)]); v.extend([coef_var, -a / 2])
        if k > 0:
            r.append(row); c_.append(iS(i, k - 1)); v.append(-a / 2)
            bub.append(b)
        else:
            bub.append(b + a / 2 * S0[i])
        row += 1

    for i in range(4):
        for k in range(n):
            for a, b in RT[i]:                 # Q <= a*Smid + b
                mid_constraint(iQ(i, k), 1.0, i, k, a, b)
            for a, b in WT[i]:                 # W/dt >= a*Smid + b   <=>  -W/dt + a*Smid <= -b
                if a == 0 and b == 0:
                    continue
                r.extend([row, row]); c_.extend([iW(i, k), iS(i, k)]); v.extend([-1.0 / dt, a / 2])
                if k > 0:
                    r.append(row); c_.append(iS(i, k - 1)); v.append(a / 2)
                    bub.append(-b)
                else:
                    bub.append(-b - a / 2 * S0[i])
                row += 1
    for k in range(n):
        r += [row, row]
        c_ += [iQ(3, k), iB(k)]
        v += [dt, -1.0]
        bub.append(WORKS_MLH * dt)
        row += 1
    Aub = coo_matrix((v, (r, c_)), shape=(row, nv)).tocsr()
    c = np.zeros(nv)
    c[8 * n:] = 1.0
    bounds = [(0, SMAX[i]) for i in range(4) for _ in range(n)] + [(0, None)] * (9 * n)
    res = linprog(c, A_ub=Aub, b_ub=bub, A_eq=Aeq, b_eq=beq, bounds=bounds, method="highs")
    val = res.fun if res.status == 0 else 1e9
    if not full:
        return val
    x = res.x
    return val, {"S": x[:4 * n].reshape(4, n), "Q": x[4 * n:8 * n].reshape(4, n),
                 "W": x[8 * n:12 * n].reshape(4, n), "B": x[12 * n:], "sph": sph, "h0": h0}
