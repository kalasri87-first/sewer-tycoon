"""Search strategies against the official SWMM grader (via research/evaluate.py).

    python research/search.py descend PLAN [PLAN ...]   steepest descent, 1-digit then 2-digit moves
    python research/search.py anneal PLAN --minutes 5    simulated annealing from PLAN
"""
import argparse
import itertools
import math
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from evaluate import evaluate  # noqa: E402

from stormline.grade import parse_plan, plan_code  # noqa: E402

CELLS = [(i, t) for i in range(4) for t in range(12)]


def flat(p):
    return [v for row in p for v in row]


def unflat(v):
    return [list(v[i * 12:(i + 1) * 12]) for i in range(4)]


def single_moves(v):
    for k in range(48):
        for d in range(5):
            if d != v[k]:
                w = v[:]
                w[k] = d
                yield w


def pair_moves(v, span=2):
    """Change two cells by up to +-span each (all pairs)."""
    for a, b in itertools.combinations(range(48), 2):
        for da in range(-span, span + 1):
            for db in range(-span, span + 1):
                if da == 0 or db == 0:
                    continue
                x, y = v[a] + da, v[b] + db
                if 0 <= x <= 4 and 0 <= y <= 4:
                    w = v[:]
                    w[a], w[b] = x, y
                    yield w


def shift_moves(v):
    """Time-shift one tank's schedule by one hour either way, or swap adjacent hours."""
    for i in range(4):
        row = v[i * 12:(i + 1) * 12]
        for new in (row[1:] + row[-1:], row[:1] + row[:-1]):
            w = v[:]
            w[i * 12:(i + 1) * 12] = new
            yield w
        for t in range(11):
            r = row[:]
            r[t], r[t + 1] = r[t + 1], r[t]
            w = v[:]
            w[i * 12:(i + 1) * 12] = r
            yield w


def descend(start, tag="descend", verbose=True, use_pairs=True):
    v = flat(parse_plan(start) if isinstance(start, str) else start)
    best = evaluate([unflat(v)], tag)[0]
    if verbose:
        print(f"start {best:7.2f}  {plan_code(unflat(v))}", flush=True)
    while True:
        improved = False
        for name, gen in (("1-digit", single_moves), ("shift", shift_moves),
                          ("2-digit", pair_moves if use_pairs else None)):
            if gen is None:
                continue
            cands = list(gen(v))
            scores = evaluate([unflat(c) for c in cands], tag)
            k = min(range(len(cands)), key=scores.__getitem__)
            if scores[k] < best - 1e-9:
                v, best = cands[k], scores[k]
                if verbose:
                    print(f"{name:8s}{best:7.2f}  {plan_code(unflat(v))}  ({len(cands)} tried)", flush=True)
                improved = True
                break
        if not improved:
            return unflat(v), best


def anneal(start, minutes=5, t0=3.0, t1=0.05, seed=0, tag="anneal", batch=64, verbose=True):
    rng = random.Random(seed)
    v = flat(parse_plan(start) if isinstance(start, str) else start)
    cur = evaluate([unflat(v)], tag)[0]
    best, bestv = cur, v[:]
    end = time.time() + minutes * 60
    t_start = time.time()
    while time.time() < end:
        frac = (time.time() - t_start) / (minutes * 60)
        T = t0 * (t1 / t0) ** frac
        cands = []
        for _ in range(batch):
            w = v[:]
            for _ in range(rng.choice([1, 1, 2, 3])):
                k = rng.randrange(48)
                w[k] = max(0, min(4, w[k] + rng.choice([-2, -1, 1, 2])))
            cands.append(w)
        scores = evaluate([unflat(c) for c in cands], tag)
        # Metropolis over the batch sequentially (all candidates are neighbours of the batch start)
        order = sorted(range(batch), key=scores.__getitem__)
        for k in order[:1]:
            d = scores[k] - cur
            if d < 0 or rng.random() < math.exp(-d / T):
                v, cur = cands[k], scores[k]
        if cur < best - 1e-9:
            best, bestv = cur, v[:]
            if verbose:
                print(f"T={T:5.2f}  {best:7.2f}  {plan_code(unflat(bestv))}", flush=True)
    return unflat(bestv), best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["descend", "anneal"])
    ap.add_argument("plans", nargs="+")
    ap.add_argument("--minutes", type=float, default=5)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--nopairs", action="store_true")
    a = ap.parse_args()
    for p in a.plans:
        if a.mode == "descend":
            plan, s = descend(p, use_pairs=not a.nopairs)
        else:
            plan, s = anneal(p, a.minutes, seed=a.seed)
        print(f"RESULT {s:.2f} {plan_code(plan)}", flush=True)


if __name__ == "__main__":
    main()
