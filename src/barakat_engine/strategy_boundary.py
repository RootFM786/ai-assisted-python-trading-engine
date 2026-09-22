"""Public boundary around confidential trading decisions.

Production decision criteria intentionally withheld; surrounding validation,
lifecycle, state ownership and integration code is unchanged.
"""
from __future__ import annotations

from typing import Any, Protocol


class StrategyDecisionProvider(Protocol):
    def on_candle_close(self, context: Any) -> Any: ...


class WithheldDecisionProvider:
    """Safe public provider: records no decision and never opens a position."""
    production_criteria_withheld = True

    def on_candle_close(self, context: Any) -> None:
        return None
