"""Compute max drawdown in R from an executed_trade_log.csv.
Sorts by exit timestamp, builds cumulative R, then peak-to-trough drawdown.
Usage: python max_drawdown_r.py <path_to_executed_trade_log.csv>
"""
import csv
import sys
from pathlib import Path

LOG = Path(sys.argv[1]) if len(sys.argv) > 1 else None
if not LOG or not LOG.exists():
    print("Usage: python max_drawdown_r.py <path_to_executed_trade_log.csv>")
    sys.exit(1)
if not LOG.is_absolute():
    LOG = Path.cwd() / LOG

with open(LOG, newline="", encoding="utf-8") as f:
    reader = csv.reader(f)
    header = next(reader)
    rr_col = outcome_col = exit_col = risk_col = None
    for i, h in enumerate(header):
        if "RR" in h:
            rr_col = i
        if "Final outcome" in h:
            outcome_col = i
        if "Exit timestamp" in h:
            exit_col = i
        if h.strip() == "Risk (R)":
            risk_col = i
    if rr_col is None or outcome_col is None or exit_col is None:
        print(f"Missing columns. Header: {header}")
        sys.exit(1)

    rows = []
    for row in reader:
        if len(row) <= max(rr_col, outcome_col, exit_col):
            continue
        exit_ts = row[exit_col].strip()
        outcome = row[outcome_col].strip().lower()
        try:
            rr = float(row[rr_col])
        except (ValueError, TypeError):
            rr = 0.0
        risk = 1.0
        if risk_col is not None and len(row) > risk_col:
            try:
                risk = float(row[risk_col])
            except (ValueError, TypeError):
                pass
        if risk <= 0:
            risk = 1.0
        r = (rr * risk) if outcome == "win" else -risk
        rows.append((exit_ts, r, outcome, rr))

# Sort by exit timestamp
rows.sort(key=lambda x: x[0])

cum = 0.0
peak = 0.0
max_dd = 0.0
peak_ts = None
dd_peak_ts = None
dd_peak_cum = None
trough_ts = None
trough_cum = None

for exit_ts, r, outcome, rr in rows:
    cum += r
    if cum > peak:
        peak = cum
        peak_ts = exit_ts
    dd = peak - cum
    if dd > max_dd:
        max_dd = dd
        dd_peak_ts = peak_ts
        dd_peak_cum = peak
        trough_ts = exit_ts
        trough_cum = cum

total_r = cum
n = len(rows)
print(f"Trades (by exit order): {n}")
print(f"Total Realised R:       {total_r:+.4f}R")
print(f"Max drawdown (R):       {max_dd:.4f}R")
if dd_peak_ts and trough_ts:
    print(f"Peak (before DD):       {dd_peak_ts}  (cumulative R = {dd_peak_cum:+.4f})")
    print(f"Trough (max DD point): {trough_ts}  (cumulative R = {trough_cum:+.4f})")
