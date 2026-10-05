"""Branch-and-bound over hours with a diversity cap.

Level by level (hour by hour), every surviving partial plan is expanded with all 625 gate
combinations for the next hour and simulated in SWMM to the end of that hour. A child is
discarded if

    spill so far (SWMM)                        >= incumbent   (exact: spill only accumulates)
    spill so far + LP lower bound on the rest  >= incumbent   (near-exact: LP relaxation)

The survivors are de-duplicated on a coarse grid of tank levels (best child per cell), so
the frontier stays diverse, and capped at --width cells (best LP value first). With a large
width this is an exhaustive search; with a small one it is a diverse beam.

    python research/bnb.py --incumbent 12.45 --width 200 --grid 2.0
"""
import argparse
import os
import sys
import time
from multiprocessing import Pool
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import lp_core  # noqa: E402
from beam import COMBOS, child_state  # noqa: E402

from stormline.build_model import HOURS  # noqa: E402
from stormline.grade import parse_plan, plan_code, run  # noqa: E402


def state_value(args):
    h, vols = args
    return lp_core.solve(h, vols, 4)


def search(incumbent, width, grid, start_prefix=None, verbose=True):
    pool = Pool(os.cpu_count())
    level = [list(start_prefix or [])]
    best_plans = []
    for h in range(len(level[0]), HOURS):
        t0 = time.time()
        children = [p + [c] for p in level for c in COMBOS]
        sims = pool.map(child_state, children, chunksize=64)
        fine = {}
        for prefix, vols, spill in sims:
            if spill >= incumbent - 1e-9:
                continue
            key = tuple(round(v * 4) for v in vols) + (round(spill * 20),)
            if key not in fine or spill < fine[key][2]:
                fine[key] = (prefix, vols, spill)
        states = list(fine.values())
        if h + 1 < HOURS:
            vals = pool.map(state_value, [(h + 1, st[1]) for st in states], chunksize=16)
        else:
            vals = [0.0] * len(states)
        alive = [(st[2] + v, st) for st, v in zip(states, vals) if st[2] + v < incumbent - 1e-9]
        alive.sort(key=lambda x: x[0])
        cells = {}
        for val, st in alive:
            key = tuple(round(v / grid) for v in st[1])
            if key not in cells:
                cells[key] = (val, st)
        kept = sorted(cells.values(), key=lambda x: x[0])[:width]
        if verbose:
            msg = (f"hour {h + 1:2d}: {len(children)} children, {len(states)} distinct, {len(alive)} pass bound, "
                   f"{len(cells)} cells, kept {len(kept)}")
            if kept:
                msg += f"; best value {kept[0][0]:.3f} (spill so far {kept[0][1][2]:.2f}), worst kept {kept[-1][0]:.3f}"
            print(msg + f" [{time.time() - t0:.0f}s]", flush=True)
        if not kept:
            break
        level = [st[0] for _, st in kept]
        if h + 1 == HOURS:
            best_plans = [[[prefix[t][i] for t in range(HOURS)] for i in range(4)] for prefix in level]
    pool.close()
    return best_plans


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--incumbent", type=float, required=True)
    ap.add_argument("--width", type=int, default=200)
    ap.add_argument("--grid", type=float, default=2.0, help="ML; diversity cell size per tank")
    ap.add_argument("--from-plan", default=None)
    ap.add_argument("--hours", type=int, default=0)
    a = ap.parse_args()
    pre = None
    if a.from_plan:
        fp = parse_plan(a.from_plan)
        pre = [tuple(fp[i][t] for i in range(4)) for t in range(a.hours)]
    plans = search(a.incumbent, a.width, a.grid, pre)
    if not plans:
        print(f"NONE: no plan below {a.incumbent} survives")
    for p in plans[:10]:
        print(f"RESULT {run(p)['spill_ML']:.2f} {plan_code(p)}", flush=True)
