"""
Pull closed-bar OHLC from MetaTrader 5 into pandas DataFrames matching ``xau_engine.io_csv`` shape:

  columns: time (UTC), open, high, low, close

Also: turn MT5 ticks into either **per-tick** rows (fast path for intrabar, no 1s bucketting)
or optional 1-second aggregates (legacy helper).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

import numpy as np
import pandas as pd

try:
    import MetaTrader5 as mt5  # type: ignore[import]
except ImportError:  # pragma: no cover
    mt5 = None


def _require_mt5() -> None:
    if mt5 is None:
        raise RuntimeError("MetaTrader5 package not installed")


def rates_to_ohlc_df(rates: Any) -> pd.DataFrame:
    """Convert MT5 ``copy_rates*`` numpy structured array to normalized OHLC DataFrame."""
    if rates is None or len(rates) == 0:
        return pd.DataFrame(columns=["time", "open", "high", "low", "close"])
    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
    for c in ("open", "high", "low", "close"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["time", "open", "high", "low", "close"])
    return df.sort_values("time").drop_duplicates("time").reset_index(drop=True)


def copy_rates_from_pos(
    symbol: str,
    timeframe: int,
    count: int,
    *,
    start_pos: int = 0,
) -> pd.DataFrame:
    """
    Last ``count`` bars ending at the current (possibly forming) bar from position ``start_pos``.
    ``timeframe``: e.g. ``mt5.TIMEFRAME_H1``, ``mt5.TIMEFRAME_M15``.
    """
    _require_mt5()
    rates = mt5.copy_rates_from_pos(symbol, timeframe, start_pos, count)
    if rates is None:
        code, msg = mt5.last_error()
        raise RuntimeError(f"copy_rates_from_pos failed: {code} {msg}")
    return rates_to_ohlc_df(rates)


def copy_rates_range(
    symbol: str,
    timeframe: int,
    date_from: datetime,
    date_to: datetime,
) -> pd.DataFrame:
    """Closed bars in [date_from, date_to] (MT5 API semantics)."""
    _require_mt5()
    if date_from.tzinfo is None:
        date_from = date_from.replace(tzinfo=timezone.utc)
    if date_to.tzinfo is None:
        date_to = date_to.replace(tzinfo=timezone.utc)
    rates = mt5.copy_rates_range(symbol, timeframe, date_from, date_to)
    if rates is None:
        code, msg = mt5.last_error()
        raise RuntimeError(f"copy_rates_range failed: {code} {msg}")
    return rates_to_ohlc_df(rates)


def _ticks_table_to_mid_df(tdf: pd.DataFrame) -> pd.DataFrame:
    """Build mid price series from MT5 tick table."""
    if tdf.empty:
        return pd.DataFrame(columns=["t_ns", "mid"])
    if "time_msc" in tdf.columns and tdf["time_msc"].notna().any():
        ts = pd.to_datetime(tdf["time_msc"], unit="ms", utc=True)
    else:
        ts = pd.to_datetime(tdf["time"], unit="s", utc=True)
    bid = pd.to_numeric(tdf.get("bid"), errors="coerce")
    ask = pd.to_numeric(tdf.get("ask"), errors="coerce")
    mid = (bid + ask) / 2.0
    last_ = pd.to_numeric(tdf.get("last"), errors="coerce")
    mid = mid.fillna(last_)
    out = pd.DataFrame({"t_ns": ts, "mid": mid})
    return out.dropna(subset=["mid"])


def ticks_to_mid_series(ticks: Any) -> pd.DataFrame:
    """Ticks numpy structured array or DataFrame -> columns: t_ns, mid."""
    if ticks is None:
        return pd.DataFrame(columns=["t_ns", "mid"])
    tdf = ticks if isinstance(ticks, pd.DataFrame) else pd.DataFrame(ticks)
    if tdf.empty:
        return pd.DataFrame(columns=["t_ns", "mid"])
    return _ticks_table_to_mid_df(tdf)


def ticks_to_intrabar_s1_df(ticks: Any) -> pd.DataFrame:
    """
    One **tick** per row (no 1-second resampling): feeds ``run_m15_backtest`` intrabar path
    with true tick sequence. ``high``/``low`` span bid–ask when available (entry/touch checks);
    timestamps are made unique at sub-ms so ``drop_duplicates(time)`` is not required.

    Columns: ``time``, ``open``, ``high``, ``low``, ``close`` (same schema as CSV S1).
    """
    if ticks is None:
        return pd.DataFrame(columns=["time", "open", "high", "low", "close"])
    tdf = ticks if isinstance(ticks, pd.DataFrame) else pd.DataFrame(ticks)
    if tdf.empty:
        return pd.DataFrame(columns=["time", "open", "high", "low", "close"])
    n = len(tdf)
    if "time_msc" in tdf.columns and tdf["time_msc"].notna().any():
        msc = pd.to_numeric(tdf["time_msc"], errors="coerce").fillna(0).to_numpy(dtype=np.int64)
    else:
        sec = pd.to_numeric(tdf["time"], errors="coerce").fillna(0).to_numpy(dtype=np.int64)
        msc = sec * np.int64(1000)
    ord_idx = np.arange(n, dtype=np.int64)
    ns_raw = msc * np.int64(1_000_000) + (ord_idx % np.int64(1_000_000))
    ts = pd.to_datetime(ns_raw, unit="ns", utc=True)

    bid = pd.to_numeric(tdf.get("bid"), errors="coerce")
    ask = pd.to_numeric(tdf.get("ask"), errors="coerce")
    last_ = pd.to_numeric(tdf.get("last"), errors="coerce")
    mid = (bid + ask) / 2.0
    mid = mid.fillna(last_)
    low = bid.fillna(mid)
    high = ask.fillna(mid)
    out = pd.DataFrame(
        {
            "time": ts,
            "open": mid,
            "high": high,
            "low": low,
            "close": mid,
        }
    )
    out = out.dropna(subset=["time", "high", "low"])
    return out.sort_values("time").reset_index(drop=True)


def ticks_to_1s_ohlc(ticks: Any) -> pd.DataFrame:
    """
    Aggregate ticks to 1-second bars (high/low of mid; mid = (bid+ask)/2 or last).

    Output matches S1-style use in ``m15_backtest``: columns ``time``, ``high``, ``low``
    (and ``open``, ``close`` for debugging; engine uses high/low paths).
    """
    ms = ticks_to_mid_series(ticks)
    if ms.empty:
        return pd.DataFrame(columns=["time", "open", "high", "low", "close"])
    ms["sec"] = ms["t_ns"].dt.floor("1s")
    g = ms.groupby("sec", sort=True)["mid"]
    ohlc = g.agg(["first", "max", "min", "last"]).reset_index()
    ohlc.columns = ["time", "open", "high", "low", "close"]
    return ohlc


def copy_ticks_range_utc(
    symbol: str,
    utc_from: datetime,
    utc_to: datetime,
    *,
    flags: Optional[int] = None,
) -> pd.DataFrame:
    """``copy_ticks_range`` as a DataFrame (``ticks_to_intrabar_s1_df`` / ``ticks_to_1s_ohlc``)."""
    _require_mt5()
    if flags is None:
        flags = mt5.COPY_TICKS_ALL
    if utc_from.tzinfo is None:
        utc_from = utc_from.replace(tzinfo=timezone.utc)
    if utc_to.tzinfo is None:
        utc_to = utc_to.replace(tzinfo=timezone.utc)
    ticks = mt5.copy_ticks_range(symbol, utc_from, utc_to, flags)
    if ticks is None:
        code, msg = mt5.last_error()
        raise RuntimeError(f"copy_ticks_range failed: {code} {msg}")
    return pd.DataFrame(ticks)


def recent_1s_from_ticks(
    symbol: str,
    utc_from: datetime,
    utc_to: datetime,
) -> pd.DataFrame:
    """Convenience: tick range -> 1s OHLC (UTC)."""
    ticks = copy_ticks_range_utc(symbol, utc_from, utc_to)
    return ticks_to_1s_ohlc(ticks)
