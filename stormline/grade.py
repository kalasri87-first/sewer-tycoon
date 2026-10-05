"""Official Sewer Tycoon Jr. grader: run a 48-digit plan through the SWMM model with pyswmm.

A plan is four groups of twelve digits, tank 1 first. Each digit is the
penstock setting for that hour: 0 closed, 1 = 25%, 2 = 50%, 3 = 75%, 4 open.
The result is the total volume spilled to rivers in ML (lower is better): the four tank
CSO outfalls plus the works overflow to the river.

Usage:
    python -m stormline.grade 444321101000-444442110002-444444400022-234432222221
    python -m stormline.grade --json PLAN
"""
import json
import os
import re
import sys
import tempfile
from pathlib import Path

from pyswmm import Links, Nodes, Simulation

INP = Path(__file__).resolve().parent.parent / "model" / "storm_line.inp"
HOURS = 12
TANKS = 4
OUTFALLS = ["CSO_1", "CSO_2", "CSO_3", "CSO_4", "CLYDE_BYPASS"]
NAMES = ["Tank 1 overflow", "Tank 2 overflow", "Tank 3 overflow", "Tank 4 overflow", "Works overflow"]


def parse_plan(text):
    """Accept any separators; return a 4 x 12 list of ints 0-4."""
    digits = re.sub(r"[^0-4]", "", str(text))
    if len(digits) != TANKS * HOURS:
        raise ValueError(f"A plan needs exactly {TANKS * HOURS} digits from 0 to 4; got {len(digits)}.")
    return [[int(d) for d in digits[i * HOURS:(i + 1) * HOURS]] for i in range(TANKS)]


def plan_code(plan):
    return "-".join("".join(str(v) for v in row) for row in plan)


def run(plan, inp=INP):
    """Simulate one plan. Returns a dict with total spill (ML) and a breakdown."""
    if isinstance(plan, str):
        plan = parse_plan(plan)
    tmp = tempfile.mkdtemp(prefix="stormline_")
    rpt, out = os.path.join(tmp, "run.rpt"), os.path.join(tmp, "run.out")
    try:
        return _run(plan, inp, rpt, out)
    finally:
        for f in (rpt, out):
            if os.path.exists(f):
                os.remove(f)
        os.rmdir(tmp)


def _run(plan, inp, rpt, out):
    with Simulation(str(inp), reportfile=rpt, outputfile=out) as sim:
        links = Links(sim)
        nodes = Nodes(sim)
        pens = [links[f"PEN_{i + 1}"] for i in range(TANKS)]

        def set_hour(h):
            for i in range(TANKS):
                pens[i].target_setting = plan[i][h] / 4.0

        sim.step_advance(3600)
        hour = 0
        set_hour(hour)
        for _ in sim:
            hour += 1
            if hour < HOURS:
                set_hour(hour)
        spills = {n: nodes[o].cumulative_inflow / 1000.0 for n, o in zip(NAMES, OUTFALLS)}
        treated = nodes["WORKS"].cumulative_inflow / 1000.0
        stored = sum(nodes[f"T{i + 1}"].volume for i in range(TANKS)) / 1000.0
        cont = sim.flow_routing_error
    total = sum(spills.values())
    return {"plan": plan_code(plan), "spill_ML": round(total, 2),
            "by_outfall_ML": {k: round(v, 2) for k, v in spills.items()},
            "treated_ML": round(treated, 2), "stored_at_end_ML": round(stored, 2),
            "continuity_error_pct": round(cont, 3)}


def main(argv):
    as_json = "--json" in argv
    args = [a for a in argv if a != "--json"]
    if not args:
        print(__doc__)
        return 2
    try:
        res = run(" ".join(args))
    except ValueError as e:
        print(e)
        return 2
    if as_json:
        print(json.dumps(res))
    else:
        print(f"Plan   {res['plan']}")
        print(f"Spill  {res['spill_ML']:.2f} ML  (lower is better)")
        for k, v in res["by_outfall_ML"].items():
            print(f"  {k:<18}{v:7.2f} ML")
        print(f"Treated {res['treated_ML']:.1f} ML, stored at end {res['stored_at_end_ML']:.1f} ML, "
              f"continuity error {res['continuity_error_pct']}%")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
