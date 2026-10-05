# Instructions for coding agents (Claude Code, Codex, and similar)

You are helping a team at the WWCE 2026 AI agents workshop play **Sewer Tycoon Jr.**, a CSO
control challenge on a fictional Glasgow combined sewer.

## Goal
Find the 48-digit penstock plan that **minimises total volume spilled to rivers (ML)** when
graded by the SWMM model in this repo. Lower is better. Report the best plan code and its
SWMM spill, plus a short plain-language explanation of the strategy.

## The rules
- A plan is four groups of twelve digits separated by dashes, tank 1 first, one digit per hour (0 = closed, 1 = 25%, 2 = 50%, 3 = 75%, 4 = open), for example `222222222222-222222222222-222222222222-222222222222`. Always report plans in exactly this format.
- The only official score is `python -m stormline.grade PLAN` (or `stormline.grade.run`).
- Do not edit `model/storm_line.inp`, `stormline/build_model.py` or `stormline/grade.py`.
  Graders use a clean copy, so edits only change your local numbers.

## Useful facts
- One SWMM run takes roughly 0.03 to 0.1 s. Runs are independent, so you can run them in parallel processes. Budget your search accordingly.
- `stormline.quick_sim.quick_spill(plan)` is the browser game's stand-in. It is faster
  but only approximate (usually within a few ML of SWMM). Fine for exploring, never for
  the final number.
- `run(plan)` returns spill by outfall, volume treated, and storage left at the end. Use
  the breakdown to understand *why* a plan spills, not just how much.
- Inflows are in `data/inflows.csv`.
- The treatment works has no storage. It treats up to 20 ML/h of whatever tank 4 releases
  at that moment; any flow above 20 ML/h overflows to the river and counts as spill.

## Working style
- Explain your hypotheses to the team as you go; they should learn something about
  real-time control, not just receive a number.
- Keep a log of plans tried and their SWMM spill so the team can see the loop working.
