"""Check that the LP cost-to-go really is a lower bound on SWMM's remaining spill.

For a sample of already-evaluated plans, walk along the SWMM trajectory and compare
    spill so far (SWMM, hour h) + LP bound from the hour-h tank levels
with the plan's final SWMM spill. A valid bound never exceeds the final spill; any excess
is a "violation" and is the margin the branch-and-bound pruning would need.

    python research/validate_lp.py --n 400
"""
import argparse
import csv
import os
import random
import sys
from multiprocessing import Pool
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import lp_core  # noqa: E402
from beam import simulate_prefix  # noqa: E402

from stormline.grade import parse_plan  # noqa: E402

RUNS = Path(__file__).resolve().parent / "runs.csv"


def check(args):
    code, final = args
    p = parse_plan(code)
    worst = (-1e9, None)
    for H in range(1, 12):
        pre = [tuple(p[i][t] for i in range(4)) for t in range(H)]
        vols, spill = simulate_prefix(pre)
        v = spill + lp_core.solve(H, vols, 4) - final
        if v > worst[0]:
            worst = (v, H)
    return code, final, worst[0], worst[1]


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=400)
    ap.add_argument("--max-spill", type=float, default=16.0)
    a = ap.parse_args()
    rows = []
    with RUNS.open() as f:
        for r in csv.DictReader(f):
            if float(r["spill_ML"]) < a.max_spill:
                rows.append((r["plan"], float(r["spill_ML"])))
    rows = list(dict(rows).items())
    random.seed(0)
    sample = sorted(rows, key=lambda x: x[1])[:50] + random.sample(rows, min(a.n, len(rows)))
    with Pool(os.cpu_count()) as pool:
        res = pool.map(check, sample, chunksize=4)
    res.sort(key=lambda x: -x[2])
    viol = [r for r in res if r[2] > 1e-6]
    print(f"{len(rows)} plans under {a.max_spill} ML; checked {len(res)}; violations: {len(viol)}")
    print("largest (bound - final spill), with the hour it occurs:")
    for code, final, v, h in res[:10]:
        print(f"  {v:+.3f} ML at hour {h}  final {final:.2f}  {code}")
