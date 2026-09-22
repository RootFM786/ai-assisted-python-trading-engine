"""
Reassess realised R from executed_trade_log.csv using two methods and report.
Usage: python Tools/verify_realised_r.py <path/to/executed_trade_log.csv>

Method A: From log columns — win: realised = RR (entry→TP1) × Risk (R); loss: realised = -Risk (R).
Method B: From actual points — win: realised = TP1 result (points) / |entry - SL|; loss: realised = -Risk (R).

Both should match for TP1 hits (RR is defined as (TP1 result distance) / (SL distance)). 
Outputs totals, per-trade stats, and any discrepancy.
"""

import csv
import sys
from pathlib import Path


def main():
    log_path = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if not log_path or not log_path.exists():
        print("Usage: verify_realised_r.py <path/to/executed_trade_log.csv>")
        sys.exit(1)
    if not log_path.is_absolute():
        log_path = Path.cwd() / log_path

    with open(log_path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        # Find column indices
        col = {}
        for i, h in enumerate(header):
            h = h.strip()
            if h == "Entry price" or (i == 6): col["entry"] = i
            if h == "Stop loss" or (i == 7): col["sl"] = i
            if "RR" in h: col["rr"] = i
            if h == "Risk (R)": col["risk"] = i
            if "Target result (points)" in h or "TP1 result (points)" in h: col["tp1_pts"] = i
            if "Final outcome" in h: col["outcome"] = i
        missing = {"entry", "sl", "rr", "risk", "tp1_pts", "outcome"} - set(col)
        if missing:
            raise ValueError(f"missing public verification columns: {sorted(missing)}")

        r_from_rr = 0.0
        r_from_pts = 0.0
        wins = losses = 0
        rr_per_trade = []

        for row in reader:
            if len(row) <= max(col["outcome"], col["rr"]):
                continue
            outcome = row[col["outcome"]].strip().lower()
            if outcome not in ("win", "loss"):
                continue
            try:
                rr = float(row[col["rr"]])
                risk = float(row[col["risk"]]) if col["risk"] < len(row) else 1.0
            except (ValueError, TypeError):
                continue
            if risk <= 0:
                risk = 1.0

            # Method A: from RR column
            if outcome == "win":
                r_a = rr * risk
                wins += 1
                rr_per_trade.append(rr)
            else:
                r_a = -risk
                losses += 1
            r_from_rr += r_a

            # Method B: from actual points (wins only; loss = -risk)
            if outcome == "win":
                try:
                    entry = float(row[col["entry"]])
                    sl = float(row[col["sl"]])
                    tp1_pts = float(row[col["tp1_pts"]])
                except (ValueError, TypeError, IndexError):
                    r_from_pts += r_a
                    continue
                risk_pts = abs(entry - sl)
                if risk_pts > 0:
                    r_b = tp1_pts / risk_pts
                else:
                    r_b = r_a
                r_from_pts += r_b
            else:
                r_from_pts += -risk

        n = wins + losses
        wr = (100.0 * wins / n) if n else 0.0
        avg_rr = sum(rr_per_trade) / len(rr_per_trade) if rr_per_trade else 0.0
        min_rr = min(rr_per_trade) if rr_per_trade else None
        max_rr = max(rr_per_trade) if rr_per_trade else None

    print("=== Realised R verification ===")
    print(f"File: {log_path.name}")
    print(f"Trades: {n}  Wins: {wins}  Losses: {losses}  WR: {wr:.1f}%")
    print()
    print("Method A (from log columns: RR × Risk for win, -Risk for loss):")
    print(f"  Total realised R: {r_from_rr:+.4f}R")
    print()
    print("Method B (from actual points: TP1 result pts / |entry - SL| for win, -Risk for loss):")
    print(f"  Total realised R: {r_from_pts:+.4f}R")
    print()
    diff = abs(r_from_rr - r_from_pts)
    if diff > 0.001:
        print(f"  Discrepancy: {diff:.4f}R  (investigate)")
    else:
        print("  Match (within 0.001R).")
    print()
    print("RR (entry-to-target) per trade (wins only):")
    print(f"  Min: {min_rr:.4f}  Max: {max_rr:.4f}  Avg: {avg_rr:.4f}")
    print(f"  => Avg R per winning trade: {avg_rr:.4f}R  (with Risk=1)")
    print()
    print("Interpretation: Total R is the sum of (RR × risk) across winning records and -risk for losses.")


if __name__ == "__main__":
    main()
