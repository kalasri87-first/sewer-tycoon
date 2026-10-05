"""Diagnostic twin of stormline.grade.run: same SWMM model and same hourly penstock changes,
but records the state of the network at the end of every hour so we can see *where and
when* a plan spills. The official score still comes from stormline.grade.run.

    python research/diag.py PLAN
"""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pyswmm import Links, Nodes, Simulation  # noqa: E402

from stormline.grade import INP, OUTFALLS, parse_plan, plan_code  # noqa: E402

HOURS, TANKS = 12, 4
CAP = [100, 100, 120, 150]


def trace(plan, inp=INP):
    if isinstance(plan, str):
        plan = parse_plan(plan)
    tmp = tempfile.mkdtemp(prefix="diag_")
    rpt, out = os.path.join(tmp, "r.rpt"), os.path.join(tmp, "r.out")
    rows = []
    try:
        with Simulation(str(inp), reportfile=rpt, outputfile=out) as sim:
            links, nodes = Links(sim), Nodes(sim)
            pens = [links[f"PEN_{i + 1}"] for i in range(TANKS)]
            sim.step_advance(3600)
            hour = 0
            for i in range(TANKS):
                pens[i].target_setting = plan[i][0] / 4.0
            prev = [0.0] * 6

            def record():
                cum = [nodes[o].cumulative_inflow / 1000.0 for o in OUTFALLS] + [nodes["WORKS"].cumulative_inflow / 1000.0]
                vols = [nodes[f"T{i + 1}"].volume / 1000.0 for i in range(TANKS)]
                rows.append({"hour": len(rows) + 1, "vol": vols,
                             "spill": [c - p for c, p in zip(cum[:5], prev[:5])],
                             "treated": cum[5] - prev[5]})
                return cum

            for _ in sim:
                prev = record()
                hour += 1
                if hour < HOURS:
                    for i in range(TANKS):
                        pens[i].target_setting = plan[i][hour] / 4.0
            record()  # final hour: the simulation ends without yielding again
    finally:
        for f in (rpt, out):
            if os.path.exists(f):
                os.remove(f)
        os.rmdir(tmp)
    return rows


def show(plan):
    if isinstance(plan, str):
        plan = parse_plan(plan)
    rows = trace(plan)
    print(plan_code(plan))
    print("hr | settings | vol T1  T2  T3  T4 (ML, end of hour) | spill T1  T2  T3  T4  works | treated")
    tot = [0.0] * 5
    for h, r in enumerate(rows):
        s = "".join(str(plan[i][h]) if h < HOURS else "-" for i in range(TANKS))
        v = " ".join(f"{x:5.1f}" for x in r["vol"])
        sp = " ".join(f"{x:5.1f}" for x in r["spill"])
        tot = [a + b for a, b in zip(tot, r["spill"])]
        print(f"{r['hour']:2d} |   {s}   | {v} | {sp} | {r['treated']:5.1f}")
    print(f"total spill {sum(tot):.2f}  by outfall " + " ".join(f"{x:.2f}" for x in tot))


if __name__ == "__main__":
    show(" ".join(sys.argv[1:]))
