"""The browser game's stand-in simulator, ported to Python.

Same network and inflows as the SWMM model, but a simple mass balance stepped once a
minute: each tank fills, anything above its overflow crest spills, and each penstock
releases like a sluice gate (orifice flow, or weir-like flow when the water is below the
gate opening). Tank 4 feeds the works, which takes up to 20 ML/h; the rest bypasses.

It runs in about a millisecond and usually lands within a few ML of SWMM, but it is not
the official grader. The official result always comes from SWMM (stormline.grade), and
at the top of the leaderboard those few ML decide the winner.
"""
import math

from .build_model import CAP_ML, CD, CREST, GATE_H, HOURS, ML_PER_H, QMAX_MLH, RUNOFF, UPSTREAM, WORKS_MLH
from .grade import parse_plan

G = 9.81
WIDTH = [QMAX_MLH[i] * ML_PER_H / (CD * GATE_H * math.sqrt(2 * G * (CREST - GATE_H / 2))) for i in range(4)]


def quick_spill(plan, substeps=60):
    if isinstance(plan, str):
        plan = parse_plan(plan)
    S = [0.0] * 4
    spill = 0.0
    dt = 1.0 / substeps                      # hours
    for t in range(HOURS):
        inflow = [RUNOFF[0][t] + UPSTREAM[t], RUNOFF[1][t], RUNOFF[2][t], RUNOFF[3][t]]
        for _ in range(substeps):
            add = [x * dt for x in inflow]
            for i in range(4):
                S[i] += add[i]
                if S[i] > CAP_ML[i]:
                    spill += S[i] - CAP_ML[i]
                    S[i] = CAP_ML[i]
                ho = plan[i][t] / 4 * GATE_H
                if ho > 0 and S[i] > 0:
                    d = CREST * S[i] / CAP_ML[i]
                    if d >= ho:
                        Q = CD * WIDTH[i] * ho * math.sqrt(2 * G * (d - ho / 2))
                    else:
                        Q = CD * WIDTH[i] * d * math.sqrt(G * d)
                    q = min(S[i], Q / ML_PER_H * dt)
                    S[i] -= q
                    if i < 3:
                        add[i + 1] += q
                    else:
                        spill += max(0.0, q - WORKS_MLH * dt)
    return round(spill, 2)
