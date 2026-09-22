"""
Contract 5 — DataAdapter (Phase 0, CSV mode).

Provides a deterministic, sequential stream of fully-closed, normalized candle events
from resolved config (adapter_type, csv_paths with M5 and H1). Exposes next_event(),
get_timeframe_stream(timeframe), get_adapter_metadata(), and peek_first_n() for testing.

Authority: CONTRACT_5_DataAdapter_SECTION_B__PATCHED_S2 DONE.txt
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterable, List, Union
from zoneinfo import ZoneInfo

from barakat_engine.guardrails import (
    gr_fail,
    require_callable,
    require_inputs,
    require_outputs,
    require_cadence,
)
from barakat_engine.types import NormalizedClosedCandle

CONTRACT = "CONTRACT_5"
EDGE = "0→5"
REQUIRED_CSV_COLUMNS = frozenset({"time", "open", "high", "low", "close"})
ADAPTER_VERSION = "contract_5_csv_v1"


# --- AdapterEvent (tagged union) ---

@dataclass(frozen=True)
class CandleEvent:
    """CandleEvent: event_type='CANDLE', candle=NormalizedClosedCandle."""
    event_type: str = "CANDLE"
    candle: NormalizedClosedCandle = field(default_factory=lambda: None)
    def __post_init__(self):
        if self.event_type != "CANDLE":
            raise ValueError("event_type must be 'CANDLE'")
        if self.candle is None:
            raise ValueError("candle is required")


@dataclass(frozen=True)
class EOFEvent:
    """EOFEvent: event_type='EOF'."""
    event_type: str = "EOF"
    def __post_init__(self):
        if self.event_type != "EOF":
            raise ValueError("event_type must be 'EOF'")


@dataclass(frozen=True)
class AdapterErrorEvent:
    """AdapterErrorEvent: event_type='ERROR', error_code, error_message. Fatal."""
    event_type: str = "ERROR"
    error_code: str = ""
    error_message: str = ""
    def __post_init__(self):
        if self.event_type != "ERROR":
            raise ValueError("event_type must be 'ERROR'")


AdapterEvent = Union[CandleEvent, EOFEvent, AdapterErrorEvent]


# --- AdapterMetadata ---

@dataclass
class AdapterMetadata:
    """Minimum required for RunHarness audit header."""
    adapter_type: str
    adapter_version: str
    historical_expected: bool
    source_range_info: dict  # per-timeframe: earliest_open_time_utc, latest_open_time_utc
    dataset_identity: dict   # resolved CSV path(s) per timeframe (M5, H1)


def _path_or_paths_to_list(path_or_paths: Any) -> List[str]:
    """Normalize PathOrPaths (str or list of str) to list of paths."""
    if isinstance(path_or_paths, str):
        return [path_or_paths]
    if isinstance(path_or_paths, list):
        for i, p in enumerate(path_or_paths):
            if not isinstance(p, str):
                gr_fail(
                    CONTRACT, "B3", EDGE, "INPUTS",
                    f"csv_paths entry must be string; got {type(p).__name__}",
                    idx=i,
                )
        return list(path_or_paths)
    gr_fail(
        CONTRACT, "B3", EDGE, "INPUTS",
        f"PathOrPaths must be str or list of str; got {type(path_or_paths).__name__}",
    )
    return []  # unreachable


def _parse_utc_datetime(s: str) -> datetime:
    """Parse ISO timestamp as timezone-aware UTC."""
    s = s.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError as e:
        raise ValueError(f"Invalid datetime {s!r}: {e}") from e
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo("UTC"))
    else:
        dt = dt.astimezone(ZoneInfo("UTC"))
    return dt


def _validate_ohlc(open_: float, high: float, low: float, close: float, *, idx: Any = None, time: Any = None) -> None:
    """OHLC validity: high >= max(open,close), low <= min(open,close), high >= low, no NaN/inf."""
    import math
    for name, val in [("open", open_), ("high", high), ("low", low), ("close", close)]:
        if not isinstance(val, (int, float)) or math.isnan(val) or math.isinf(val):
            gr_fail(
                CONTRACT, "B6", EDGE, "OUTPUTS",
                f"OHLC must be finite numbers; {name}={val!r}",
                idx=idx, time=time,
            )
    if high < max(open_, close) or low > min(open_, close) or high < low:
        gr_fail(
            CONTRACT, "B6", EDGE, "OUTPUTS",
            f"OHLC invalid: high>=max(open,close), low<=min(open,close), high>=low; o={open_!r} h={high!r} l={low!r} c={close!r}",
            idx=idx, time=time,
        )


def _read_csv_candles(
    csv_path: str,
    timeframe_minutes: int,
) -> List[NormalizedClosedCandle]:
    """
    Read one CSV file into list of NormalizedClosedCandle. Strict chronological order, no duplicates.
    Required columns: time (open timestamp UTC), open, high, low, close. Optional: volume.
    """
    path = Path(csv_path)
    require_inputs(
        path.exists(),
        CONTRACT, "B3", EDGE,
        f"CSV file not found: {csv_path}",
    )
    rows: List[dict] = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            gr_fail(CONTRACT, "B3", EDGE, "INPUTS", "CSV has no header row")
        raw_fieldnames = list(reader.fieldnames)
        if "time" not in raw_fieldnames:
            gr_fail(CONTRACT, "B3", EDGE, "INPUTS", "CSV missing required column: time")
        missing_ohlc = {"open", "high", "low", "close"} - set(raw_fieldnames)
        if missing_ohlc:
            gr_fail(
                CONTRACT, "B3", EDGE, "INPUTS",
                f"CSV missing required columns: {sorted(missing_ohlc)}; have {raw_fieldnames}",
            )
        for i, row in enumerate(reader):
            if not row:
                continue
            time_raw = row.get("time")
            if time_raw is None or not str(time_raw).strip():
                gr_fail(CONTRACT, "B3", EDGE, "INPUTS", "Missing time value", idx=i)
            try:
                open_ts = _parse_utc_datetime(str(time_raw))
            except ValueError as e:
                gr_fail(CONTRACT, "B3", EDGE, "INPUTS", str(e), idx=i, time=time_raw)
            try:
                open_ = float(row["open"])
                high = float(row["high"])
                low = float(row["low"])
                close = float(row["close"])
            except (KeyError, TypeError, ValueError) as e:
                gr_fail(CONTRACT, "B3", EDGE, "INPUTS", f"Invalid OHLC: {e}", idx=i, time=time_raw)
            _validate_ohlc(open_, high, low, close, idx=i, time=open_ts)
            vol = None
            if "volume" in row and row["volume"] not in (None, ""):
                try:
                    vol = float(row["volume"])
                except (TypeError, ValueError):
                    pass
            close_ts = open_ts + timedelta(minutes=timeframe_minutes)
            rows.append({
                "candle_open_time_utc": open_ts,
                "open": open_,
                "high": high,
                "low": low,
                "close": close,
                "candle_close_time_utc": close_ts,
                "volume": vol,
            })
    candles = [
        NormalizedClosedCandle(
            candle_open_time_utc=r["candle_open_time_utc"],
            open=r["open"],
            high=r["high"],
            low=r["low"],
            close=r["close"],
            candle_close_time_utc=r["candle_close_time_utc"],
            volume=r["volume"],
        )
        for r in rows
    ]
    # Strict chronological order, no duplicates
    for i in range(1, len(candles)):
        if candles[i].candle_open_time_utc <= candles[i - 1].candle_open_time_utc:
            gr_fail(
                CONTRACT, "B6", EDGE, "OUTPUTS",
                "Candles must be strictly chronological; duplicate or non-monotonic time",
                idx=i,
                time=candles[i].candle_open_time_utc,
            )
    return candles


def _load_timeframe(path_or_paths: Any, timeframe_key: str, timeframe_minutes: int) -> List[NormalizedClosedCandle]:
    """Load one timeframe from PathOrPaths; concatenate if list (deterministic order)."""
    paths = _path_or_paths_to_list(path_or_paths)
    all_candles: List[NormalizedClosedCandle] = []
    for path in paths:
        candles = _read_csv_candles(path, timeframe_minutes)
        if all_candles and candles:
            if candles[0].candle_open_time_utc <= all_candles[-1].candle_open_time_utc:
                gr_fail(
                    CONTRACT, "B3", EDGE, "INPUTS",
                    f"Concatenated CSV overlap/non-monotonic across files for {timeframe_key}",
                    time=candles[0].candle_open_time_utc,
                )
        all_candles.extend(candles)
    return all_candles


def peek_first_n(csv_path: str, n: int) -> List[NormalizedClosedCandle]:
    """
    Phase 0 helper: read and return the first N normalized candles from a single CSV.
    Timeframe is inferred from file (5-min spacing => M5, 60-min => H1); if ambiguous, defaults to M5.
    """
    require_callable(n >= 0, CONTRACT, "B4", EDGE, f"n must be non-negative; got {n}")
    path = Path(csv_path)
    require_inputs(path.exists(), CONTRACT, "B3", EDGE, f"CSV file not found: {csv_path}")
    candles = _read_csv_candles(csv_path, 5)
    if len(candles) >= 2:
        delta = (candles[1].candle_open_time_utc - candles[0].candle_open_time_utc).total_seconds()
        minutes = int(delta // 60)
        if minutes == 60:
            candles = _read_csv_candles(csv_path, 60)
    return candles[:n]


class CSVDataAdapter:
    """
    DataAdapter for Phase 0 CSV mode. Reads adapter_type and csv_paths (M5, H1) from
    resolved config snapshot. next_event() yields M5 stream then EOF; get_timeframe_stream
    supplies M5 and H1 separately (no H1 aggregation from M5).
    """

    def __init__(self, resolved_config_snapshot: dict) -> None:
        require_inputs(
            isinstance(resolved_config_snapshot, dict),
            CONTRACT, "B3", EDGE,
            "resolved_config_snapshot must be a dict",
        )
        adapter_type = resolved_config_snapshot.get("adapter_type")
        if adapter_type == "BROKER":
            gr_fail(
                CONTRACT, "B8", EDGE, "INPUTS",
                "UNDEFINED IN AUTHORITY — BROKER DataAdapter behaviour",
            )
        require_inputs(
            adapter_type == "CSV",
            CONTRACT, "B3", EDGE,
            f"adapter_type must be CSV in Phase 0; got {adapter_type!r}",
        )
        csv_paths = resolved_config_snapshot.get("csv_paths")
        require_inputs(
            isinstance(csv_paths, dict),
            CONTRACT, "B3", EDGE,
            "csv_paths must be present and a dict when adapter_type=CSV",
        )
        require_inputs(
            "M5" in csv_paths,
            CONTRACT, "B3", EDGE,
            "csv_paths must include M5",
        )
        require_inputs(
            "H1" in csv_paths,
            CONTRACT, "B3", EDGE,
            "csv_paths must include H1",
        )
        self._adapter_type = "CSV"
        self._csv_paths = csv_paths
        self._m5: List[NormalizedClosedCandle] = _load_timeframe(csv_paths["M5"], "M5", 5)
        self._h1: List[NormalizedClosedCandle] = _load_timeframe(csv_paths["H1"], "H1", 60)
        self._m5_index = 0
        self._eof_emitted = False

        if not self._m5 and not self._h1:
            gr_fail(CONTRACT, "B4", EDGE, "OUTPUTS", "No candles loaded from csv_paths M5 or H1")
        # Metadata: source_range_info and dataset_identity
        self._source_range_info: dict = {}
        self._dataset_identity: dict = {}
        for key, candles, minutes in [("M5", self._m5, 5), ("H1", self._h1, 60)]:
            path_or_paths = csv_paths.get(key)
            paths = _path_or_paths_to_list(path_or_paths) if path_or_paths else []
            self._dataset_identity[key] = paths
            if candles:
                self._source_range_info[key] = {
                    "earliest_open_time_utc": candles[0].candle_open_time_utc,
                    "latest_open_time_utc": candles[-1].candle_open_time_utc,
                }
            else:
                self._source_range_info[key] = {
                    "earliest_open_time_utc": None,
                    "latest_open_time_utc": None,
                }

        # TEMP_DIAG_REMOVE_AFTER_FIX: DIAG_SCOPE_WINDOW (prints disabled to reduce terminal spam)

    def next_event(self) -> AdapterEvent:
        """
        Sequential event API: CandleEvent for each M5 candle in order, then exactly one EOFEvent.
        After EOF, must not return any further events.
        """
        if self._eof_emitted:
            gr_fail(
                CONTRACT, "B7", EDGE, "CADENCE",
                "Must not return any event after EOFEvent",
                idx=self._m5_index,
            )
        if self._m5_index >= len(self._m5):
            self._eof_emitted = True
            return EOFEvent()
        candle = self._m5[self._m5_index]
        self._m5_index += 1
        return CandleEvent(candle=candle)

    def get_timeframe_stream(self, timeframe: str) -> Iterable[NormalizedClosedCandle]:
        """
        Return iterable of NormalizedClosedCandle for 'M5' or 'H1'.
        H1 is from csv_paths['H1'], not aggregated from M5.
        """
        if timeframe == "M5":
            return list(self._m5)
        if timeframe == "H1":
            return list(self._h1)
        gr_fail(
            CONTRACT, "B4", EDGE, "CALLABLE",
            f"timeframe must be 'M5' or 'H1'; got {timeframe!r}",
        )
        return iter([])  # unreachable

    def get_adapter_metadata(self) -> AdapterMetadata:
        """Deterministic metadata for RunHarness audit header."""
        return AdapterMetadata(
            adapter_type=self._adapter_type,
            adapter_version=ADAPTER_VERSION,
            historical_expected=True,
            source_range_info=self._source_range_info,
            dataset_identity=self._dataset_identity,
        )
