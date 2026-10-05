# Search log: Sewer Tycoon Jr. valve plan

All spills are official SWMM numbers from `stormline.grade.run` (unmodified model). Every
plan evaluated is in `research/runs.csv` (with per-outfall breakdown).

Setup note: `pip install pyswmm` fails on Debian's system setuptools (old `julian`
dependency); a venv with current setuptools works.

## Understanding the problem

- Total inflow 564 ML; storage to the crests 470 ML; works takes at most 20 ML/h × 12 h = 240 ML.
- **Identity: spill = 564 − treated − stored at end.** Water left in the tanks at 12:00
  is free. So the job is to treat as much as possible (works at exactly 20 ML/h for as many
  hours as possible) while never overtopping a tank.
- A tank's penstock flow depends on its depth (orifice: Q ∝ opening × √head), so an empty
  tank can't release much even fully open. Tank 4 (feeding the works) is nearly empty
  until hour 4, which is why early treatment is hard.
- Releasing more than 20 ML/h from tank 4 spills at the works just like a tank overflow.

## Reference plans

| Plan | Spill (ML) | Notes |
|---|---|---|
| `222222222222-222222222222-222222222222-222222222222` | 95.46 | all 50% (README baseline); T1–T3 overtop at the peak |
| `444444444444-444444444444-444444444444-444444444444` | 145.47 | all open; works overflow 79 ML (tank 4 releases > 20 ML/h) |
| `444321101000-444442110002-444444400022-234432222221` | 59.30 | example in grade.py docstring |
| 200 random plans | best 93.44, median 151 | structure matters |

## Lower bound (research/lp_bound.py)

LP relaxation: gates can pass any flow up to their fully-open rating, adjusted every
5 min (or every minute). The rating is concave in storage, so the bound is exact for
that relaxation. **Bound: 13.8 ML at 5-min steps, 12.5 ML at 1-min steps.** No hourly
5-level plan can beat ~12.5 ML.

The LP's optimal control: open everything early to move water downstream and build head in
tank 4; works at exactly 20 ML/h from hour 7; T1 holds back at the peak (hours 6–7) while
T2–T4 fill; all tanks full at the end. The unavoidable spill is at T1/T2 at the storm peak.

## Search runs

| # | Approach | Start | Result (ML) | Plan |
|---|---|---|---|---|
| 1 | Steepest descent, single-digit moves | all-2 (95.46) | 14.56 | `444422111222-434444221222-223444442222-222243322222` |
| 2 | Steepest descent, single-digit moves | docstring example (59.30) | 14.58 | `444441110002-444444220002-444444441022-234433222221` |
| 3 | Steepest descent, single-digit moves | all-4 (145.47) | 19.77 | `444440201004-444444211024-444444432233-444443322222` |
| 4 | Steepest descent + 2-digit moves (≈11.6k neighbours/round) | #1 (14.56) | 14.24 | `444441111222-434444221222-223444442222-222243322222` |
| 5 | Steepest descent + 2-digit moves | #2 (14.58) | **13.58** | `444441110022-444444220022-444444441022-234433222221` |
| 6 | LP-guided seed (round LP flows to nearest gate setting) | LP | 24.63 (unrefined) | `144441010000-124444120000-112444431000-111244322231` |

Notes:
- #4: two-digit move found "T1 fully open in hour 5, then 25% in hour 6": drain T1 hard
  just before the peak, then hold it back while T2/T3 take their own runoff.
- #5: a *late* fix: T1 sat at its crest in hours 9–11 with the gate shut and dribbled over;
  opening T1 and T2 to 50% in hour 11 passes that water to T3, which had room. Remaining
  spill: T3 6.7 ML in hour 7, T2 4.2 ML in hours 5–6, T1 2.2 ML (hours 7–10).
- quick_sim vs SWMM on good plans: quick_sim reads 2–3 ML high and swaps the order of
  close plans, so all searching is done directly on SWMM (~130 runs/s on 4 cores).
- LP bound refined (midpoint storage in the rating constraint, stable across step sizes):
  **12.1 ML** with continuous control.
| 7 | Block coordinate search (joint 625-combo blocks: one hour × 4 tanks, 2×2, one tank × 4 h) | #5 (13.58) | **12.47** (round 0, still running) | `444441110122-444444220122-444444441122-234433222221` |

Notes:
- #7: the first block move found was "open T1, T2 and T3 to 25% together in hour 10". T1 was
  at its crest and dribbling over (1.1 ML in hour 10), but opening T1 alone overtops T2, and
  opening T1+T2 overtops T3; it takes all three at once to pass the water down to T4.
  Single- and two-digit searches can't see a three-gate move.

### Correction to the lower bound

The 12.1 ML "bound" above and a beam-search estimate of 13.3 ML were **wrong**: the 12.47 ML
plan beats both. Checking "spill so far + LP cost-to-go" along that plan's trajectory showed
the LP was too pessimistic in hour 7. Cause: in SWMM a spilling tank rises a little above
its crest (the weir needs head to pass flow; e.g. T3 holds 121.1 ML against a 120 ML crest),
and that surcharge is temporary extra storage that later drains through the penstock. The
old LP capped storage at the crest. Fixed LP (`lp_core.py`): storage up to the 6 m max depth,
overflow ≥ weir rating 1.84 × 100 m × h^1.5 (convex, still an LP). Along the 12.47 plan the
bound is now monotone (10.6 → 12.5) as it should be.

**Corrected lower bound: 10.34 ML** (12 steps/h). Part of the remaining gap is LP slack: its
concave rating bound overestimates what a nearly empty tank can release (it charges 0.57 ML
"loss" to hour 3, when every gate in the 12.47 plan is already fully open).
| 7b | Block search, round 1 from 12.47 | #7 | no further improvement | 12.47 is optimal w.r.t. every joint hour block, 2×2 block and 4-hour single-tank block |
| 8 | Steepest descent (1-digit, shifts, all 2-digit pairs ±2) | 12.47 | no improvement | 12.47 is also a local optimum for these moves |
