"""
Contract 4 — ExecutionModeController (Phase 0).

Classify execution_mode into finite vs indefinite semantics and expose
mode-tied run-lifetime flags. Pass-through only for evaluation timestamps;
no parsing, normalization, or timezone shift.

Authority: CONTRACT_4_ExecutionModeController_SECTION_B__PATCHED_S2 DONE.txt
Invocation: Once per run as RunHarness orchestration Step 4 (after ConfigResolver,
before LoggerSink and DataAdapter construction).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from barakat_engine.guardrails import require_inputs, require_outputs

CONTRACT = "CONTRACT_4"
EDGE = "0→4"

VALID_MODES = frozenset({"backtest", "replay", "demo", "live"})

# Contract B4: backtest/replay == finite; demo/live == indefinite
FINITE_MODES = frozenset({"backtest", "replay"})
INDEFINITE_MODES = frozenset({"demo", "live"})
# allow_idle_start_no_candle: true ONLY for demo/live
IDLE_START_NO_CANDLE_MODES = frozenset({"demo", "live"})


@dataclass(frozen=True)
class ExecutionModeContext:
    """Locked interface per Contract B4. All fields required; timestamps pass-through."""

    execution_mode: str
    is_finite: bool
    eof_expected: bool
    allow_idle_start_no_candle: bool
    evaluation_start_timestamp: Optional[str]
    evaluation_end_timestamp: Optional[str]


def build_execution_mode_context(
    execution_mode: str,
    evaluation_start_timestamp: Optional[str] = None,
    evaluation_end_timestamp: Optional[str] = None,
) -> ExecutionModeContext:
    """
    Build execution mode context for this run. Invoked once per run (Step 4).

    Inputs (LOCKED):
      execution_mode: one of {backtest, replay, demo, live} — HARD FAIL otherwise.
      evaluation_start_timestamp: optional string, pass-through unchanged.
      evaluation_end_timestamp: optional string, pass-through unchanged.

    Outputs (LOCKED):
      ExecutionModeContext with execution_mode, is_finite, eof_expected,
      allow_idle_start_no_candle, evaluation_start_timestamp, evaluation_end_timestamp.
    """
    # INPUTS: execution_mode must be in allowed set (B3; B9 fatal)
    require_inputs(
        execution_mode in VALID_MODES,
        CONTRACT,
        "B3",
        EDGE,
        f"execution_mode must be one of {sorted(VALID_MODES)}, got {execution_mode!r}",
    )

    is_finite = execution_mode in FINITE_MODES
    eof_expected = execution_mode in FINITE_MODES  # replay == backtest (B6)
    allow_idle_start_no_candle = execution_mode in IDLE_START_NO_CANDLE_MODES

    ctx = ExecutionModeContext(
        execution_mode=execution_mode,
        is_finite=is_finite,
        eof_expected=eof_expected,
        allow_idle_start_no_candle=allow_idle_start_no_candle,
        evaluation_start_timestamp=evaluation_start_timestamp,
        evaluation_end_timestamp=evaluation_end_timestamp,
    )

    # OUTPUTS: required fields present and consistent with mode
    require_outputs(
        ctx.is_finite == is_finite and ctx.eof_expected == eof_expected,
        CONTRACT,
        "B4",
        EDGE,
        "ExecutionModeContext flags must match mode semantics",
    )
    require_outputs(
        ctx.allow_idle_start_no_candle == allow_idle_start_no_candle,
        CONTRACT,
        "B4",
        EDGE,
        "allow_idle_start_no_candle must be true only for demo/live",
    )
    require_outputs(
        ctx.evaluation_start_timestamp is evaluation_start_timestamp,
        CONTRACT,
        "B4",
        EDGE,
        "evaluation_start_timestamp must be pass-through unchanged",
    )
    require_outputs(
        ctx.evaluation_end_timestamp is evaluation_end_timestamp,
        CONTRACT,
        "B4",
        EDGE,
        "evaluation_end_timestamp must be pass-through unchanged",
    )

    return ctx


# --- Phase 0 helper: manual test; not used by engine ---

_EXPECTED_FLAGS = {
    "backtest": {
        "is_finite": True,
        "eof_expected": True,
        "allow_idle_start_no_candle": False,
    },
    "replay": {
        "is_finite": True,
        "eof_expected": True,
        "allow_idle_start_no_candle": False,
    },
    "demo": {
        "is_finite": False,
        "eof_expected": False,
        "allow_idle_start_no_candle": True,
    },
    "live": {
        "is_finite": False,
        "eof_expected": False,
        "allow_idle_start_no_candle": True,
    },
}


def peek_mode_flags() -> dict[str, dict[str, bool]]:
    """
    Phase 0 helper: call build_execution_mode_context for each mode and return
    mode -> {is_finite, eof_expected, allow_idle_start_no_candle}.
    HARD FAIL if any mode produces unexpected flags per Contract 4.
    """
    result: dict[str, dict[str, bool]] = {}
    for mode in sorted(VALID_MODES):
        ctx = build_execution_mode_context(mode, None, None)
        flags = {
            "is_finite": ctx.is_finite,
            "eof_expected": ctx.eof_expected,
            "allow_idle_start_no_candle": ctx.allow_idle_start_no_candle,
        }
        expected = _EXPECTED_FLAGS[mode]
        require_outputs(
            flags == expected,
            CONTRACT,
            "B4",
            EDGE,
            f"mode {mode!r} produced flags {flags!r}, expected {expected!r}",
        )
        result[mode] = flags
    return result
