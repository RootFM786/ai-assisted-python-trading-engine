"""
Phase 0 dataclasses for BARAKAT BOT V1.

This module defines the core data structures used throughout Phase 0 (spine + stubs).
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, List, Any
from zoneinfo import ZoneInfo


class EngineStepStatus(Enum):
    """Engine step status (Contract 6 B4/B9)."""
    CONTINUE = "CONTINUE"
    HALT = "HALT"
    ERROR = "ERROR"
    HARD_FAIL_INVALID = "HARD_FAIL_INVALID"


class EngineTerminationStatus(Enum):
    """Engine termination status (Contract 6 B4/B9; Contract 0 run loop)."""
    CLEAN_TERMINATION = "CLEAN_TERMINATION"
    TERMINATED_WITH_ERROR = "TERMINATED_WITH_ERROR"
    TERMINATED_OK = "TERMINATED_OK"
    TERMINATED_INVALID = "TERMINATED_INVALID"


@dataclass(frozen=True)
class BiasState:
    """HTF bias state at a derived close time (Contract 6 / Contract 8). bias in BULL, BEAR, NEUTRAL."""
    bias: str
    bias_leg_id: str
    bias_set_at_utc: datetime


@dataclass
class NormalizedClosedCandle:
    """
    Normalized closed candle with locked schema.
    
    Required fields:
    - candle_open_time_utc: timezone-aware UTC datetime
    - open, high, low, close: float values
    
    Optional fields:
    - candle_close_time_utc: timezone-aware UTC datetime | None
    - volume: float | None
    
    Alias:
    - open_time_utc: alias for candle_open_time_utc (via @property)
    """
    candle_open_time_utc: datetime
    open: float
    high: float
    low: float
    close: float
    candle_close_time_utc: Optional[datetime] = None
    volume: Optional[float] = None
    
    def __post_init__(self):
        """Ensure timezone-aware UTC datetime for candle_open_time_utc."""
        if self.candle_open_time_utc.tzinfo is None:
            self.candle_open_time_utc = self.candle_open_time_utc.replace(tzinfo=ZoneInfo("UTC"))
        if self.candle_close_time_utc is not None and self.candle_close_time_utc.tzinfo is None:
            self.candle_close_time_utc = self.candle_close_time_utc.replace(tzinfo=ZoneInfo("UTC"))
    
    @property
    def open_time_utc(self) -> datetime:
        """Alias for candle_open_time_utc."""
        return self.candle_open_time_utc


@dataclass
class RunIdentity:
    """Run identity information."""
    run_id: str
    run_uuid: str


@dataclass
class ConfigSnapshot:
    """Configuration snapshot (minimum: execution_mode)."""
    execution_mode: str
    # Additional config fields can be added here as needed


# --- Contract 10: Displacement provider & evaluation (B8/B4) ---

@dataclass(frozen=True)
class DisplacementEvent:
    """DisplacementEvent (B8): immutable input to authorize_displacement."""
    m5_candle_open_time_utc: datetime
    m5_derived_close_time_utc: datetime
    direction: str  # BULL | BEAR


@dataclass
class AuthorizationDecision:
    """AuthorizationDecision (B8): provider output."""
    authorized: bool
    reason_code: Optional[str] = None


@dataclass
class DisplacementEvaluationResult:
    """DisplacementEvaluationResult (B4): one per evaluated pointer candle when bias is directional."""
    timestamp_utc: datetime
    bias_state: str
    expected_direction: str
    candle_direction: str  # BULL | BEAR | DOJI
    candle_range: float
    candle_body: float
    atr14: Optional[float]  # None = blank (insufficient history)
    range_to_atr: Optional[float]  # None = blank if atr14 blank
    body_ratio: float
    dominant_opposing_wick: bool
    displacement_result: str  # "valid" | "invalid"
    invalidation_reason: str  # semicolon-separated or ""


# Nested record types for ExecutionState

@dataclass
class ActiveDisplacementWindowRecord:
    """Active displacement window record."""
    authorizing_displacement_open_time_utc: Optional[datetime] = None
    authorizing_displacement_close_time_utc: Optional[datetime] = None
    direction: Optional[str] = None
    total_window_candle_count: int = 0
    window_candles_consumed: int = 0
    window_candles_remaining: int = 0
    authorizing_displacement_high: Optional[float] = None
    authorizing_displacement_low: Optional[float] = None


@dataclass
class ArmedFVGRecord:
    """Armed Fair Value Gap record (Contract 11/12)."""
    formation_close_time_utc: Optional[datetime] = None
    direction: Optional[str] = None
    zone_low: Optional[float] = None
    zone_high: Optional[float] = None
    bound_displacement_close_time_utc: Optional[datetime] = None
    freshness_counter: int = 0
    armed: bool = False
    traded_flag: bool = False
    loss_count: int = 0
    invalidated: bool = False
    invalidation_reason: Optional[str] = None
    win_count: int = 0
    fvg_id: Optional[str] = None
    # Contract 12 B4: Offset-2/3 prerequisite tracking (mutated only by EntryModule)
    offset1_interacted: Optional[bool] = None
    offset1_close_inside: Optional[bool] = None
    offset2_close_inside: Optional[bool] = None


# --- Contract 12: EntryModule handoff types (B4) ---

@dataclass
class EntryToRiskTargetsRequest:
    """EntryToRiskTargetsRequest (LOCKED). Built by EntryModule, consumed by RiskTargetsModule.evaluate."""
    direction: str  # BULL | BEAR
    entry_candle_close_time_utc: datetime
    entry_price: float
    fvg_id: str
    fvg_formation_close_time_utc: datetime
    authorizing_displacement_close_time_utc: datetime
    swing_freeze_cutoff_time_utc: datetime


@dataclass
class RiskTargetsResponse:
    """RiskTargetsResponse (LOCKED). Returned by RiskTargetsModule.evaluate."""
    stop_loss: float
    tp1: float
    rr_to_tp1: float
    is_rr_valid: bool


@dataclass(frozen=True)
class RiskTargetsNoTradeOutcome:
    """NO-TRADE outcome (Contract 13 B9). MUST NOT produce RiskTargetsResponse. reason_code locked."""
    reason_code: str  # e.g. "SL structural anchor unclear"


@dataclass
class EntryModuleResult:
    """
    EntryModuleResult (Contract 12 B4): tagged union.
    Exactly one of: NO_ACTION, BLOCKED_CANDIDATE, ENTRY_EXECUTED.
    """
    status: str  # "NO_ACTION" | "BLOCKED_CANDIDATE" | "ENTRY_EXECUTED"
    # BLOCKED_CANDIDATE
    blocked_at_close_time_utc: Optional[datetime] = None
    reason_code: Optional[str] = None
    fvg_id: Optional[str] = None
    # ENTRY_EXECUTED
    entry_candle_close_time_utc: Optional[datetime] = None
    entry_price: Optional[float] = None
    direction: Optional[str] = None
    stop_loss: Optional[float] = None
    tp1: Optional[float] = None
    rr_to_tp1: Optional[float] = None
    stop_after_entry_same_candle: Optional[bool] = None


@dataclass
class SwingRecord:
    """
    Swing record (Contract 9 canonical schema).
    Primary key: (timeframe, swing_type, swing_open_time_utc). Duplicate keys forbidden.
    """
    timeframe: str = "M5"  # enum ∈ {M5, H1}
    swing_type: Optional[str] = None  # enum ∈ {HIGH, LOW}
    swing_open_time_utc: Optional[datetime] = None
    swing_confirmed_at_utc: Optional[datetime] = None
    price: Optional[float] = None
    candle_index: Optional[int] = None
    leg_id: Optional[str] = None  # stable identifier of active leg at confirmation


@dataclass
class ActiveTrade:
    """Active trade record (Contract 14 B3: minimum required for OutcomeSimulator)."""
    trade_id: Optional[str] = None
    entry_derived_close_timestamp_utc: Optional[datetime] = None
    entry_price: Optional[float] = None
    direction: Optional[str] = None
    stop_loss_price: Optional[float] = None
    tp1_price: Optional[float] = None
    rr_to_tp1: Optional[float] = None
    risk_r: Optional[float] = None
    mae_points: float = 0.0  # Contract 14 B3/B6: non-negative; init 0.0 on trade open
    mfe_points: float = 0.0  # Contract 14 B3/B6: non-negative; init 0.0 on trade open
    has_tp2: bool = False
    broker_fill_snapshot: Optional[Any] = None


class ExitReason:
    """Contract 14 B4: exit_reason enum."""
    TP1_HIT = "TP1_HIT"
    SL_HIT = "SL_HIT"


@dataclass
class OutcomeUpdate:
    """
    Contract 14 B4: outcome result returned to caller. No state mutation; caller applies.
    When is_resolved=True, exit_* and realized_r/tp1_result_points/sl_result_points are set.
    When is_resolved=False, mae_points/mfe_points are updated for the current candle (no hit).
    """
    is_resolved: bool
    mae_points: float  # B4/B6: required, non-negative
    mfe_points: float  # B4/B6: required, non-negative
    exit_reason: Optional[str] = None  # TP1_HIT | SL_HIT when is_resolved
    exit_derived_close_timestamp_utc: Optional[datetime] = None
    exit_price: Optional[float] = None
    realized_r: Optional[float] = None
    tp1_result_points: Optional[float] = None
    sl_result_points: Optional[float] = None


@dataclass
class TradeState:
    """Trade state nested record. trade_is_open/active_trade kept in sync with ExecutionState.open_trades by ESM."""
    trade_is_open: bool = False
    active_trade: Optional[ActiveTrade] = None
    entry_candle_close_time_utc: Optional[datetime] = None
    exit_candle_close_time_utc: Optional[datetime] = None


@dataclass
class ExecutionState:
    """
    Execution state as a superset shape based on Phase 0 execution state field list.
    
    Includes all hub-owned fields, spoke-required fields, and nested record shapes.
    All non-Phase-0 logic fields default safely (None / empty / 0).
    Naming seams are preserved as-is (not resolved).
    """
    # Hub-owned execution-state fields (Contract 6)
    confirmed_swings: List[SwingRecord] = field(default_factory=list)
    active_displacement_window: Optional[ActiveDisplacementWindowRecord] = None
    armed_fvg_execution_objects: List[ArmedFVGRecord] = field(default_factory=list)
    trade_state: TradeState = field(default_factory=TradeState)
    loss_counter: int = 0
    
    # Spoke-required execution-state view fields
    trade_is_open: bool = False  # Also in trade_state, but required as top-level
    armed_fvgs: List[ArmedFVGRecord] = field(default_factory=list)  # Naming seam: armed_fvg_execution_objects vs armed_fvgs
    confirmed_swings_m5: List[SwingRecord] = field(default_factory=list)
    phase: Optional[str] = None
    active_trade: Optional[ActiveTrade] = None  # Naming seam: also in trade_state
    open_trades: List[ActiveTrade] = field(default_factory=list)  # Source of truth; max len = config max_open_positions
    trade_sequence_id: Optional[str] = None
