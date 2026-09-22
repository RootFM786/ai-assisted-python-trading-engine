"""Bounded MetaTrader 5 connectivity and account-query adapter.

This is genuine integration code for terminal initialisation, symbol metadata,
account snapshots, position queries and historical deal aggregation. Production
credentials, terminal paths, broker identifiers and order submission are
intentionally excluded from the public project.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional, Tuple

try:
    import MetaTrader5 as mt5  # type: ignore[import]
except ImportError:  # pragma: no cover
    mt5 = None


def initialize_existing_terminal() -> Tuple[bool, str]:
    """Connect only to an already authenticated local MT5 terminal."""
    if mt5 is None:
        return False, "MetaTrader5 package is not installed"
    if mt5.initialize():
        return True, "connected to existing terminal session"
    code, message = mt5.last_error()
    return False, f"initialise failed: {code} {message}"


def get_symbol_sizing_info(symbol: str) -> Optional[dict[str, float]]:
    """Read broker-provided instrument metadata; does not place an order."""
    if mt5 is None:
        return None
    info = mt5.symbol_info(symbol)
    if info is None:
        return None
    try:
        point = float(info.point)
        tick_value = float(info.trade_tick_value)
        tick_size = float(info.trade_tick_size or point)
        return {
            "point": point,
            "value_per_point_per_lot": tick_value * (point / tick_size),
            "volume_min": float(info.volume_min),
            "volume_max": float(info.volume_max),
            "volume_step": float(info.volume_step),
        }
    except (AttributeError, TypeError, ValueError, ZeroDivisionError):
        return None


def ensure_symbol_visible(symbol: str) -> bool:
    if mt5 is None:
        return False
    info = mt5.symbol_info(symbol)
    return bool(info and (info.visible or mt5.symbol_select(symbol, True)))


def account_snapshot() -> Optional[Tuple[float, str]]:
    """Return balance and account currency for local diagnostics only."""
    if mt5 is None:
        return None
    info = mt5.account_info()
    if info is None:
        return None
    try:
        return float(info.balance), str(info.currency).strip()
    except (AttributeError, TypeError, ValueError):
        return None


def count_open_positions(symbol: str) -> int:
    if mt5 is None:
        return 0
    positions = mt5.positions_get(symbol=symbol)
    return len(positions or ())


def net_realized_pl_account_currency(position_id: int, *, lookback_days: int = 7) -> Optional[float]:
    """Aggregate a closed position's deal P/L from local terminal history."""
    if mt5 is None:
        return None
    end = datetime.now(timezone.utc)
    rows = mt5.history_deals_get(end - timedelta(days=lookback_days), end) or ()
    matching = [row for row in rows if getattr(row, "position_id", None) == position_id]
    if not matching:
        return None
    return sum(float(getattr(row, "profit", 0) or 0) + float(getattr(row, "swap", 0) or 0) + float(getattr(row, "commission", 0) or 0) for row in matching)


def send_order(*_: Any, **__: Any) -> None:
    """Intentionally unavailable: production execution adapter is private."""
    raise NotImplementedError("Live order submission is intentionally withheld from the public repository.")


def shutdown() -> None:
    if mt5 is not None:
        mt5.shutdown()
