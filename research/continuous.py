"""Continuous relaxation in SWMM: let each penstock setting be any value in [0, 1] (SWMM accepts
that), optimise all 48 with CMA-ES against the same SWMM model, then round to the nearest
quarter and hand the result to the discrete search. This is NOT an official score (the
grader only allows quarters); it shows where the ideal settings lie.

    python research/continuous.py --start PLAN --sigma 0.15 --evals 20000
"""
import argparse
import os
import sys
import tempfile
from multiprocessing import Pool
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import cma  # noqa: E402
from pyswmm import Links, Nodes, Simulation  # noqa: E402

from stormline.grade import INP, OUTFALLS, parse_plan, plan_code  # noqa: E402


def spill_continuous(x):
    """x: 48 floats in [0,1] (tank-major). Same control loop as the grader."""
    s = np.clip(np.asarray(x, float), 0, 1).reshape(4, 12)
    tmp = tempfile.mkdtemp(prefix="cont_")
    rpt, out = os.path.join(tmp, "r.rpt"), os.path.join(tmp, "r.out")
    try:
        with Simulation(str(INP), reportfile=rpt, outputfile=out) as sim:
            links, nodes = Links(sim), Nodes(sim)
            pens = [links[f"PEN_{i + 1}"] for i in range(4)]
            sim.step_advance(3600)
            for i in range(4):
                pens[i].target_setting = float(s[i, 0])
            hour = 0
            for _ in sim:
                hour += 1
                if hour < 12:
                    for i in range(4):
                        pens[i].target_setting = float(s[i, hour])
            total = sum(nodes[o].cumulative_inflow for o in OUTFALLS) / 1000.0
    finally:
        for f in (rpt, out):
            if os.path.exists(f):
                os.remove(f)
        os.rmdir(tmp)
    return total


def to_plan(x):
    s = np.clip(np.asarray(x, float), 0, 1).reshape(4, 12)
    return [[int(round(v * 4)) for v in row] for row in s]


def optimise(x0, sigma, evals, seed=0, verbose=True):
    pool = Pool(os.cpu_count())
    es = cma.CMAEvolutionStrategy(list(x0), sigma, {"bounds": [0, 1], "seed": seed, "maxfevals": evals,
                                                     "popsize": 32, "verbose": -9})
    best, bestx = 1e9, None
    gen = 0
    while not es.stop():
        X = es.ask()
        f = pool.map(spill_continuous, X)
        es.tell(X, f)
        gen += 1
        k = int(np.argmin(f))
        if f[k] < best:
            best, bestx = f[k], np.array(X[k])
        if verbose and gen % 20 == 0:
            print(f"gen {gen:4d} evals {es.countevals:6d} best continuous {best:.3f}", flush=True)
    pool.close()
    return bestx, best


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2" * 48)
    ap.add_argument("--sigma", type=float, default=0.2)
    ap.add_argument("--evals", type=int, default=20000)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    x0 = np.array([v / 4 for row in parse_plan(a.start) for v in row])
    x, f = optimise(x0, a.sigma, a.evals, a.seed)
    print(f"CONTINUOUS {f:.3f}")
    print("settings (x4):")
    for row in np.clip(x, 0, 1).reshape(4, 12):
        print("  " + " ".join(f"{v * 4:4.2f}" for v in row))
    print(f"ROUNDED {plan_code(to_plan(x))}")
    np.save(Path(__file__).resolve().parent / f"cont_best_seed{a.seed}.npy", x)
