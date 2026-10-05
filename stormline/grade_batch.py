"""Grade a CSV of submissions with SWMM and print a ranked leaderboard.

Works directly on the Google Form's response sheet downloaded as CSV (columns such as
"Timestamp", "Team Name", "Your Approach", "Your solution"); columns are matched by
"team", "approach" (or "level") and "solution" (or "plan"). Each team's best plan counts.

    python -m stormline.grade_batch responses.csv
    python -m stormline.grade_batch responses.csv --out results.csv
Invalid plans are listed separately rather than stopping the run.
"""
import csv
import sys

from .grade import run


def _col(headers, *words):
    for w in words:
        for h in headers:
            if w in h.lower():
                return h
    raise SystemExit(f"No column containing any of {words} in {headers}")


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    out = argv[argv.index("--out") + 1] if "--out" in argv else None
    best, bad, n = {}, [], 0
    with open(argv[0], newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        ct = _col(reader.fieldnames, "team")
        cl = _col(reader.fieldnames, "approach", "level")
        cp = _col(reader.fieldnames, "solution", "plan", "code")
        for r in reader:
            n += 1
            team, level = r[ct].strip(), (r[cl].strip() or "(no approach given)")
            try:
                res = run(r[cp])
            except Exception as e:  # invalid plan code
                bad.append((team or "?", str(e)))
                continue
            key = (team.lower(), level.lower())
            if key not in best or res["spill_ML"] < best[key]["spill_ML"]:
                best[key] = {"team": team, "level": level, "spill_ML": res["spill_ML"], "plan": res["plan"]}
    rows = sorted(best.values(), key=lambda r: r["spill_ML"])
    print(f"{n} submissions, {len(rows)} team entries graded with SWMM\n\nOverall")
    for k, r in enumerate(rows, 1):
        print(f"{k:3d}. {r['team']:<28}{r['level']:<22}{r['spill_ML']:8.2f} ML")
    for lvl in sorted({r["level"] for r in rows}):
        sub = [r for r in rows if r["level"].lower() == lvl.lower()]
        if sub:
            print(f"Best {lvl}: {sub[0]['team']} ({sub[0]['spill_ML']:.2f} ML)")
    if bad:
        print("\nCould not grade:")
        for t, e in bad:
            print(f"  {t}: {e}")
    if out:
        with open(out, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["team", "level", "spill_ML", "plan"])
            w.writeheader()
            w.writerows(rows)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
