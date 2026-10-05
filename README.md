# Sewer Tycoon Jr.

*by the Digital Water Lab ([digitalwaterlab.org](https://www.digitalwaterlab.org)), University of Michigan*

A real-time control challenge for the **IWA World Water Congress 2026 (Glasgow) hands-on
AI agents workshop**. Four CSO storage tanks (tanks 1 to 4) on a fictional combined sewer
pass flow downhill to a treatment works that can take 20 ML/h. A twelve-hour storm brings 564 ML. Set each tank's outlet penstock hour
by hour so that **as little as possible spills to the rivers**.

The sewer network and all numbers are invented.

## How spills happen

There are two ways to spill, and both count the same:

- **Tank overflow.** When a tank is full, anything more spills over its CSO weir to the river.
- **Works overflow.** The treatment works has no storage. It treats up to 20 ML/h of whatever
  tank 4 releases at that moment; any flow above 20 ML/h overflows to the river.

## The official grader is SWMM

```bash
pip install -r requirements.txt
python -m stormline.grade 222222222222-222222222222-222222222222-222222222222
```

```
Spill  95.46 ML  (lower is better)
  Tank 1 overflow ...
```

The browser game uses a fast stand-in that tracks SWMM to within a few ML. Plans are
interchangeable: copy your plan code from the browser and grade it here. **Submitted
plans are scored with this SWMM model**, so teams that tune their plan against SWMM
directly have an edge at the top of the leaderboard.

## Plan format

A plan is four groups of twelve digits separated by dashes, tank 1 first, one digit per hour (0 = closed, 1 = 25%, 2 = 50%, 3 = 75%, 4 = open), for example `222222222222-222222222222-222222222222-222222222222`. The grader ignores separators, but please submit plans in exactly this format.

## What's in the repo

| Path | What it is |
|---|---|
| `model/storm_line.inp` | The SWMM model: four storage units, orifice penstocks, CSO weirs, works inlet with a 20 ML/h outlet and an overflow weir. |
| `stormline/grade.py` | Official grader. Runs a plan with pyswmm, changing each penstock every hour. |
| `stormline/quick_sim.py` | The browser game's stand-in simulator, for fast exploration. |
| `stormline/build_model.py` | Regenerates the .inp from the parameters (for the curious; don't edit for submissions). |
| `data/inflows.csv` | Hourly runoff per tank and upstream sewer flow, ML. |
| `examples/starter_loop.py` | A simple hill-climbing loop against SWMM. Beat it. |
| `stormline/grade_batch.py` | For organisers: grades the Google Form response sheet (downloaded as CSV) and prints the leaderboard, keeping each team's best plan. |
| `AGENTS.md` | Instructions for Claude Code, Codex, and other coding agents. |

## The levels

1. **Play**: set the valves by hand in the browser game.
2. **Basic prompting**: explain the problem to a chat assistant and work it out together.
3. **Agentic tool use**: give an assistant the utility's sensor data to analyse and plan from.
4. **Automated research loop**: open this folder in a coding agent and let it search against the model.

## Submitting

Paste your plan code, team name and level into the workshop form. The organisers grade
every submission with `stormline.grade` and the lowest spill wins.

## Further reading

- Schmidt, J., Tobias, M., Loos, S., and Kerkez, B. (2025). Democratizing Sewer Data: Customized
  Interfaces Allow Non-engineers to Take Action Against Urban Flooding. ACM SIGCAS/SIGCHI Conference
  on Computing and Sustainable Societies (COMPASS '25). https://doi.org/10.1145/3715335.3735480
  (the research behind SewerTycoon, https://www.digitalwaterlab.org/sewertycoon)
- Rimer, S.P., Mullapudi, A., Troutman, S.C., et al., and Kerkez, B. (2023). pystorms: A simulation
  sandbox for the development and evaluation of stormwater control algorithms. Environmental
  Modelling & Software, 162, 105635. https://arxiv.org/abs/2110.12289
