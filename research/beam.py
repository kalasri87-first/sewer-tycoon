"""Beam search over hours, with an LP cost-to-go.

Build the plan one hour at a time. For every partial plan in the beam, try all 5^4 = 625
gate combinations for the next hour, simulate in SWMM up to the end of that hour (same
hourly control as the grader, stopped early), and score the child as

    spill so far (SWMM)  +  LP lower bound on the spill still to come from the tank levels reached

then keep the best K distinct states. The LP relaxation (continuous control, rating-curve
limits) is the same as research/lp_bound.py, started from the current storage.

    python research/beam.py --width 30
"""
import argparse
import itertools
import math
import os
import sys
import tempfile
import time
from multiprocessing import Pool
from pathlib import Path

import numpy as np
from scipy.optimize import linprog
from scipy.sparse import coo_matrix

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pyswmm import Links, Nodes, Simulation  # noqa: E402

import lp_core  # noqa: E402  (corrected LP with weir surcharge)

from stormline.build_model import CAP_ML, CD, CREST, GATE_H, HOURS, ML_PER_H, QMAX_MLH, WORKS_MLH, inflow_mlh  # noqa: E402
from stormline.grade import INP, OUTFALLS, plan_code, run  # noqa: E402

G = 9.81
WIDTH = [QMAX_MLH[i] * ML_PER_H / (CD * GATE_H * math.sqrt(2 * G * (CREST - GATE_H / 2))) for i in range(4)]
TANGENTS = np.linspace(1.0, CREST + 0.2, 12)


def qmax(i, d):
    return CD * WIDTH[i] * GATE_H * math.sqrt(2 * G * max(d - GATE_H / 2, 0.0)) / ML_PER_H


def _tangents(i):
    out = []
    for d0 in TANGENTS:
        f0 = qmax(i, d0)
        slope_d = CD * WIDTH[i] * GATE_H * G / math.sqrt(2 * G * (d0 - GATE_H / 2)) / ML_PER_H
        a = slope_d * CREST / CAP_ML[i]
        out.append((a, f0 - a * d0 * CAP_ML[i] / CREST))
    return out


TAN = [_tangents(i) for i in range(4)]


def fmax(i, s):
    """Concave upper bound on fully-open flow at storage s (ML)."""
    return max(0.0, min(b + a * s for a, b in TAN[i]))


def lp_to_go(h0, S0, sph=2):
    """LP lower bound on spill from hour h0 (start) to 12 with initial storage S0 (ML)."""
    n = (HOURS - h0) * sph
    if n == 0:
        return 0.0
    dt = 1.0 / sph
    nv = 13 * n
    iS = lambda i, k: i * n + k            # noqa: E731
    iQ = lambda i, k: 4 * n + i * n + k    # noqa: E731
    iW = lambda i, k: 8 * n + i * n + k    # noqa: E731
    iB = lambda k: 12 * n + k              # noqa: E731
    r, cidx, val, beq = [], [], [], []
    row = 0
    for i in range(4):
        for k in range(n):
            t = h0 + k // sph
            r += [row, row, row]
            cidx += [iS(i, k), iQ(i, k), iW(i, k)]
            val += [1.0, dt, 1.0]
            rhs = inflow_mlh(i, t) * dt
            if k > 0:
                r.append(row); cidx.append(iS(i, k - 1)); val.append(-1.0)
            else:
                rhs += S0[i]
            if i > 0:
                r.append(row); cidx.append(iQ(i - 1, k)); val.append(-dt)
            beq.append(rhs)
            row += 1
    Aeq = coo_matrix((val, (r, cidx)), shape=(row, nv)).tocsr()
    r, cidx, val, bub = [], [], [], []
    row = 0
    for i in range(4):
        for k in range(n):
            # Q over the step <= f(mid-step storage), f concave (tangent lines)
            for a, b in TAN[i]:
                r += [row, row]
                cidx += [iQ(i, k), iS(i, k)]
                val += [1.0, -a / 2]
                if k > 0:
                    r.append(row); cidx.append(iS(i, k - 1)); val.append(-a / 2)
                    bub.append(b)
                else:
                    bub.append(b + a / 2 * S0[i])
                row += 1
    for k in range(n):
        r += [row, row]
        cidx += [iQ(3, k), iB(k)]
        val += [dt, -1.0]
        bub.append(WORKS_MLH * dt)
        row += 1
    Aub = coo_matrix((val, (r, cidx)), shape=(row, nv)).tocsr()
    c = np.zeros(nv)
    c[8 * n:] = 1.0
    bounds = ([(0, CAP_ML[i]) for i in range(4) for _ in range(n)]
              + [(0, None)] * (4 * n)
              + [(0, None)] * (5 * n))
    res = linprog(c, A_ub=Aub, b_ub=bub, A_eq=Aeq, b_eq=beq, bounds=bounds, method="highs")
    return res.fun if res.status == 0 else 1e9


