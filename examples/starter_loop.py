"""A deliberately simple starting loop: random restarts plus hill climbing against SWMM.

It works, slowly. The point of the Harness level is to do better than this: look at
where and when each plan spills, form a hypothesis, and search smarter.

    python examples/starter_loop.py --minutes 5
    python examples/starter_loop.py --minutes 5 --start 222222222222-222222222222-222222222222-222222222222
"""
import argparse
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from stormline.grade import parse_plan, plan_code, run  # noqa: E402


def score(plan):
    return run(plan)["spill_ML"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--minutes", type=float, default=3)
    ap.add_argument("--start", default="2" * 48)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    random.seed(a.seed)
    cur = parse_plan(a.start)
    cur_s = score(cur)
    best, best_s = cur, cur_s
    print(f"start  {cur_s:7.2f} ML  {plan_code(cur)}")
    end = time.time() + a.minutes * 60
    tries = 0
    while time.time() < end:
        cand = [row[:] for row in cur]
        for _ in range(random.choice([1, 1, 2])):
            i, t = random.randrange(4), random.randrange(12)
            cand[i][t] = max(0, min(4, cand[i][t] + random.choice([-1, 1])))
        s = score(cand)
        tries += 1
        if s <= cur_s:
            cur, cur_s = cand, s
            if s < best_s:
                best, best_s = cand, s
                print(f"try {tries:5d}  {s:7.2f} ML  {plan_code(best)}")
    print(f"\nBest after {tries} SWMM runs: {best_s:.2f} ML")
    print(plan_code(best))


if __name__ == "__main__":
    main()
