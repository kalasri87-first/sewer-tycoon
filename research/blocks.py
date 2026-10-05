"""Block-coordinate search: jointly re-optimise a block of cells, holding the rest fixed.

  hour  : all 4 tanks in one hour (5^4 = 625 combos)
  tank2 : one tank, two consecutive hours, plus its neighbour tank same hours (5^4)
  pair  : two adjacent hours for two adjacent tanks (5^4)

    python research/blocks.py PLAN [--rounds N]
"""
import argparse
import itertools
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from evaluate import evaluate  # noqa: E402

from stormline.grade import parse_plan, plan_code  # noqa: E402


def blocks():
    out = []
    for t in range(12):                       # all tanks in one hour
        out.append(("hour", [(i, t) for i in range(4)]))
    for i in range(3):                        # 2x2: tanks i,i+1 x hours t,t+1
        for t in range(11):
            out.append(("2x2", [(i, t), (i, t + 1), (i + 1, t), (i + 1, t + 1)]))
    for i in range(4):                        # one tank, four consecutive hours
        for t in range(9):
            out.append(("run4", [(i, t + k) for k in range(4)]))
    return out


def optimise(plan, rounds=10, verbose=True, tag="blocks"):
    plan = parse_plan(plan) if isinstance(plan, str) else [r[:] for r in plan]
    best = evaluate([plan], tag)[0]
    if verbose:
        print(f"start {best:7.2f}  {plan_code(plan)}", flush=True)
    for rnd in range(rounds):
        improved = False
        for name, cells in blocks():
            cands = []
            for combo in itertools.product(range(5), repeat=len(cells)):
                p = [r[:] for r in plan]
                for (i, t), v in zip(cells, combo):
                    p[i][t] = v
                cands.append(p)
            scores = evaluate(cands, tag)
            k = min(range(len(cands)), key=scores.__getitem__)
            if scores[k] < best - 1e-9:
                plan, best = cands[k], scores[k]
                improved = True
                if verbose:
                    print(f"r{rnd} {name:5s}{cells[0]} {best:7.2f}  {plan_code(plan)}", flush=True)
        if not improved:
            break
    return plan, best


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("plans", nargs="+")
    ap.add_argument("--rounds", type=int, default=10)
    a = ap.parse_args()
    for p in a.plans:
        plan, s = optimise(p, a.rounds)
        print(f"RESULT {s:.2f} {plan_code(plan)}", flush=True)