def simulate_prefix(prefix):
    """prefix: list of 4-tuples (settings 0-4) for hours 0..h-1. Returns (volumes ML, spill so far ML)."""
    H = len(prefix)
    tmp = tempfile.mkdtemp(prefix="beam_")
    rpt, out = os.path.join(tmp, "r.rpt"), os.path.join(tmp, "r.out")
    try:
        with Simulation(str(INP), reportfile=rpt, outputfile=out) as sim:
            links, nodes = Links(sim), Nodes(sim)
            pens = [links[f"PEN_{i + 1}"] for i in range(4)]
            sim.step_advance(3600)
            for i in range(4):
                pens[i].target_setting = prefix[0][i] / 4.0
            hour = 0
            for _ in sim:
                hour += 1
                if hour >= H and H < HOURS:
                    break
                if hour < HOURS:
                    for i in range(4):
                        pens[i].target_setting = prefix[hour][i] / 4.0
            vols = [nodes[f"T{i + 1}"].volume / 1000.0 for i in range(4)]
            spill = sum(nodes[o].cumulative_inflow for o in OUTFALLS) / 1000.0
    finally:
        for f in (rpt, out):
            if os.path.exists(f):
                os.remove(f)
        os.rmdir(tmp)
    return vols, spill


def child_state(prefix):
    vols, spill = simulate_prefix(prefix)
    return prefix, vols, spill


def state_value(args):
    h, vols = args
    return lp_core.solve(h, vols, 4)


COMBOS = list(itertools.product(range(5), repeat=4))


def beam(width, incumbent=1e9, verbose=True):
    """Beam search; children are simulated, de-duplicated by rounded state, pruned if their
    spill so far already exceeds the incumbent, and only then scored with the LP."""
    pool = Pool(os.cpu_count())
    level = [[]]
    for h in range(HOURS):
        t0 = time.time()
        children = [p + [c] for p in level for c in COMBOS]
        sims = pool.map(child_state, children, chunksize=64)
        uniq = {}
        for prefix, vols, spill in sims:
            if spill >= incumbent:
                continue
            key = tuple(round(v * 4) for v in vols) + (round(spill * 4),)
            if key not in uniq or spill < uniq[key][2]:
                uniq[key] = (prefix, vols, spill)
        states = list(uniq.values())
        vals = pool.map(state_value, [(h + 1, st[1]) for st in states], chunksize=16)
        scored = sorted(((st[2] + v, st) for st, v in zip(states, vals)), key=lambda x: x[0])
        nxt = scored[:width]
        level = [st[0] for _, st in nxt]
        if verbose:
            val, (prefix, vols, spill) = nxt[0]
            print(f"hour {h + 1:2d}: {len(children)} children -> {len(states)} distinct states; "
                  f"best value {val:.2f} (spill so far {spill:.2f}, vols {[round(v, 1) for v in vols]}); "
                  f"worst kept {nxt[-1][0]:.2f} [{time.time() - t0:.0f}s]", flush=True)
    pool.close()
    return [[[prefix[t][i] for t in range(HOURS)] for i in range(4)] for prefix in level]


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--width", type=int, default=20)
    ap.add_argument("--incumbent", type=float, default=1e9)
    a = ap.parse_args()
    plans = beam(a.width, a.incumbent)
    for p in plans[:10]:
        print(f"RESULT {run(p)['spill_ML']:.2f} {plan_code(p)}", flush=True)
