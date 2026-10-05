"""Turn the LP relaxation's ideal flows into a discrete plan: for each tank and hour, pick the
gate setting whose sluice-gate flow (at the LP's mean depth that hour) best matches the
LP's mean penstock flow. Used as a seed for local search.

    python research/lp_seed.py
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lp_core import WIDTH, solve  # noqa: E402

from stormline.build_model import CAP_ML, CD, CREST, GATE_H, ML_PER_H  # noqa: E402
from stormline.grade import plan_code  # noqa: E402

G = 9.81


def gate_flow(i, setting, d):
    ho = setting / 4 * GATE_H
    if ho <= 0 or d <= 0:
        return 0.0
    if d >= ho:
        q = CD * WIDTH[i] * ho * math.sqrt(2 * G * (d - ho / 2))
    else:
        q = CD * WIDTH[i] * d * math.sqrt(G * d)
    return q / ML_PER_H


def seed(steps=12, bias=0.0):
    _, x = solve(0, [0, 0, 0, 0], steps, full=True)
    S, Q = x["S"], x["Q"]
    plan = []
    for i in range(4):
        row = []
        for h in range(12):
            sl = slice(h * steps, (h + 1) * steps)
            prev = S[i, h * steps - 1] if h > 0 else 0.0
            d = CREST * (0.5 * (prev + S[i, (h + 1) * steps - 1])) / CAP_ML[i]
            q = Q[i, sl].mean() + bias
            row.append(min(range(5), key=lambda s: abs(gate_flow(i, s, d) - q)))
        plan.append(row)
    return plan


if __name__ == "__main__":
    for steps in (12, 60):
        for bias in (0.0, 1.0, -1.0):
            print(steps, bias, plan_code(seed(steps, bias)))
