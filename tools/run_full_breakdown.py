"""
Produce day-of-week and hourly breakdowns from a public-safe trade log.
Usage: python Tools/run_full_breakdown.py <path/to/executed_trade_log.csv>
"""
import csv
import sys
from pathlib import Path
from datetime import datetime, timezone

DAY_NAMES = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")


def main():
    log_path = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if not log_path or not log_path.exists():
        print("Usage: run_full_breakdown.py <path/to/executed_trade_log.csv>")
        sys.exit(1)
    if not log_path.is_absolute():
        log_path = Path.cwd() / log_path

    with open(log_path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        rr_col = outcome_col = risk_col = None
        for i, h in enumerate(header):
            if "RR" in h:
                rr_col = i
            if "Final outcome" in h:
                outcome_col = i
            if h.strip() == "Risk (R)":
                risk_col = i
        if rr_col is None or outcome_col is None:
            print("Could not find RR or Final outcome column.")
            sys.exit(1)

        rows = []
        dow = {}   # 0=Monday .. 6=Sunday
        hourly = {}  # 0..23
        for row in reader:
            if len(row) <= max(rr_col, outcome_col):
                continue
            try:
                rr = float(row[rr_col])
            except (ValueError, TypeError):
                continue
            outcome = row[outcome_col].strip().lower()
            if outcome not in ("win", "loss"):
                continue
            risk = 1.0
            if risk_col is not None and len(row) > risk_col:
                try:
                    risk = float(row[risk_col])
                except (ValueError, TypeError):
                    pass
            if risk <= 0:
                risk = 1.0
            realised = (rr * risk) if outcome == "win" else -risk
            ts = row[2].strip()
            try:
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                wd, hour_utc = dt.weekday(), dt.hour
            except (ValueError, TypeError):
                wd, hour_utc = 0, 0
            dow.setdefault(wd, {"w": 0, "l": 0, "r": 0.0})
            hourly.setdefault(hour_utc, {"w": 0, "l": 0, "r": 0.0})
            dow[wd]["r"] += realised
            dow[wd]["w" if outcome == "win" else "l"] += 1
            hourly[hour_utc]["r"] += realised
            hourly[hour_utc]["w" if outcome == "win" else "l"] += 1
            rows.append({"rr": rr, "outcome": outcome, "risk": risk, "realised": realised})

    wins = sum(1 for r in rows if r["outcome"] == "win")
    losses = sum(1 for r in rows if r["outcome"] == "loss")
    total = wins + losses
    total_r = sum(r["realised"] for r in rows)
    wr_pct = (100.0 * wins / total) if total else 0.0

    out_file = log_path.parent / "full_breakdown.txt"
    with open(out_file, "w", encoding="utf-8") as fh:
        fh.write(f"Run: {log_path.parent.name}\n")
        fh.write(f"Total: {total} trades | Wins: {wins} | Losses: {losses} | WR: {wr_pct:.1f}% | Realised R: {total_r:+.4f}R\n\n")

        # DoW
        fh.write("DAY OF WEEK (entry candle date, UTC)\n")
        fh.write("Day            Wins   Losses   Trades   Win rate %   Realised R\n")
        fh.write("-" * 65 + "\n")
        for wd in range(7):
            d = dow.get(wd, {"w": 0, "l": 0, "r": 0.0})
            t = d["w"] + d["l"]
            wr = (100.0 * d["w"] / t) if t else 0.0
            fh.write(f"{DAY_NAMES[wd]:<14} {d['w']:>6} {d['l']:>8} {t:>8} {wr:>10.1f}% {d['r']:>+12.4f}R\n")
        fh.write("-" * 65 + "\n")
        fh.write(f"{'TOTAL':<14} {wins:>6} {losses:>8} {total:>8} {wr_pct:>10.1f}% {total_r:>+12.4f}R\n\n")

        # Hourly
        fh.write("HOUR OF DAY (UTC) 00:00-23:00\n")
        fh.write("Hour (UTC)   Wins   Losses   Trades   Win rate %   Realised R\n")
        fh.write("-" * 65 + "\n")
        for h in range(24):
            d = hourly.get(h, {"w": 0, "l": 0, "r": 0.0})
            t = d["w"] + d["l"]
            wr = (100.0 * d["w"] / t) if t else 0.0
            fh.write(f"{h:02d}:00         {d['w']:>4} {d['l']:>8} {t:>8} {wr:>10.1f}% {d['r']:>+12.4f}R\n")
        fh.write("-" * 65 + "\n")
        fh.write(f"TOTAL            {wins:>4} {losses:>8} {total:>8} {wr_pct:>10.1f}% {total_r:>+12.4f}R\n\n")

        fh.write("Strategy-specific filter and optimisation analysis is intentionally withheld.\n")

    print(f"Written: {out_file}")
    print(f"  Trades: {total}  Wins: {wins}  Losses: {losses}  WR: {wr_pct:.1f}%  Realised R: {total_r:+.4f}R")


if __name__ == "__main__":
    main()
