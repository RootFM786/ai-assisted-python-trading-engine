"""
Contract 15 — MandatorySinkLogger (Phase 0).

Create and own the two V1 mandatory sink CSV outputs under the run output directory.
Write-only semantics; locked CSV serialization; hard-fail on write/flush/close or schema failure.

Authority: CONTRACT_15_MandatorySinkLogger_SECTION_B__PATCHED_S2 DONE.txt
Invocation: Constructed by RunHarness at run start; flush/close at termination.
Phase 0: spine run; may emit zero rows. on_candle_close may be no-op unless event present.
"""

from __future__ import annotations

import csv
import os
import time
from datetime import datetime
from typing import Any, Optional, TextIO

from barakat_engine.guardrails import gr_fail, require_callable, require_inputs, require_outputs


def _determine_session(utc_hour: int) -> str:
    """Map UTC hour to session name per Contract 15 B6."""
    if 0 <= utc_hour < 7:
        return "Asia"
    if 7 <= utc_hour < 13:
        return "London"
    if 13 <= utc_hour < 18:
        return "NY"
    return "Late NY"


def _fmt_ts(dt: Optional[datetime]) -> str:
    """Format datetime to millisecond-precision ISO string with Z suffix."""
    if dt is None:
        return ""
    if dt.tzinfo is not None:
        return dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    return dt.isoformat()


def _fmt_price(v: Optional[float]) -> str:
    if v is None:
        return ""
    return f"{v:.6f}"

CONTRACT = "CONTRACT_15"
EDGE = "0→15"

# B6 locked headers (exact strings, in order)
EXECUTED_TRADE_LOG_HEADER = [
    "Run UUID",
    "Trade #",
    "Entry candle timestamp (DERIVED M5 close time, UTC)",
    "Session (Asia / London / NY / Late NY)",
    "Trade type",
    "Direction",
    "Entry price",
    "Stop loss",
    "TP1",
    "TP2 (blank unless used)",
    "RR (entry → TP1)",
    "Risk (R)",
    "MAE (points)",
    "MFE (points)",
    "TP1 hit (yes/no)",
    "TP1 result (points)",
    "TP2 hit (yes/no)",
    "TP2 result (points)",
    "Final outcome (win / loss)",
    "Notes (must include: brief trade progression, brief session/market conditions, estimated trade duration)",
    "Upstream signal timestamp",
    "Candidate creation timestamp",
    "Exit timestamp",
    "Candidate lifecycle marker",
]

BLOCKED_CANDIDATES_LOG_HEADER = [
    "Run UUID",
    "Timestamp",
    "Reason code",
]

VALID_EXECUTION_MODES = frozenset({"backtest", "replay", "demo", "live"})


def _norm_path_for_contract(p: str) -> str:
    """Normalize path for contract equality: forward slashes, no trailing slash except for dirs."""
    return os.path.normpath(p).replace("\\", "/").rstrip("/")


def _ensure_dir(path: str) -> None:
    """Create directory if it does not exist. Hard-fail on failure."""
    try:
        os.makedirs(path, exist_ok=True)
    except OSError as e:
        gr_fail(
            CONTRACT,
            "B9",
            EDGE,
            "OUTPUTS",
            f"mandatory sink run_output_dir creation failed: {e}",
        )


def _open_sink(path: str, header: list[str]) -> TextIO:
    """Create CSV file with locked header. UTF-8, LF. Hard-fail on write failure."""
    try:
        f = open(path, "w", encoding="utf-8", newline="")
    except OSError as e:
        gr_fail(
            CONTRACT,
            "B9",
            EDGE,
            "OUTPUTS",
            f"mandatory sink file open failed: {path!r} — {e}",
        )
    writer = csv.writer(f, lineterminator="\n", quoting=csv.QUOTE_MINIMAL)
    try:
        writer.writerow(header)
        f.flush()
    except (OSError, csv.Error) as e:
        try:
            f.close()
        except OSError:
            pass
        gr_fail(
            CONTRACT,
            "B9",
            EDGE,
            "OUTPUTS",
            f"mandatory sink header write failed: {path!r} — {e}",
        )
    return f


