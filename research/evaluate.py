"""Parallel, cached evaluation of plans with the official SWMM grader.

Every plan scored is appended to research/runs.csv (plan, spill, breakdown) so the whole
search history is kept.
"""
import csv
import os
import sys
from multiprocessing import Pool
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from stormline.grade import plan_code, run  # noqa: E402

LOG = Path(__file__).resolve().parent / "runs.csv"
FIELDS = ["plan", "spill_ML", "t1", "t2", "t3", "t4", "works", "treated_ML", "stored_at_end_ML", "tag"]
_cache = {}
_pool = None


def _load():
    if LOG.exists() and not _cache:
        with LOG.open() as f:
            for row in csv.DictReader(f):
                _cache[row["plan"]] = float(row["spill_ML"])


def _one(code):
    r = run(code)
    o = list(r["by_outfall_ML"].values())
    return {"plan": code, "spill_ML": r["spill_ML"], "t1": o[0], "t2": o[1], "t3": o[2], "t4": o[3],
            "works": o[4], "treated_ML": r["treated_ML"], "stored_at_end_ML": r["stored_at_end_ML"]}


def pool():
    global _pool
    if _pool is None:
        _pool = Pool(os.cpu_count())
    return _pool


def evaluate(plans, tag=""):
    """plans: list of 4x12 lists or codes. Returns list of spills (ML), official SWMM numbers."""
    _load()
    codes = [p if isinstance(p, str) else plan_code(p) for p in plans]
    todo = sorted({c for c in codes if c not in _cache})
    if todo:
        results = pool().map(_one, todo, chunksize=max(1, len(todo) // (8 * os.cpu_count())))
        new = not LOG.exists()
        with LOG.open("a", newline="") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS)
            if new:
                w.writeheader()
            for r in results:
                r["tag"] = tag
                w.writerow(r)
                _cache[r["plan"]] = r["spill_ML"]
    return [_cache[c] for c in codes]


def n_evaluated():
    _load()
    return len(_cache)
