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
| 9 | Beam search over hours, width 30, all 625 gate combos per hour, score = SWMM spill so far + corrected-LP cost-to-go; prune any prefix whose spill already ≥ incumbent | empty plan | no plan < 12.47 | beam converged on the same hour-6 state as the 12.47 plan ([98.1, 98.4, 121.5, 75.4] ML); by hour 9 every surviving path had spilled ≥ 12.47 |

Notes on #9: the beam is an independent check. It is guided by the LP, not by local moves,
yet it lands in the same basin. From the hour-6 state the LP says ≥ 8.04 ML more spill is
unavoidable; the 12.47 plan spills 8.48 more, so there is at most ~0.4 ML left to find in
hours 7–12 from that state.
| 10 | Tail beam (width 300) from the 12.47 plan's first 6 hours: all 625 combos per hour, exact incumbent pruning | 12.47 | **12.45** | `444441110200-444444220200-444444441200-234433222200` |

Notes on #10: effectively an exhaustive search of hours 7–12 given hours 1–6 (only 3 states
survive pruning after hour 7, 1 after hours 8 and 9). The gain is in hour 10: T1, T2, T3 at
50% together (instead of 25%) moves T1's leftover water down to T4 in one go; hours 11–12 can
then be closed. So for this opening, 12.45 is the best tail; any further gain must come
from changing hours 1–6.
| 11 | Iterated local search (kicks of 2–6 cells around the peak, single-digit re-descent, accept ties), 20 min | 12.47 | no improvement | |
| 12 | Continuous relaxation in SWMM: CMA-ES over 48 settings in [0,1] (30k SWMM runs), not an official score | 12.45 plan | 12.23 (continuous) | rounded to quarters: `444441110100-444444220200-424444441210-244443222112` = 18.76 official |

Notes on #12: with gate settings free to take any value (still held for a whole hour),
SWMM gets 12.23 ML, so the 5-level restriction costs only ~0.2 ML in this basin. The
continuous optimum has the same shape as the 12.45 plan. The main difference is tank 4 in
hours 5–6 at 3.5 and 2.9 (on the 0–4 scale), i.e. *between* the allowed settings: it wants
to release just under 20 ML/h while its level rises, which 50%/75% can only approximate.
Naive rounding breaks the timing (18.76 ML), so the discrete search is still needed.

SWMM engine used throughout: pyswmm 2.2.0 / swmm-toolkit 0.17.0 / SWMM 5.2.4. The 12.45
plan's report has no warnings or flooding; continuity error 0.008%.
| 13 | Steepest descent (1-digit, shifts, 2-digit) from the rounded CMA plan | 18.76 | 12.45 | `444441110200-444444220200-424444441210-244443222212` (ties #10; two 1-digit moves, then stuck) |
| 14 | Branch-and-bound over hours, diversity grid 2 ML, width 100: prune if SWMM spill so far ≥ 12.45 or spill + LP bound ≥ 12.45 | empty plan | nothing < 12.45 | after hour 3 only 5 of 344 states could still beat 12.45; empty by hour 9 |
| 15 | Validation of the corrected LP bound (research/validate_lp.py): 350 plans with spill < 16 ML (50 best + 300 random of 25,855), check spill so far + LP ≤ final spill at every hour | — | bound holds | worst excess +0.005 ML, which is the grader's rounding of the final score to 0.01 ML (occurs at hours 10–11 where the LP term is 0) |

So the branch-and-bound pruning (#14, #16) is sound: no plan that would score ≤ 12.44 can be
pruned at an incumbent of 12.45.
| 16 | Branch-and-bound as #14 but fine grid (0.25 ML), width up to 3000 | empty plan | nothing < 12.45 | viable states per hour: 5, 42, 39, 47, 259, 591, 38, 7, then 0 at hour 9 (every path ≥ 12.45 by then) |

Caveat on #14/#16: states within 0.25 ML of each other are merged, and the kept
representative is arbitrary. This merged the 12.45 plan's own hour-1 state with a
near-identical one (T3 holding 0.05 ML vs 0), so these runs are very wide searches but not
strict proofs of optimality.
| 17 | Exhaustive-tail check (research/tails.py): branch-and-bound over hours 7–12 (0.05 ML de-dup, LP pruning) from the 30 best openings in runs.csv, first by digits, then de-duplicated by the hour-6 *tank state* (30 genuinely different states, best known 12.45–12.82) | — | nothing < 12.45 | no known opening has a finish that beats 12.45 |

## Result

**Best plan: `444441110200-444444220200-444444441200-234433222200`, 12.45 ML total spill**
(official `python -m stormline.grade`; T1 1.05, T2 4.21, T3 7.19, T4 0.00, works 0.00).

| Hour | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Tank 1 | 4 | 4 | 4 | 4 | 4 | 1 | 1 | 1 | 0 | 2 | 0 | 0 |
| Tank 2 | 4 | 4 | 4 | 4 | 4 | 4 | 2 | 2 | 0 | 2 | 0 | 0 |
| Tank 3 | 4 | 4 | 4 | 4 | 4 | 4 | 4 | 4 | 1 | 2 | 0 | 0 |
| Tank 4 | 2 | 3 | 4 | 4 | 3 | 3 | 2 | 2 | 2 | 2 | 0 | 0 |

Strategy, in plain terms:
1. **Only the peak matters.** Spill = 564 − treated − stored at noon, and stored water is
   free. All spill happens in hours 5–9; afterwards the only job is not to overtop anything.
2. **Hours 1–5: everything open.** Push water downstream while the tanks are low, so each
   has room for its own runoff peak and tank 4 builds the depth it needs to feed the works
   (a nearly empty tank can't release much, however wide the gate).
3. **Hours 6–8: hold back at the top, run flat out at the bottom.** T1 drops to 25% so the
   upstream flood waits in T1 while T2 and T3 take their own runoff; T3 stays fully open
   because the T3→T4 penstock is the bottleneck and T4 is the only tank with room left.
4. **Never more than 20 ML/h to the works.** As tank 4 fills, its gate steps down from 75%
   to 50% so the works get close to, but not over, 20 ML/h. (A wider gate on a full tank
   would overflow at the works, which counts as spill just the same.)
5. **Hour 10: open T1, T2, T3 together (50%)** to pass T1's leftover water down to T4 in one
   go; opening T1 alone would just overtop T2. Then close everything.

Evidence that this is at or very near the best possible:
- LP lower bound with ideal minute-by-minute control: 10.3 ML. Continuous (any setting,
  hourly) control in SWMM: 12.23 ML, so the 5-level rule costs only ~0.2 ML here.
- Every independent method converged on 12.45: local search (single, shift, 2-digit),
  joint block search, LP-guided beam, branch-and-bound with an LP bound validated on 350
  trajectories, iterated local search, CMA-ES + descent, and exhaustive tails from 30
  different openings.
- 201,967 distinct plans fully scored with SWMM (plus ~1M partial simulations inside the
  beam/branch-and-bound); 346 plans tie at 12.45. They differ only in settings that change
  no flow (e.g. a gate on a nearly empty tank), and none is lower.

Caveats: graded with pyswmm 2.2.0 / SWMM 5.2.4. Differences of a few hundredths of an ML
(e.g. 12.45 vs 12.47) are within what a different SWMM version could shift. The plan is
tuned to a perfectly known storm and would need feedback control to cope with forecast
error. The raw log of every plan scored is `research/runs.csv.gz`.
