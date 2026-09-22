"""
Contract 6: ExecutionStateMachine — Phase 0 (Shapes ON, Logic OFF).

Authority: Contracts/CONTRACT_6_ExecutionStateMachine_SECTION_B__PATCHED_S2 DONE.txt
Owns execution-state mutation, pointer-based candle-close advancement, and call order
to spoke modules. Evaluation-window gating is enforced deterministically.
"""

from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from barakat_engine.guardrails import (
    gr_fail,
    gr_require,
    require_callable,
    require_cadence,
    require_inputs,
)
from barakat_engine.types import (
    ActiveTrade,
    BiasState,
    ConfigSnapshot,
    EntryModuleResult,
    ExecutionState,
    EngineStepStatus,
    EngineTerminationStatus,
    NormalizedClosedCandle,
    OutcomeUpdate,
)

CONTRACT = "CONTRACT_6"
EDGE_HARNESS_TO_6 = "0→6"
EDGE_6_TO_7 = "6→7"
EDGE_6_TO_8 = "6→8"
EDGE_6_TO_9 = "6→9"
EDGE_6_TO_10 = "6→10"
EDGE_6_TO_11 = "6→11"
EDGE_6_TO_12 = "6→12"
EDGE_6_TO_13 = "6→13"
EDGE_6_TO_14 = "6→14"
EDGE_6_TO_15 = "6→15"
EDGE_6_TO_16 = "6→16"

VALID_TERMINATION_REASONS = frozenset({"EOF", "MANUAL_STOP", "ERROR"})
PUBLIC_RECENT_HISTORY_CAP = 32
PUBLIC_PRIOR_HISTORY_CAP = 64

# Section references for guardrail messages
SECTION_B3 = "B3"
SECTION_B4 = "B4"
SECTION_B5 = "B5"
SECTION_B6 = "B6"
SECTION_B9 = "B9"


@dataclass(frozen=True)
class StepContext:
    """
    StepContext (ctx) — schema binding from Contract 6 B3.
    Read-only for spokes unless their contracts grant mutation rights.
    """
    now_utc: datetime
    current_m5_candle: NormalizedClosedCandle
    htf_bias_state_at_now: BiasState
    m5_recent_closed_candles: tuple
    m5_prior_closed_candles_for_atr: tuple
    config_snapshot: Any
    execution_state_ref: ExecutionState
    trade_is_open: bool
    active_trade: Optional[Any]
    open_trade_count: int  # len(open_trades); used for phase2 gate and entry gate
    # Run-context / pointer (minimal for Phase 0)
    idx: int
    run_id: str
    execution_mode: str
    evaluation_start_timestamp: Optional[datetime]
    evaluation_end_timestamp: Optional[datetime]


def _neutral_bias_state(now_utc: datetime) -> BiasState:
    """Phase 0: neutral BiasState when HTFBiasTimeline not provided or for stub."""
    return BiasState(
        bias="NEUTRAL",
        bias_leg_id="phase0",
        bias_set_at_utc=now_utc,
    )


def _crossed_friday_2200(prev_close_utc: datetime, now_utc: datetime) -> bool:
    """Return True when there is a Friday 22:00 UTC boundary between prev_close_utc and now_utc.
    This detects the first candle fed by the adapter after Friday 22:00 engine time (weekend gap)."""
    days_since_friday = (now_utc.weekday() - 4) % 7
    last_friday = now_utc - timedelta(days=days_since_friday)
    friday_22 = last_friday.replace(hour=22, minute=0, second=0, microsecond=0)
    if friday_22.tzinfo is None and now_utc.tzinfo is not None:
        friday_22 = friday_22.replace(tzinfo=now_utc.tzinfo)
    if friday_22 > now_utc:
        friday_22 -= timedelta(days=7)
    return prev_close_utc <= friday_22 < now_utc


class _NoOpSpoke:
    """Phase 0 stub: no-op on_candle_close for optional spoke modules."""

    def on_candle_close(self, ctx: StepContext) -> bool:
        """When no SingleTradePolicy is wired, allow Phase 2 (Contract 7 not in use)."""
        return True


