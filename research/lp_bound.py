"""Lower bound on spill: LP relaxation of the control problem (see lp_core.py).

Relaxations vs the real game: each penstock can pass *any* flow between zero and its
fully-open rating, changed every time step (not 5 settings held for an hour). Tanks may
surcharge above the crest, with the overflow at least the weir rating of that head, as in
SWMM. No plan can beat this bound, apart from small effects the LP ignores (the 0.2 ML
works sump, discretisation).

    python research/lp_bound.py [steps_per_hour]
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lp_core import solve  # noqa: E402

from stormline.build_model import HOURS  # noqa: E402


def report(sph=12):
    val, x = solve(0, [0, 0, 0, 0], sph, full=True)
    print(f"LP lower bound on spill: {val:.2f} ML  (tank spills {x['W'].sum(1).round(2)}, works {x['B'].sum():.2f})")
    print("hour | mean penstock flow Q1..Q4 (ML/h) | end storage S1..S4 (ML)")
    for h in range(HOURS):
        sl = slice(h * sph, (h + 1) * sph)
        q = x["Q"][:, sl].mean(1)
        print(f"{h + 1:4d} | " + " ".join(f"{v:5.1f}" for v in q) + " | " +
              " ".join(f"{v:5.1f}" for v in x["S"][:, (h + 1) * sph - 1]))
    return val


if __name__ == "__main__":
    report(int(sys.argv[1]) if len(sys.argv) > 1 else 12)
