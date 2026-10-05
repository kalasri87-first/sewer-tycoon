"""Build the Sewer Tycoon Jr. SWMM model (model/storm_line.inp).

The network is a cascade of four CSO storage tanks on a combined sewer:
tank 1 (T1) passes flow to T2, then T3, then T4, which feeds the treatment works. Each tank has an outlet penstock (a SWMM orifice whose setting, 0 to 1,
the grader changes every hour), an overflow weir to its own CSO outfall, and tank 4
discharges into a small inlet sump at the works. The works outlet is capped at 20 ML/h;
anything more overtops the sump's bypass weir to the Clyde. Inflows (runoff plus upstream
sewer flow) are fixed hourly series, so there is no hydrology to argue about.

Run:  python -m stormline.build_model
"""
import math
from pathlib import Path


def _round(x):
    """Round half up, to match the browser game exactly."""
    return int(math.floor(x + 0.5))


ML_PER_H = 1000.0 / 3600.0          # 1 ML/h in m3/s
HOURS = 12
SCALE = 1.25
BASE_P = [3, 8, 16, 20, 12, 6, 3, 1, 0, 0, 0, 0]
AREA = [1.5, 1.5, 1.5, 1.0]
LAG = [0, 1, 2, 3]                   # the storm reaches each tank one hour after the one above
P = [x * SCALE for x in BASE_P]
RUNOFF = [[_round(P[t - LAG[i]] * AREA[i]) if 0 <= t - LAG[i] < HOURS else 0 for t in range(HOURS)] for i in range(4)]
UPSTREAM = [_round(x * SCALE) for x in [4, 6, 10, 14, 12, 8, 5, 3, 2, 1, 1, 0]]

NAMES = ["Tank 1", "Tank 2", "Tank 3", "Tank 4"]
CAP_ML = [100, 100, 120, 150]          # storage up to the overflow crest, ML
QMAX_MLH = [34, 34, 34, 38]            # penstock flow when fully open with the tank at the crest, ML/h
WORKS_MLH = 20                         # flow to full treatment, ML/h
CREST = 5.0                            # overflow crest depth in each tank, m
INVERT = [30.0, 20.0, 10.0, 0.0]       # tank inverts, m (each tank sits well above the next)
CD = 0.65                              # orifice discharge coefficient
GATE_H = 1.0                           # penstock opening height when fully open, m


def inflow_mlh(i, t):
    return RUNOFF[i][t] + (UPSTREAM[t] if i == 0 else 0)