def _derive_now_utc(candle: NormalizedClosedCandle) -> datetime:
    """
    Derived M5 close timestamp per Contract 6 B3 TimeSemantics.
    If candle.candle_close_time_utc exists: now_utc = candle.candle_close_time_utc
    Else: now_utc = candle.candle_open_time_utc + 5 minutes.
    """
    if candle.candle_close_time_utc is not None:
        return candle.candle_close_time_utc
    five_min = timedelta(minutes=5)
    now = candle.candle_open_time_utc + five_min
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return now


def _build_step_context(
    candle: NormalizedClosedCandle,
    now_utc: datetime,
    idx: int,
    run_id: str,
    execution_mode: str,
    evaluation_start_timestamp: Optional[datetime],
    evaluation_end_timestamp: Optional[datetime],
    execution_state: ExecutionState,
    config_snapshot: Optional[ConfigSnapshot],
    htf_bias_state: BiasState,
    m5_recent_closed_candles: Tuple[NormalizedClosedCandle, ...],
    m5_prior_closed_candles_for_atr: Tuple[NormalizedClosedCandle, ...] = (),
) -> StepContext:
    """Build StepContext per Contract 6 B3 schema. Contract 9: m5_recent_closed_candles min 7. Contract 10: m5_prior_closed_candles_for_atr for ATR(14)."""
    open_trades = getattr(execution_state, "open_trades", None) or []
    open_trade_count = len(open_trades)
    trade_is_open = open_trade_count > 0
    active_trade = open_trades[0] if open_trades else None
    return StepContext(
        now_utc=now_utc,
        current_m5_candle=candle,
        htf_bias_state_at_now=htf_bias_state,
        m5_recent_closed_candles=m5_recent_closed_candles,
        m5_prior_closed_candles_for_atr=m5_prior_closed_candles_for_atr,
        config_snapshot=config_snapshot,
        execution_state_ref=execution_state,
        trade_is_open=trade_is_open,
        active_trade=active_trade,
        open_trade_count=open_trade_count,
        idx=idx,
        run_id=run_id,
        execution_mode=execution_mode,
        evaluation_start_timestamp=evaluation_start_timestamp,
        evaluation_end_timestamp=evaluation_end_timestamp,
    )


