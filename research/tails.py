"""Exhaustive-tail check for many openings.

Take the best distinct 6-hour openings among plans already scored (research/runs.csv) and,
from each opening's hour-6 state, run branch-and-bound over hours 7-12 with fine
de-duplication (0.05 ML) and incumbent pruning. Answers: does any known opening have a
better finish than the one the incumbent uses?

    python research/tails.py --incumbent 12.45 --top 30 --hours 6
"""
import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bnb import search  # noqa: E402

from stormline.grade import parse_plan, plan_code, run  # noqa: E402

RUNS = Path(__file__).resolve().parent / "runs.csv"


def openings(hours, top, max_spill):
    best = {}
    with RUNS.open() as f:
        for r in csv.DictReader(f):
            s = float(r["spill_ML"])
            if s > max_spill:
                continue
            p = parse_plan(r["plan"])
            key = tuple(tuple(p[i][t] for i in range(4)) for t in range(hours))
            if key not in best or s < best[key][0]:
                best[key] = (s, r["plan"])
    return sorted(best.items(), key=lambda kv: kv[1][0])[:top]


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--incumbent", type=float, default=12.45)
    ap.add_argument("--top", type=int, default=30)
    ap.add_argument("--hours", type=int, default=6)
    ap.add_argument("--max-spill", type=float, default=13.0)
    a = ap.parse_args()
    ops = openings(a.hours, a.top, a.max_spill)
    print(f"{len(ops)} distinct {a.hours}-hour openings to check", flush=True)
    found = []
    for n, (prefix, (s, code)) in enumerate(ops):
        plans = search(a.incumbent, 5000, 0.05, start_prefix=list(prefix), verbose=False)
        line = f"[{n + 1}/{len(ops)}] opening of {code} (best known {s:.2f}): "
        if plans:
            sc = min(run(p)["spill_ML"] for p in plans)
            best = min(plans, key=lambda p: run(p)["spill_ML"])
            line += f"FOUND {sc:.2f} {plan_code(best)}"
            found.append((sc, plan_code(best)))
        else:
            line += "no tail beats the incumbent"
        print(line, flush=True)
    print("SUMMARY", sorted(found)[:5] if found else "nothing below incumbent", flush=True)
