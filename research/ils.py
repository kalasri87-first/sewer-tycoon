"""Iterated local search: kick the incumbent (random multi-cell change focused on the storm
peak), re-descend with single-digit moves, keep the result if it is at least as good.
Accepting equal scores lets the search drift across the plateaus this problem has
(many settings do not change the flow when a tank is nearly empty).

    python research/ils.py PLAN --minutes 10 --seed 1
"""
import argparse
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from evaluate import evaluate  # noqa: E402
from search import flat, single_moves, unflat  # noqa: E402

from stormline.grade import parse_plan, plan_code  # noqa: E402


def quick_descend(v, best, tag):
    while True:
        cands = list(single_moves(v))
        scores = evaluate([unflat(c) for c in cands], tag)
        k = min(range(len(cands)), key=scores.__getitem__)
        if scores[k] < best - 1e-9:
            v, best = cands[k], scores[k]
        else:
            return v, best


def kick(v, rng):
    w = v[:]
    n = rng.choice([2, 3, 4, 5, 6])
    for _ in range(n):
        i = rng.randrange(4)
        t = min(11, max(0, int(rng.gauss(6.0, 2.0))))   # storm peak is hours 5-8 (index 4-7)
        w[i * 12 + t] = max(0, min(4, w[i * 12 + t] + rng.choice([-2, -1, 1, 2])))
    return w


def ils(start, minutes, seed, tag="ils"):
    rng = random.Random(seed)
    v = flat(parse_plan(start))
    cur = evaluate([unflat(v)], tag)[0]
    v, cur = quick_descend(v, cur, tag)
    best, bestv = cur, v[:]
    print(f"start {best:7.2f}  {plan_code(unflat(v))}", flush=True)
    end = time.time() + minutes * 60
    it = 0
    while time.time() < end:
        it += 1
        w = kick(v, rng)
        s = evaluate([unflat(w)], tag)[0]
        w, s = quick_descend(w, s, tag)
        if s <= cur + 1e-9:
            v, cur = w, s
        if s < best - 1e-9:
            best, bestv = s, w[:]
            print(f"it {it:4d} {best:7.2f}  {plan_code(unflat(bestv))}", flush=True)
    return unflat(bestv), best


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("plan")
    ap.add_argument("--minutes", type=float, default=10)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    plan, s = ils(a.plan, a.minutes, a.seed)
    print(f"RESULT {s:.2f} {plan_code(plan)}", flush=True)