class ExecutionStateMachine:
    """
    Contract 6: ExecutionStateMachine.
    Owns shared ExecutionState mutation; calls spoke modules in locked order per candle close.
    Phase 0: Shapes ON, Logic OFF — minimal bookkeeping, no trade-logic mutations.
    """

    def __init__(
        self,
        run_id: str,
        execution_mode: str,
        evaluation_start_timestamp: datetime,
        evaluation_end_timestamp: Optional[datetime],
        *,
        config_snapshot: Optional[ConfigSnapshot] = None,
        htf_bias_timeline: Optional[Any] = None,
        single_trade_policy: Optional[Any] = None,
        htf_bias_provider: Optional[Any] = None,
        structure_module: Optional[Any] = None,
        displacement_module: Optional[Any] = None,
        fvg_module: Optional[Any] = None,
        entry_module: Optional[Any] = None,
        risk_targets_module: Optional[Any] = None,
        outcome_simulator: Optional[Any] = None,
        mandatory_sink_logger: Optional[Any] = None,
        diagnostic_sink_logger: Optional[Any] = None,
    ) -> None:
        gr_require(
            bool(run_id),
            CONTRACT,
            SECTION_B3,
            EDGE_HARNESS_TO_6,
            "INPUTS",
            "run_id must be non-empty",
        )  # EDGE 0→6: construction inputs
        self._run_id: str = run_id
        self._execution_mode: str = execution_mode
        self._evaluation_start_timestamp: datetime = evaluation_start_timestamp
        self._evaluation_end_timestamp: Optional[datetime] = evaluation_end_timestamp
        self._config_snapshot: Optional[ConfigSnapshot] = config_snapshot
        self._htf_bias_timeline: Optional[Any] = htf_bias_timeline

        self._single_trade_policy = single_trade_policy if single_trade_policy is not None else _NoOpSpoke()
        self._htf_bias_provider = htf_bias_provider if htf_bias_provider is not None else _NoOpSpoke()
        self._structure_module = structure_module if structure_module is not None else _NoOpSpoke()
        self._displacement_module = displacement_module if displacement_module is not None else _NoOpSpoke()
        self._fvg_module = fvg_module if fvg_module is not None else _NoOpSpoke()
        self._entry_module = entry_module if entry_module is not None else _NoOpSpoke()
        self._risk_targets_module = risk_targets_module if risk_targets_module is not None else _NoOpSpoke()
        self._outcome_simulator = outcome_simulator if outcome_simulator is not None else _NoOpSpoke()
        self._mandatory_sink_logger = mandatory_sink_logger if mandatory_sink_logger is not None else _NoOpSpoke()
        self._diagnostic_sink_logger = diagnostic_sink_logger if diagnostic_sink_logger is not None else _NoOpSpoke()

        self._execution_state: ExecutionState = ExecutionState()
        self._step_index: int = 0
        self._last_candle_open_time_utc: Optional[datetime] = None
        self._last_close_utc: Optional[datetime] = None
        # Public build retains bounded deterministic history without production qualifiers.
        self._m5_recent_buffer: List[NormalizedClosedCandle] = []
        # Prior closed candles are retained for adapter/state continuity.
        self._m5_prior_buffer: List[NormalizedClosedCandle] = []
        # TEMP_DIAG_REMOVE_AFTER_FIX: DIAG_BIAS_CHECK
        self._diag_bias_total_bias_samples = 0
        self._diag_bias_non_neutral_count = 0
        self._diag_bias_printed_count = 0
        # TEMP_DIAG_REMOVE_AFTER_FIX: DIAG_CTX_BIAS_WIRING
        self._diag_ctx_bias_total_checked = 0
        self._diag_ctx_bias_matched = 0
        self._diag_ctx_bias_differed = 0
        self._diag_ctx_bias_printed = 0

        self._trade_number: int = 0
        self._pending_trade_info: Optional[dict] = None  # kept for any single-trade legacy reads
        self._pending_trade_info_by_id: Dict[str, dict] = {}  # trade_id -> log info for executed_trade log

    def on_candle_close(self, candle: NormalizedClosedCandle) -> EngineStepStatus:
        """
        Process one adapter-provided closed candle. Returns EngineStepStatus.
        Contract 6 B3/B4/B5: time semantics, evaluation gating, call order.
        """
        idx = self._step_index
        now_utc = _derive_now_utc(candle)

        # --- Weekend reset: first candle after Friday 22:00 engine time ---
        if self._last_close_utc is not None and _crossed_friday_2200(self._last_close_utc, now_utc):
            self._execution_state.active_displacement_window = None
            self._execution_state.armed_fvgs.clear()
            self._execution_state.armed_fvg_execution_objects.clear()
            self._execution_state.open_trades.clear()
            self._execution_state.trade_state.trade_is_open = False
            self._execution_state.trade_state.active_trade = None
            self._execution_state.trade_is_open = False
            self._execution_state.active_trade = None
            self._execution_state.phase = None
            self._pending_trade_info_by_id.clear()

        # --- INPUTS guardrails (B3, B9) ---
        require_inputs(
            candle.candle_open_time_utc.tzinfo is not None,
            CONTRACT,
            SECTION_B3,
            EDGE_HARNESS_TO_6,
            "candle_open_time_utc must be UTC tz-aware",
            idx=idx,
            time=now_utc,
        )
        if self._last_candle_open_time_utc is not None:
            require_inputs(
                candle.candle_open_time_utc > self._last_candle_open_time_utc,
                CONTRACT,
                SECTION_B9,
                EDGE_HARNESS_TO_6,
                "candle_open_time_utc must be strictly increasing",
                idx=idx,
                time=now_utc,
            )
        self._last_candle_open_time_utc = candle.candle_open_time_utc

        if getattr(candle, "open_time_utc", None) is not None:
            require_inputs(
                candle.open_time_utc == candle.candle_open_time_utc,
                CONTRACT,
                SECTION_B3,
                EDGE_HARNESS_TO_6,
                "open_time_utc alias must equal candle_open_time_utc",
                idx=idx,
                time=now_utc,
            )

        # Bias state for ctx (Phase 0: from timeline or neutral stub)
        if self._htf_bias_timeline is not None and getattr(self._htf_bias_timeline, "get_bias_at", None):
            try:
                bias_state = self._htf_bias_timeline.get_bias_at(now_utc)
                bs_utc = getattr(bias_state, "bias_set_at_utc", None)
                require_inputs(
                    bs_utc is None or getattr(bs_utc, "tzinfo", None) is not None,
                    CONTRACT,
                    SECTION_B9,
                    EDGE_6_TO_8,
                    "BiasState must not have timezone-naive timestamps",
                    idx=idx,
                    time=now_utc,
                )
                require_inputs(
                    getattr(bias_state, "bias", None) in ("BULL", "BEAR", "NEUTRAL"),
                    CONTRACT,
                    SECTION_B9,
                    EDGE_6_TO_8,
                    "BiasState.bias must be BULL, BEAR, or NEUTRAL",
                    idx=idx,
                    time=now_utc,
                )
            except Exception as e:
                gr_fail(
                    CONTRACT,
                    SECTION_B5,
                    EDGE_6_TO_8,
                    "CALLABLE",
                    f"HTFBiasTimeline.get_bias_at failed: {e}",
                    idx=idx,
                    time=now_utc,
                )
                bias_state = _neutral_bias_state(now_utc)
        else:
            bias_state = _neutral_bias_state(now_utc)

        # TEMP_DIAG_REMOVE_AFTER_FIX: DIAG_BIAS_CHECK
        in_scope = now_utc >= self._evaluation_start_timestamp and (
            self._evaluation_end_timestamp is None or now_utc < self._evaluation_end_timestamp
        )
        if in_scope:
            self._diag_bias_total_bias_samples += 1
            bias_val = getattr(bias_state, "bias", "NEUTRAL")
            if bias_val != "NEUTRAL":
                self._diag_bias_non_neutral_count += 1
            if self._diag_bias_printed_count < 5:
                self._diag_bias_printed_count += 1

        # Maintain bounded chronological history for spoke modules.
        self._m5_recent_buffer.append(candle)
        self._m5_recent_buffer = self._m5_recent_buffer[-PUBLIC_RECENT_HISTORY_CAP:]
        m5_recent_tuple: Tuple[NormalizedClosedCandle, ...] = tuple(self._m5_recent_buffer)
        m5_prior_for_atr: Tuple[NormalizedClosedCandle, ...] = tuple(self._m5_prior_buffer[-PUBLIC_PRIOR_HISTORY_CAP:])

        # TEMP_DIAG_REMOVE_AFTER_FIX: DIAG_CTX_BIAS_WIRING — Wire ESM-computed bias into ctx so Contract 16 (and other spokes) see it; ctx.htf_bias_state_at_now is the same bias_state computed above.
        ctx = _build_step_context(
            candle=candle,
            now_utc=now_utc,
            idx=idx,
            run_id=self._run_id,
            execution_mode=self._execution_mode,
            evaluation_start_timestamp=self._evaluation_start_timestamp,
            evaluation_end_timestamp=self._evaluation_end_timestamp,
            execution_state=self._execution_state,
            config_snapshot=self._config_snapshot,
            htf_bias_state=bias_state,
            m5_recent_closed_candles=m5_recent_tuple,
            m5_prior_closed_candles_for_atr=m5_prior_for_atr,
        )

        # TEMP_DIAG_REMOVE_AFTER_FIX: DIAG_CTX_BIAS_WIRING
        in_scope_ctx = now_utc >= self._evaluation_start_timestamp and (
            self._evaluation_end_timestamp is None or now_utc < self._evaluation_end_timestamp
        )
        if in_scope_ctx:
            self._diag_ctx_bias_total_checked += 1
            computed_bias = getattr(bias_state, "bias", "NEUTRAL")
            ctx_bias = getattr(ctx.htf_bias_state_at_now, "bias", "NEUTRAL")
            if computed_bias == ctx_bias:
                self._diag_ctx_bias_matched += 1
            else:
                self._diag_ctx_bias_differed += 1
            if self._diag_ctx_bias_printed < 10:
                self._diag_ctx_bias_printed += 1

        # Evaluation-start gating (B5): before start, return CONTINUE without mutating Phase-2 state
        if now_utc < self._evaluation_start_timestamp:
            self._call_spokes_in_order(ctx)
            self._m5_prior_buffer.append(candle)
            self._last_