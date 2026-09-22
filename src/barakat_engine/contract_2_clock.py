"""
Contract 2 — Clock & TimeSemantics (Phase 0).

Authority: CONTRACT_2_Clock_TimeSemantics_SECTION_B__PATCHED_S2 DONE.txt

Phase 0 time semantics:
- now_utc is the derived M5 candle close timestamp (UTC) of the current candle.
- Deterministic, candle-derived only (no wall-clock/system time).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from barakat_engine.guardrails import gr_fail, require_inputs, require_outputs

CONTRACT = "CONTRACT_2"
EDGE = "0→2"

UTC = timezone.utc


def _is_utc_aware(ts: Any) -> bool:
    if not isinstance(ts, datetime):
        return False
    if ts.tzinfo is None:
        return False
    try:
        return ts.utcoffset() == timedelta(0)
    except Exception:
        return False


def utc_assert(timestamp: datetime) -> None:
    """
    Enforce timezone-aware UTC datetime.

    Hard-fails immediately on violation.
    """
    require_inputs(
        _is_utc_aware(timestamp),
        CONTRACT,
        "B6",
        EDGE,
        "timestamp must be timezone-aware UTC datetime",
        time=timestamp,
    )


def derive_close_timestamp(timeframe: str, open_timestamp_utc: datetime) -> datetime:
    """
    Mechanical candle open→close derivation.

    - M5 close = open + 5 minutes
    - H1 close = open + 1 hour
    """
    require_inputs(
        timeframe in {"M5", "H1"},
        CONTRACT,
        "B9",
        EDGE,
        f"timeframe must be one of {{'M5','H1'}}; got {timeframe!r}",
        time=open_timestamp_utc,
    )
    utc_assert(open_timestamp_utc)
    if timeframe == "M5":
        close_ts = open_timestamp_utc + timedelta(minutes=5)
    else:
        close_ts = open_timestamp_utc + timedelta(hours=1)
    require_outputs(
        _is_utc_aware(close_ts),
        CONTRACT,
        "B6",
        EDGE,
        "derived close timestamp must be timezone-aware UTC datetime",
        time=close_ts,
    )
    return close_ts


def derive_now_utc_from_m5_candle(candle: Any) -> datetime:
    """
    Phase 0 now_utc semantics (M5 derived close).

    Derivation rule:
    - If candle.candle_close_time_utc exists (non-None): now_utc = candle.candle_close_time_utc
    - Else: now_utc = candle.candle_open_time_utc + 5 minutes
    """
    require_inputs(
        candle is not None and hasattr(candle, "candle_open_time_utc"),
        CONTRACT,
        "B3",
        EDGE,
        "candle must have candle_open_time_utc",
    )
    open_ts = getattr(candle, "candle_open_time_utc", None)
    utc_assert(open_ts)

    close_ts: Optional[datetime] = getattr(candle, "candle_close_time_utc", None)
    if close_ts is not None:
        utc_assert(close_ts)
        expected = open_ts + timedelta(minutes=5)
        require_inputs(
            close_ts == expected,
            CONTRACT,
            "B6",
            EDGE,
            "candle_close_time_utc must equal candle_open_time_utc + 5 minutes when present",
            time=close_ts,
        )
        now_utc = close_ts
    else:
        now_utc = open_ts + timedelta(minutes=5)

    require_outputs(
        _is_utc_aware(now_utc),
        CONTRACT,
        "B6",
        EDGE,
        "now_utc must be timezone-aware UTC datetime",
        time=now_utc,
    )
    return now_utc


def derive_now_utc(candle: Any) -> datetime:
    """Alias for Phase 0 now_utc derivation (M5 close semantics)."""
    return derive_now_utc_from_m5_candle(candle)


@dataclass(frozen=True)
class TimeSemanticsContext:
    """
    Per-run immutable time semantics context.

    Provides UTC enforcement and mechanical close derivation.
    """

    def utc_assert(self, timestamp: datetime) -> None:
        return utc_assert(timestamp)

    def derive_close_timestamp(self, timeframe: str, open_timestamp_utc: datetime) -> datetime:
        return derive_close_timestamp(timeframe, open_timestamp_utc)


def _parse_as_utc_datetime(open_time_utc_str: str) -> datetime:
    s = open_time_utc_str.strip()
    if not s:
        raise ValueError("empty timestamp")
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    else:
        dt = dt.astimezone(UTC)
    return dt


def peek_now_utc_from_open(open_time_utc_str: str) -> str:
    """
    Phase 0 helper (manual test; not used by engine).

    - Parse open_time_utc_str as UTC.
    - Return derived M5 close timestamp as ISO-8601 UTC string ending in 'Z'.
    - HARD FAIL if parsing fails.
    """
    require_inputs(
        isinstance(open_time_utc_str, str),
        CONTRACT,
        "B3",
        EDGE,
        f"open_time_utc_str must be str; got {type(open_time_utc_str).__name__}",
    )
    try:
        open_ts = _parse_as_utc_datetime(open_time_utc_str)
    except Exception as e:
        gr_fail(
            CONTRACT,
            "B9",
            EDGE,
            "INPUTS",
            f"Failed to parse open_time_utc_str as datetime: {e}",
            time=open_time_utc_str,
        )
        raise  # unreachable

    now_utc = open_ts + timedelta(minutes=5)
    utc_assert(open_ts)
    utc_assert(now_utc)

    # Mandatory sink timestamp shape: ISO-8601 UTC with Z, no fractional seconds.
    now_utc = now_utc.astimezone(UTC).replace(microsecond=0)
    return now_utc.isoformat().replace("+00:00", "Z")