class MandatorySinkLogger:
    """
    Mandatory sink logger: executed_trade_log.csv and blocked_candidates_log.csv.
    Write-only; locked headers and serialization; hard-fail on any write/flush/close failure.
    """

    def __init__(
        self,
        run_id: str,
        run_uuid: str,
        run_output_root: str,
        run_output_dir: str,
        execution_mode: str,
    ) -> None:
        """
        Run-level construction. Creates run_output_dir and both mandatory sink files
        with locked headers. Phase 0 may leave files with header-only (zero data rows).
        """
        # INPUTS (B3)
        require_inputs(
            isinstance(run_id, str) and len(run_id) > 0,
            CONTRACT,
            "B3",
            EDGE,
            "run_id must be non-empty string",
        )
        require_inputs(
            isinstance(run_uuid, str) and len(run_uuid) > 0,
            CONTRACT,
            "B3",
            EDGE,
            "run_uuid must be non-empty string (required for per-row Run UUID)",
        )
        require_inputs(
            run_id == run_uuid,
            CONTRACT,
            "B3",
            EDGE,
            "run_id and run_uuid must be the same value",
        )
        expected_dir = _norm_path_for_contract(run_output_root) + "/" + run_id + "/"
        actual_dir = _norm_path_for_contract(run_output_dir)
        if not actual_dir.endswith("/"):
            actual_dir = actual_dir + "/"
        require_inputs(
            actual_dir == expected_dir,
            CONTRACT,
            "B3",
            EDGE,
            f"run_output_dir MUST equal run_output_root + '/' + run_id + '/'; got run_output_dir={run_output_dir!r}",
        )
        require_inputs(
            execution_mode in VALID_EXECUTION_MODES,
            CONTRACT,
            "B3",
            EDGE,
            f"execution_mode must be one of {sorted(VALID_EXECUTION_MODES)}, got {execution_mode!r}",
        )

        self._run_id = run_id
        self._run_uuid = run_uuid
        self._run_output_dir = run_output_dir
        self._execution_mode = execution_mode
        self._closed = False

        _ensure_dir(run_output_dir)

        executed_path = os.path.join(run_output_dir, "executed_trade_log.csv")
        blocked_path = os.path.join(run_output_dir, "blocked_candidates_log.csv")

        self._executed_file = _open_sink(executed_path, EXECUTED_TRADE_LOG_HEADER)
        self._blocked_file = _open_sink(blocked_path, BLOCKED_CANDIDATES_LOG_HEADER)
        self._executed_writer = csv.writer(
            self._executed_file, lineterminator="\n", quoting=csv.QUOTE_MINIMAL
        )
        self._blocked_writer = csv.writer(
            self._blocked_file, lineterminator="\n", quoting=csv.QUOTE_MINIMAL
        )

    def on_candle_close(self, ctx: Any) -> None:
        """
        Per-candle hook required by hub. Phase 0 may be no-op unless an event is explicitly present.
        """
        require_callable(
            not self._closed,
            CONTRACT,
            "B4",
            EDGE,
            "on_candle_close called after close()",
        )

    def log_blocked_candidate(
        self,
        timestamp_utc: datetime,
        reason_code: str,
    ) -> None:
        """Append one row to blocked_candidates_log.csv (B6 schema)."""
        require_callable(
            not self._closed,
            CONTRACT, "B4", EDGE,
            "log_blocked_candidate called after close()",
        )
        try:
            self._blocked_writer.writerow([
                self._run_uuid,
                _fmt_ts(timestamp_utc),
                reason_code,
            ])
            self._blocked_file.flush()
        except (OSError, csv.Error) as e:
            gr_fail(CONTRACT, "B9", EDGE, "OUTPUTS",
                    f"blocked_candidates_log.csv write failed: {e}")

    def log_executed_trade(
        self,
        *,
        trade_number: int,
        entry_timestamp: Optional[datetime],
        direction: Optional[str],
        entry_price: Optional[float],
        stop_loss: Optional[float],
        tp1: Optional[float],
        rr_to_tp1: Optional[float],
        mae_points: float,
        mfe_points: float,
        exit_reason: Optional[str],
        exit_timestamp: Optional[datetime],
        exit_price: Optional[float],
        realized_r: Optional[float],
        tp1_result_points: Optional[float],
        displacement_ts: Optional[datetime] = None,
        fvg_ts: Optional[datetime] = None,
        sniper_offset: Optional[int] = None,
        risk_r: Optional[float] = None,
    ) -> None:
        """Append one row to executed_trade_log.csv (B6 locked schema)."""
        require_callable(
            not self._closed,
            CONTRACT, "B4", EDGE,
            "log_executed_trade called after close()",
        )
        session = _determine_session(entry_timestamp.hour) if entry_timestamp else ""
        dir_label = "LONG" if direction == "BULL" else ("SHORT" if direction == "BEAR" else (direction or ""))
        tp1_hit = "yes" if exit_reason == "TP1_HIT" else "no"
        final_outcome = "win" if exit_reason == "TP1_HIT" else "loss"

        duration_str = ""
        if entry_timestamp and exit_timestamp:
            delta = exit_timestamp - entry_timestamp
            mins = int(delta.total_seconds() // 60)
            duration_str = f"~{mins}m"

        notes = (
            f"{dir_label} entry at {_fmt_price(entry_price)} ({session} session). "
            f"{exit_reason or 'N/A'} at {_fmt_price(exit_price)}. Duration {duration_str}."
        )

        row = [
            self._run_uuid,
            trade_number,
            _fmt_ts(entry_timestamp),
            session,
            "Strategy decision (criteria withheld)",
            dir_label,
            _fmt_price(entry_price),
            _fmt_price(stop_loss),
            _fmt_price(tp1),
            "",                                         # TP2 (blank)
            f"{rr_to_tp1:.4f}" if rr_to_tp1 is not None else "",
            f"{(risk_r if risk_r is not None else 1.0):.4f}",  # Risk (R)
            f"{mae_points:.6f}",
            f"{mfe_points:.6f}",
            tp1_hit,
            f"{tp1_result_points:.6f}" if tp1_result_points is not None else "0.000000",
            "no",                                       # TP2 hit
            "",                                         # TP2 result
            final_outcome,
            notes,
            _fmt_ts(displacement_ts),
            _fmt_ts(fvg_ts),
            _fmt_ts(exit_timestamp),
            str(sniper_offset) if sniper_offset is not None else "",
        ]
        try:
            self._executed_writer.writerow(row)
            self._executed_file.flush()
        except (OSError, csv.Error) as e:
            gr_fail(CONTRACT, "B9", EDGE, "OUTPUTS",
                    f"executed_trade_log.csv write failed: {e}")

    def flush(self) -> None:
        """Flush both mandatory sink files. Hard-fail on failure."""
        require_callable(
            not self._closed,
            CONTRACT,
            "B4",
            EDGE,
            "flush() called after close()",
        )
        try:
            self._executed_file.flush()
        except OSError as e:
            gr_fail(
                CONTRACT,
                "B9",
                EDGE,
                "OUTPUTS",
                f"executed_trade_log.csv flush failed: {e}",
            )
        try:
            self._blocked_file.flush()
        except OSError as e:
            gr_fail(
                CONTRACT,
                "B9",
                EDGE,
                "OUTPUTS",
                f"blocked_candidates_log.csv flush failed: {e}",
            )

    def close(self) -> None:
        """Flush and close both mandatory sink files. Hard-fail on failure."""
        if self._closed:
            return
        self.flush()
        try:
            self._executed_file.close()
        except OSError as e:
            gr_fail(
                CONTRACT,
                "B9",
                EDGE,
                "OUTPUTS",
                f"executed_trade_log.csv close failed: {e}",
            )
        try:
            self._blocked_file.close()
        except OSError as e:
            gr_fail(
                CONTRACT,
                "B9",
                EDGE,
                "OUTPUTS",
                f"blocked_candidates_log.csv close failed: {e}",
            )
        self._closed = True

    @property
    def run_output_dir(self) -> str:
        return self._run_output_dir


def peek_mandatory_sinks(run_output_root: str = "runs/_selftest") -> dict:
    """
    Phase 0 helper (manual test; not used by engine).
    Create a new run folder under run_output_root, construct MandatorySinkLogger to create
    executed_trade_log.csv and blocked_candidates_log.csv with locked headers, then read
    only the first line (header) of each file and return:
      executed_trade_log_header, blocked_candidates_log_header, run_output_dir.
    HARD FAIL if either file is missing, either header line is empty, or flush/close fails.
    """
    run_id = "SELFTEST_" + str(int(time.time() * 1000))
    run_output_root_norm = _norm_path_for_contract(run_output_root)
    run_output_dir_norm = run_output_root_norm + "/" + run_id + "/"

    logger = MandatorySinkLogger(
        run_id=run_id,
        run_uuid=run_id,
        run_output_root=run_output_root_norm,
        run_output_dir=run_output_dir_norm,
        execution_mode="backtest",
    )
    logger.flush()
    logger.close()

    executed_path = os.path.join(run_output_dir_norm, "executed_trade_log.csv")
    blocked_path = os.path.join(run_output_dir_norm, "blocked_candidates_log.csv")

    require_outputs(
        os.path.isfile(executed_path),
        CONTRACT,
        "B4",
        EDGE,
        f"executed_trade_log.csv missing after construction: {executed_path!r}",
    )
    require_outputs(
        os.path.isfile(blocked_path),
        CONTRACT,
        "B4",
        EDGE,
        f"blocked_candidates_log.csv missing after construction: {blocked_path!r}",
    )

    try:
        with open(executed_path, "r", encoding="utf-8") as f:
            executed_line = f.readline()
        with open(blocked_path, "r", encoding="utf-8") as f:
            blocked_line = f.readline()
    except OSError as e:
        gr_fail(
            CONTRACT,
            "B9",
            EDGE,
            "OUTPUTS",
            f"peek_mandatory_sinks: read header failed: {e}",
        )

    executed_header = executed_line.rstrip("\n\r") if executed_line else ""
    blocked_header = blocked_line.rstrip("\n\r") if blocked_line else ""

    require_outputs(
        len(executed_header) > 0,
        CONTRACT,
        "B6",
        EDGE,
        "executed_trade_log.csv header line is empty",
    )
    require_outputs(
        len(blocked_header) > 0,
        CONTRACT,
        "B6",
        EDGE,
        "blocked_candidates_log.csv header line is empty",
    )

    return {
        "executed_trade_log_header": executed_header,
        "blocked_candidates_log_header": blocked_header,
        "run_output_dir": run_output_dir_norm,
    }
