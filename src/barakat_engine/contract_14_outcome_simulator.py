"""Contract 14 — deterministic outcome-state integration.

The production exit policy, including market-gap and collision policy, is
intentionally withheld. The real interface, no-mutation result contract and
MAE/MFE accounting boundary remain public.
"""
from __future__ import annotations

from typing import Any

from barakat_engine.types import OutcomeUpdate


def _non_negative(value: float) -> float:
    return max(0.0, float(value))


class OutcomeSimulator:
    """Public-safe outcome module; it never resolves a real production trade."""

    production_exit_policy_withheld = True

    def on_candle_close(self, ctx: Any) -> OutcomeUpdate:
        trade = getattr(ctx, "active_trade", None)
        if trade is None:
            return OutcomeUpdate(is_resolved=False, mae_points=0.0, mfe_points=0.0)
        return OutcomeUpdate(
            is_resolved=False,
            mae_points=_non_negative(getattr(trade, "mae_points", 0.0)),
            mfe_points=_non_negative(getattr(trade, "mfe_points", 0.0)),
        )


def evaluate_outcome(current_candle_m5: Any, execution_mode_context: Any, execution_state_ref: Any) -> OutcomeUpdate:
    """Compatibility entry point preserving the Contract 14 call shape."""
    active_trade = getattr(execution_state_ref, "active_trade", None)
    return OutcomeUpdate(
        is_resolved=False,
        mae_points=_non_negative(getattr(active_trade, "mae_points", 0.0)),
        mfe_points=_non_negative(getattr(active_trade, "mfe_points", 0.0)),
    )
