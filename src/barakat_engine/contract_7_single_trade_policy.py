"""
Contract 7: SingleTradePolicy — V1 Policy (single active trade at a time).

Authority: Contracts/CONTRACT_7_SingleTradePolicy_SECTION_B__PATCHED_S2 DONE.txt

Enforces phase2_scanning_allowed = (open_trade_count < max_open_positions). Evaluated at the START
of each candle-close engine step (by ExecutionStateMachine) before Phase 2 logic.
When at capacity (open_trade_count >= max_open_positions), Phase 2 modules MUST NOT run.
Passive state aging carve-outs are only those explicitly permitted by authority.
"""

from __future__ import annotations

from typing import Any

from barakat_engine.guardrails import gr_fail, require_inputs

CONTRACT = "CONTRACT_7"
EDGE_6_TO_7 = "6→7"
SECTION_B3 = "B3"
SECTION_B4 = "B4"
SECTION_B6 = "B6"
SECTION_B9 = "B9"

REQUIRED_EXECUTION_POLICY_PROVIDER = "single_trade"


def evaluate_single_trade_policy(
    execution_policy_provider: str,
    open_trade_count: int,
    max_open_positions: int,
    *,
    idx: int | None = None,
    time: Any = None,
) -> bool:
    """
    Evaluate SingleTradePolicy per Contract 7 B3/B4/B6.

    Inputs (B3):
      execution_policy_provider: MUST equal "single_trade" (fatal otherwise).
      open_trade_count: number of currently open trades.
      max_open_positions: config cap (e.g. 1 or 2).

    Output (B4):
      phase2_scanning_allowed: True iff Phase 2 scanning may execute this step; False if at capacity.

    Policy mapping (B6): phase2_scanning_allowed = (open_trade_count < max_open_positions).
    """
    require_inputs(
        execution_policy_provider is not None,
        CONTRACT,
        SECTION_B3,
        EDGE_6_TO_7,
        "execution_policy_provider is required",
        idx=idx,
        time=time,
    )
    require_inputs(
        execution_policy_provider == REQUIRED_EXECUTION_POLICY_PROVIDER,
        CONTRACT,
        SECTION_B6,
        EDGE_6_TO_7,
        f"execution_policy_provider MUST equal {REQUIRED_EXECUTION_POLICY_PROVIDER!r}; got {execution_policy_provider!r}",
        idx=idx,
        time=time,
    )
    require_inputs(
        isinstance(open_trade_count, int) and open_trade_count >= 0,
        CONTRACT,
        SECTION_B9,
        EDGE_6_TO_7,
        "open_trade_count must be non-negative integer",
        idx=idx,
        time=time,
    )
    require_inputs(
        isinstance(max_open_positions, int) and max_open_positions >= 1,
        CONTRACT,
        SECTION_B9,
        EDGE_6_TO_7,
        "max_open_positions must be positive integer",
        idx=idx,
        time=time,
    )
    return open_trade_count < max_open_positions


class SingleTradePolicy:
    """
    SingleTradePolicy spoke: evaluated at START of each candle-close step by ExecutionStateMachine.
    on_candle_close(ctx) returns phase2_scanning_allowed so ESM can gate Phase 2 modules.
    """

    def on_candle_close(self, ctx: Any) -> bool:
        """
        Evaluate policy for this step. Contract 7 B5: at START of candle-close step, prior to Phase 2.
        Returns phase2_scanning_allowed (True iff Phase 2 may run).
        """
        config_snapshot = getattr(ctx, "config_snapshot", None)
        if config_snapshot is None:
            gr_fail(
                CONTRACT,
                SECTION_B3,
                EDGE_6_TO_7,
                "INPUTS",
                "config_snapshot is required on StepContext",
                idx=getattr(ctx, "idx", None),
                time=getattr(ctx, "now_utc", None),
            )
        execution_policy_provider = config_snapshot.get("execution_policy_provider")
        open_trade_count = getattr(ctx, "open_trade_count", 0)
        if not isinstance(open_trade_count, int) or open_trade_count < 0:
            open_trade_count = 0
        max_open_positions = config_snapshot.get("max_open_positions", 1)
        if not isinstance(max_open_positions, int) or max_open_positions < 1:
            max_open_positions = 1
        return evaluate_single_trade_policy(
            execution_policy_provider=execution_policy_provider,
            open_trade_count=open_trade_count,
            max_open_positions=max_open_positions,
            idx=getattr(ctx, "idx", None),
            time=getattr(ctx, "now_utc", None),
        )
