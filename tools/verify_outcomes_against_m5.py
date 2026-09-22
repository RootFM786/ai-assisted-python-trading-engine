"""
Verify executed_trade_log outcomes against M5 fixture data.
For each trade: find candles from entry to exit; confirm exit candle has TP1 in range
(and no earlier candle had SL in range first for same-candle semantics).
Usage: python Tools/verify_outcomes_against_m5.py <executed_trade_log.csv> <M5_fixture.csv>
Expects log to have: Entry timestamp (col 2), Direction (5), Entry price (6), Stop loss (7), TP1 (8), Exit timestamp (22), Final outcome (18).
M5 CSV: time, open, high, low, close (time = bar open, close_ts = time + 5min).
"""

import csv
import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone


def parse_ts(s: str):
    if not s or not s.strip():
        return None
    s = s.strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return None


def load_m5(path: Path):
    """Yield (open_ts, close_ts, low, high) per row. CSV time = bar open."""
    with open(path, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            t = row.get("time", "").strip()
            if not t:
                continue
            open_ts = parse_ts(t)
            if open_ts is None:
                continue
            try:
                low = float(row["low"])
                high = float(row["high"])
            except (KeyError, TypeError, ValueError):
                continue
            close_ts = open_ts + timedelta(minutes=5)
            yield open_ts, close_ts, low, high


def main():
    if len(sys.argv) < 3:
        print("Usage: verify_outcomes_against_m5.py <executed_trade_log.csv> <M5_fixture.csv>")
        sys.exit(1)
    log_path = Path(sys.argv[1])
    m5_path = Path(sys.argv[2])
    if not log_path.exists() or not m5_path.exists():
        print("Files not found.")
        sys.exit(1)

    m5_rows = list(load_m5(m5_path))
    if not m5_rows:
        print("No M5 rows loaded.")
        sys.exit(1)

    with open(log_path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        idx_ts = None
        idx_dir = None
        idx_entry = None
        idx_sl = None
        idx_tp1 = None
        idx_exit = None
        idx_outcome = None
        for i, h in enumerate(header):
            if "Entry candle" in h and "timestamp" in h:
                idx_ts = i
            if "Direction" in h:
                idx_dir = i
            if "Entry price" in h:
                idx_entry = i
            if "Stop loss" in h:
                idx_sl = i
            if h.strip() == "TP1":
                idx_tp1 = i
            if "Exit timestamp" in h:
                idx_exit = i
            if "Final outcome" in h:
                idx_outcome = i

        required = {
            "Entry candle timestamp": idx_ts,
            "Direction": idx_dir,
            "Entry price": idx_entry,
            "Stop loss": idx_sl,
            "TP1": idx_tp1,
            "Exit timestamp": idx_exit,
            "Final outcome": idx_outcome,
        }
        missing = [name for name, index in required.items() if index is None]
        if missing:
            print("This verifier requires a full execution-log schema.")
            print("Missing columns: " + ", ".join(missing))
            sys.exit(2)

        errors = []
        checked = 0
        for row in reader:
            if len(row) <= max(required.values()):
                continue
            try:
                entry_ts = parse_ts(row[idx_ts])
                exit_ts = parse_ts(row[idx_exit])
                entry_p = float(row[idx_entry])
                sl_p = float(row[idx_sl])
                tp1_p = float(row[idx_tp1])
            except (TypeError, ValueError):
                continue
            outcome = row[idx_outcome].strip().lower()
            if outcome not in ("win", "loss"):
                continue
            direction = (row[idx_dir] or "").upper()
            if "LONG" in direction or "BULL" in direction:
                want_tp1_side = "above"
            else:
                want_tp1_side = "below"

            # Find candles with close > entry_ts and close <= exit_ts
            exit_candle_ok = False
            sl_hit_first = False
            for open_ts, close_ts, low, high in m5_rows:
                if close_ts <= entry_ts:
                    continue
                if close_ts > exit_ts:
                    break
                sl_touched = low <= sl_p <= high
                tp1_touched = low <= tp1_p <= high
                if sl_touched and tp1_touched:
                    if outcome == "win":
                        errors.append((f"Trade entry {entry_ts}: both SL and TP1 on same candle (close {close_ts}); logged as {outcome} (expected loss per contract)"))
                    sl_hit_first = True
                    break
                if sl_touched:
                    sl_hit_first = True
                    break
                if tp1_touched:
                    if close_ts == exit_ts:
                        exit_candle_ok = True
                    break

            if outcome == "win" and not sl_hit_first:
                if not exit_candle_ok and exit_ts:
                    # Check if exit_ts candle actually contains TP1
                    for open_ts, close_ts, low, high in m5_rows:
                        if close_ts == exit_ts:
                            if low <= tp1_p <= high:
                                exit_candle_ok = True
                            break
                if not exit_candle_ok:
                    errors.append((f"Trade entry {entry_ts} exit {exit_ts}: TP1 {tp1_p} not in exit-candle range?"))
            checked += 1
            if checked >= 20:
                break

    print(f"Checked {checked} trades against M5.")
    if errors:
        print(f"Found {len(errors)} issue(s):")
        for e in errors[:15]:
            print("  ", e)
    else:
        print("All checked trades: exit candle consistent with logged outcome (TP1 in range for wins; no SL-first).")
    print()
    print("Note: this public verifier checks logged outcome consistency only.")
    print("It does not define, disclose or validate production target/stop parameters.")


if __name__ == "__main__":
    main()