def build(path):
    g = 9.81
    lines = []
    w = lines.append
    w("[TITLE]\nSewer Tycoon Jr. (fictional CSO network for the WWCE 2026 AI agents workshop)\n")
    w("[OPTIONS]")
    for k, v in [("FLOW_UNITS", "CMS"), ("INFILTRATION", "HORTON"), ("FLOW_ROUTING", "DYNWAVE"),
                 ("START_DATE", "01/01/2026"), ("START_TIME", "00:00:00"),
                 ("REPORT_START_DATE", "01/01/2026"), ("REPORT_START_TIME", "00:00:00"),
                 ("END_DATE", "01/01/2026"), ("END_TIME", "12:00:00"),
                 ("REPORT_STEP", "00:05:00"), ("ROUTING_STEP", "0:00:05"), ("VARIABLE_STEP", "0"),
                 ("ALLOW_PONDING", "NO"), ("SKIP_STEADY_STATE", "NO"), ("INERTIAL_DAMPING", "PARTIAL"),
                 ("NORMAL_FLOW_LIMITED", "BOTH"), ("MIN_SURFAREA", "1.14"), ("MAX_TRIALS", "8"),
                 ("HEAD_TOLERANCE", "0.0015"), ("THREADS", "1")]:
        w(f"{k:<22}{v}")
    w("")
    w("[OUTFALLS]")
    for i in range(4):
        w(f"CSO_{i+1}  {INVERT[i]-4:.2f}  FREE  NO")
    w("WORKS  -20.00  FREE  NO")
    w("CLYDE_BYPASS  -20.00  FREE  NO")
    w("")
    w("[STORAGE]")
    w(";;Name  Elev  MaxDepth  InitDepth  Shape  Coeff  Expon  Const  SurDepth  Fevap")
    for i in range(4):
        area = CAP_ML[i] * 1000.0 / CREST
        w(f"T{i+1}  {INVERT[i]:.2f}  6.0  0  FUNCTIONAL  0  0  {area:.1f}  0  0")
    w("SUMP  -10.00  3.0  0  FUNCTIONAL  0  0  200.0  0  0")
    w("")
    w("[ORIFICES]")
    w(";;Name  From  To  Type  Offset  Qcoeff  Gated  CloseTime")
    to = ["T2", "T3", "T4", "SUMP"]
    for i in range(4):
        w(f"PEN_{i+1}  T{i+1}  {to[i]}  SIDE  0  {CD}  NO  0")
    w("")
    w("[WEIRS]")
    w(";;Name  From  To  Type  CrestHt  Qcoeff  Gated  EndCon  EndCoeff  Surcharge")
    for i in range(4):
        w(f"CSO_WEIR_{i+1}  T{i+1}  CSO_{i+1}  TRANSVERSE  {CREST}  1.84  NO  0  0  YES")
    w("BYPASS_WEIR  SUMP  CLYDE_BYPASS  TRANSVERSE  1.0  1.84  NO  0  0  YES")
    w("")
    w("[OUTLETS]")
    w(";;Name  From  To  Offset  Type  QTable/Qcoeff  Qexpon  Gated")
    w("TO_WORKS  SUMP  WORKS  0  TABULAR/DEPTH  WORKS_CAP  NO")
    w("")
    w("[XSECTIONS]")
    w(";;Link  Shape  Geom1  Geom2  Geom3  Geom4")
    for i in range(4):
        # width so a fully open gate passes QMAX with the tank at the crest: Q = Cd*A*sqrt(2g(h - H/2))
        width = QMAX_MLH[i] * ML_PER_H / (CD * GATE_H * (2 * g * (CREST - GATE_H / 2)) ** 0.5)
        w(f"PEN_{i+1}  RECT_CLOSED  {GATE_H}  {width:.4f}  0  0")
    for i in range(4):
        w(f"CSO_WEIR_{i+1}  RECT_OPEN  1.0  100  0  0")
    w("BYPASS_WEIR  RECT_OPEN  2.0  50  0  0")
    w("")
    w("[CURVES]")
    cap = WORKS_MLH * ML_PER_H
    w("WORKS_CAP  Rating  0  0")
    w(f"WORKS_CAP  0.2  {cap:.4f}")
    w(f"WORKS_CAP  3.0  {cap:.4f}")
    w("")
    w("[TIMESERIES]")
    for i in range(4):
        for t in range(HOURS):
            q = inflow_mlh(i, t) * ML_PER_H
            w(f"IN_T{i+1}  {t:.4f}  {q:.5f}")
            w(f"IN_T{i+1}  {t+0.9999:.4f}  {q:.5f}")
        w(f"IN_T{i+1}  {HOURS:.4f}  0")
    w("")
    w("[INFLOWS]")
    w(";;Node  Constituent  TimeSeries  Type  Mfactor  Sfactor")
    for i in range(4):
        w(f"T{i+1}  FLOW  IN_T{i+1}  FLOW  1.0  1.0")
    w("")
    w("[REPORT]\nINPUT NO\nCONTROLS NO\nSUBCATCHMENTS NONE\nNODES NONE\nLINKS NONE\n")
    w("[COORDINATES]")
    for i in range(4):
        w(f"T{i+1}  {i*100}  {300-i*100}")
        w(f"CSO_{i+1}  {i*100}  {260-i*100}")
    w("SUMP  400  -20\nWORKS  450  -60\nCLYDE_BYPASS  350  -60")
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text("\n".join(lines) + "\n")
    return path


if __name__ == "__main__":
    out = Path(__file__).resolve().parent.parent / "model" / "storm_line.inp"
    print("wrote", build(out))
