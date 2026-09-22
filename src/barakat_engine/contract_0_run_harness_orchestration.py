"""
Contract 0 — RunHarness & Orchestration (Phase 0).

Deterministic run entrypoint and run lifecycle: validate RunRequest, resolve/freeze config,
wire modules in mandated order (Steps 1–9), run forward-only candle loop, terminate.

Authority: CONTRACT_0_RunHarness_Orchestration_SECTION_B__PATCHED_S2 DONE.txt
Phase 0 scope: Logic OFF; orchestration contract-true.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from barakat_engine.guardrails import (
    gr_fail,
    require_cadence,
    require_inputs,
    require_outputs,
    require_ownership,
)
from barakat_engine import contract_1_run_identity_audit as c1
from barakat_engine import contract_2_clock as c2
from barakat_engine import contract_3_config_resolver as c3
from barakat_engine import contract_4_execution_mode_controller as c4
from barakat_engine import contract_5_data_adapter as c5
from barakat_engine import contract_6_execution_state_machine as c6
from barakat_engine import contract_7_single_trade_policy as c7
from barakat_engine import contract_8_htf_bias_provider as c8
from barakat_engine import contract_9_structure_module as c9
from barakat_engine import contract_10_displacement_module as c10
from barakat_engine import contract_11_fvg_module as c11
from barakat_engine import contract_12_entry_module as c12
from barakat_engine import contract_13_risk_targets_module as c13
from barakat_engine import contract_14_outcome_simulator as c14
from barakat_engine import contract_15_mandatory_sink_logger as c15
from barakat_engine import contract_16_diagnostic_sink_logger as c16
from barakat_engine.types import (
    EngineStepStatus,
    EngineTerminationStatus,
    NormalizedClosedCandle,
)

CONTRACT = "CONTRACT_0"
EDGE_0_1 = "0→1"
EDGE_0_2 = "0→2"
EDGE_0_3 = "0→3"
EDGE_0_4 = "0→4"
EDGE_0_5 = "0→5"
EDGE_0_6 = "0→6"
EDGE_0_15 = "0→15"
EDGE_0_16 = "0→16"

VALID_EXECUTION_MODES = frozenset({"backtest", "replay", "demo", "live"})
STOPPED_EXTERNALLY = "STOPPED_EXTERNALLY"


# --- Input / output shapes (B3/B4) ---

@dataclass(frozen=True)
class AdapterInput:
    """AdapterInput: adapter_type (REQUIRED), adapter_params (REQUIRED; RunHarness MUST NOT validate internal keys)."""
    adapter_type: str
    adapter_params: dict[str, Any]


@dataclass
class RunBoundaries:
    """Optional run boundaries from RunRequest."""
    evaluation_start_timestamp: Optional[str] = None
    evaluation_end_timestamp: Optional[str] = None


@dataclass
class RunRequest:
    """RunRequest (LOCKED): instrument_id, execution_mode, config_input, adapter_input, optional run_boundaries."""
    instrument_id: str
    execution_mode: str
    config_input: dict[str, Any]  # ConfigInputEnvelope
    adapter_input: AdapterInput
    run_boundaries: Optional[RunBoundaries] = None


@dataclass
class ExternalStopSignal:
    """ExternalStopSignal: stop_requested (REQUIRED), stop_reason (OPTIONAL), stop_requested_at_utc (OPTIONAL)."""
    stop_requested: bool
    stop_reason: Optional[str] = None
    stop_requested_at_utc: Optional[str] = None


@dataclass
class BuildMetadata:
    """Build/runtime metadata for audit header (runtime-defined sourcing)."""
    engine_version: str = ""
    git_hash: str = ""
    build_id: str = ""


def _parse_utc_timestamp(s: str) -> datetime:
    """Parse ISO UTC timestamp string to timezone-aware datetime."""
    s = s.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt


def _validate_run_request(request: RunRequest) -> None:
    """Validate RunRequest (B9): required fields and ConfigInputEnvelope. Hard-fail on violation."""
    require_inputs(
        isinstance(request.instrument_id, str) and (request.instrument_id or "").strip() != "",
        CONTRACT, "B3", EDGE_0_3,
        "instrument_id is required and must be non-empty string",
    )
    require_inputs(
        request.execution_mode in VALID_EXECUTION_MODES,
        CONTRACT, "B3", EDGE_0_3,
        f"execution_mode must be one of {sorted(VALID_EXECUTION_MODES)}",
    )
    require_inputs(
        isinstance(request.config_input, dict),
        CONTRACT, "B3", EDGE_0_3,
        "config_input must be ConfigInputEnvelope (dict)",
    )
    require_inputs(
        request.adapter_input is not None
        and isinstance(request.adapter_input.adapter_type, str)
        and isinstance(request.adapter_input.adapter_params, dict),
        CONTRACT, "B3", EDGE_0_3,
        "adapter_input must have adapter_type (str) and adapter_params (object)",
    )
    env = request.config_input
    base = env.get("base_preset_id_or_path")
    require_inputs(
        base is not None and isinstance(base, str) and (base or "").strip() != "",
        CONTRACT, "B9", EDGE_0_3,
        "ConfigInputEnvelope.base_preset_id_or_path is required and non-empty",
    )
    overrides = env.get("overrides")
    if overrides is not None:
        require_inputs(
            isinstance(overrides, dict),
            CONTRACT, "B9", EDGE_0_3,
            "ConfigInputEnvelope.overrides must be object if present",
        )
    cfg_file = 1 if env.get("config_file_path") is not None else 0
    cfg_obj = 1 if env.get("config_object") is not None else 0
    cfg_blob = 1 if env.get("config_blob") is not None else 0
    require_inputs(
        cfg_file + cfg_obj + cfg_blob == 1,
        CONTRACT, "B9", EDGE_0_3,
        "ConfigInputEnvelope: exactly one of config_file_path, config_object, config_blob required",
    )


def _check_duplicate_controls(
    request: RunRequest,
    snapshot: Any,
    run_boundaries: Optional[RunBoundaries],
) -> None:
    """B9: If same control from multiple sources mismatches → HARD FAIL."""
    # execution_mode: RunRequest vs ResolvedConfigSnapshot
    snap_mode = snapshot.get("execution_mode")
    if snap_mode is not None and request.execution_mode != snap_mode:
        gr_fail(
            CONTRACT, "B9", EDGE_0_3, "INPUTS",
            f"execution_mode mismatch: RunRequest={request.execution_mode!r} vs ResolvedConfigSnapshot={snap_mode!r}",
        )
    # evaluation_start_timestamp / evaluation_end_timestamp: run_boundaries vs snapshot
    if run_boundaries is not None:
        req_start = run_boundaries.evaluation_start_timestamp
        req_end = run_boundaries.evaluation_end_timestamp
        snap_start = snapshot.get("evaluation_start_timestamp")
        snap_end = snapshot.get("evaluation_end_timestamp")
        if req_start is not None and snap_start is not None and req_start != snap_start:
            gr_fail(
                CONTRACT, "B9", EDGE_0_3, "INPUTS",
                "evaluation_start_timestamp mismatch: RunRequest.run_boundaries vs ResolvedConfigSnapshot",
            )
        if req_end is not None and snap_end is not None and req_end != snap_end:
            gr_fail(
                CONTRACT, "B9", EDGE_0_3, "INPUTS",
                "evaluation_end_timestamp mismatch: RunRequest.run_boundaries vs ResolvedConfigSnapshot",
            )
    # adapter_type: RunRequest.adapter_input vs ResolvedConfigSnapshot
    snap_adapter = snapshot.get("adapter_type")
    if snap_adapter is not None and request.adapter_input.adapter_type != snap_adapter:
        gr_fail(
            CONTRACT, "B9", EDGE_0_3, "INPUTS",
            f"adapter_type mismatch: RunRequest.adapter_input={request.adapter_input.adapter_type!r} vs ResolvedConfigSnapshot={snap_adapter!r}",
        )


def _resolve_evaluation_timestamps(
    snapshot: Any,
    run_boundaries: Optional[RunBoundaries],
    mode_context: c4.ExecutionModeContext,
) -> tuple[Optional[str], Optional[str]]:
    """Resolve evaluation_start_timestamp and evaluation_end_timestamp; duplicate already checked."""
    start = None
    end = None
    if run_boundaries is not None:
        start = run_boundaries.evaluation_start_timestamp
        end = run_boundaries.evaluation_end_timestamp
    if start is None:
        start = snapshot.get("evaluation_start_timestamp")
    if end is None:
        end = snapshot.get("evaluation_end_timestamp")
    return start, end


def _default_evaluation_start_from_first_candle(
    adapter: Any,
    time_semantics: c2.TimeSemanticsContext,
) -> str:
    """Finite mode: default evaluation_start to derived close of first M5 candle (B3)."""
    try:
        m5_stream = adapter.get_timeframe_stream("M5")
        first_m5 = next(iter(m5_stream), None)
    except Exception:
        first_m5 = None
    require_inputs(
        first_m5 is not None,
        CONTRACT, "B9", EDGE_0_6,
        "finite mode with omitted evaluation_start_timestamp requires at least one M5 candle in adapter",
    )
    close_ts = time_semantics.derive_close_timestamp("M5", first_m5.candle_open_time_utc)
    return close_ts.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _write_audit_header(
    run_output_dir: str,
    run_id: str,
    run_uuid: str,
    timestamp_utc_created: str,
    execution_mode: str,
    instrument_id: str,
    adapter_type: str,
    adapter_version: str,
    build_metadata: BuildMetadata,
    resolved_config_snapshot_hash: str,
    module_selection: list[dict[str, str]],
    input_dataset_identity: dict,
) -> None:
    """Write runs/<run_id>/audit_header.json exactly once. HARD FAIL if file already exists (B4/B9)."""
    audit_path = os.path.join(run_output_dir, "audit_header.json")
    require_outputs(
        not os.path.isfile(audit_path),
        CONTRACT, "B9", EDGE_0_1,
        f"audit_header.json already exists for run_id {run_id!r}; must not overwrite",
    )
    payload = {
        "run_id": run_id,
        "run_uuid": run_uuid,
        "timestamp_utc_created": timestamp_utc_created,
        "execution_mode": execution_mode,
        "instrument_id": instrument_id,
        "adapter_type": adapter_type,
        "adapter_version": adapter_version,
        "engine_version": build_metadata.engine_version,
        "git_hash": build_metadata.git_hash,
        "build_id": build_metadata.build_id,
        "module_selection_list": module_selection,
        "resolved_config_snapshot_hash": resolved_config_snapshot_hash,
        "input_dataset_identity": input_dataset_identity,
    }
    try:
        with open(audit_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, sort_keys=True, indent=2)
    except OSError as e:
        gr_fail(
            CONTRACT, "B9", EDGE_0_1, "OUTPUTS",
            f"audit_header.json write failed: {e}",
        )


def run(
    request: RunRequest,
    run_output_root: str,
    get_external_stop_signal: Callable[[], ExternalStopSignal],
    build_metadata: Optional[BuildMetadata] = None,
    construct_only: bool = False,
) -> str:
    """
    Run entrypoint (LOCKED). Accepts RunRequest, run_output_root (environment-defined),
    external stop provider, optional build metadata, and optional construct_only.
    Returns run_end_status.

    Per-run fixed order: Steps 1–9. If construct_only=True, performs Steps 1–8
    (through audit header + sink construction), flushes/closes loggers, then returns
    "CONSTRUCT_ONLY" without entering the candle loop.
    RunHarness MUST NOT mutate ExecutionState directly (ownership).
    """
    if build_metadata is None:
        build_metadata = BuildMetadata()

    _validate_run_request(request)

    # --- Step 1: RunIdentity (run_output_root, execution_mode, instrument_id only) ---
    identity = c1.create_run_identity(
        run_output_root=run_output_root,
        execution_mode=request.execution_mode,
        instrument_id=request.instrument_id,
    )

    # --- Step 2: TimeSemanticsContext construct and freeze ---
    time_semantics = c2.TimeSemanticsContext()

    # --- Step 3: ConfigResolver once; freeze ResolvedConfigSnapshot ---
    snapshot_dict, resolved_config_snapshot_hash = c3.resolve_config(request.config_input)
    snapshot = snapshot_dict  # MappingProxyType from c3
    _check_duplicate_controls(request, snapshot, request.run_boundaries)

    # Duplicate control: run_output_root (environment) vs snapshot
    snap_root = snapshot.get("run_output_root")
    require_inputs(
        snap_root is not None and str(snap_root).strip() != "",
        CONTRACT, "B9", EDGE_0_3,
        "ResolvedConfigSnapshot.run_output_root is required",
    )
    if str(snap_root).rstrip("/") != str(run_output_root).rstrip("/"):
        gr_fail(
            CONTRACT, "B9", EDGE_0_3, "INPUTS",
            f"run_output_root mismatch: environment={run_output_root!r} vs ResolvedConfigSnapshot={snap_root!r}",
        )

    # --- Resolve evaluation timestamps (after snapshot; for Step 4 and ESM) ---
    eval_start_str, eval_end_str = _resolve_evaluation_timestamps(
        snapshot, request.run_boundaries, None
    )
    mode_context = c4.build_execution_mode_context(
        execution_mode=request.execution_mode,
        evaluation_start_timestamp=eval_start_str,
        evaluation_end_timestamp=eval_end_str,
    )

    # --- Step 4: ExecutionModeController already invoked above; we have mode_context ---
    # (We built it with snapshot/run_boundaries; default for finite omitted start is done after Step 6.)

    # --- Step 5: Logger construction ---
    mandatory_logger = c15.MandatorySinkLogger(
        run_id=identity.run_id,
        run_uuid=identity.run_uuid,
        run_output_root=run_output_root,
        run_output_dir=identity.run_output_dir,
        execution_mode=request.execution_mode,
    )
    diagnostics_enabled = bool(snapshot.get("diagnostics_enabled", False))
    diagnostic_sinks = snapshot.get("diagnostic_sinks_enabled") or []
    if not isinstance(diagnostic_sinks, list):
        diagnostic_sinks = []
    diag_verbosity = snapshot.get("diagnostic_verbosity") or "normal"
    diagnostic_logger = c16.DiagnosticSinkLogger(
        run_id=identity.run_id,
        run_uuid=identity.run_uuid,
        run_output_dir=identity.run_output_dir,
        diagnostics_enabled=diagnostics_enabled,
        diagnostic_sinks_enabled=diagnostic_sinks,
        diagnostic_verbosity=diag_verbosity,
    )

    # --- Step 6: DataAdapter from resolved snapshot (adapter_type, csv_paths) + request overlay ---
    adapter_config = dict(snapshot)
    if request.adapter_input.adapter_params:
        adapter_config.update(request.adapter_input.adapter_params)
    adapter = c5.CSVDataAdapter(adapter_config)

    # --- Default evaluation_start for finite mode when omitted ---
    if mode_context.is_finite and eval_start_str is None:
        eval_start_str = _default_evaluation_start_from_first_candle(adapter, time_semantics)
        mode_context = c4.build_execution_mode_context(
            execution_mode=request.execution_mode,
            evaluation_start_timestamp=eval_start_str,
            evaluation_end_timestamp=eval_end_str,
        )

    eval_start_dt: Optional[datetime] = None
    eval_end_dt: Optional[datetime] = None
    if eval_start_str:
        eval_start_dt = _parse_utc_timestamp(eval_start_str)
    if eval_end_str:
        eval_end_dt = _parse_utc_timestamp(eval_end_str)
    require_inputs(
        eval_start_dt is not None,
        CONTRACT, "B5", EDGE_0_4,
        "evaluation_start_timestamp must be set (from config, run_boundaries, or first-candle default)",
    )

    # --- Step 6b: Build HTF bias timeline from adapter H1 + M5 for ESM ---
    h1_candles = list(adapter.get_timeframe_stream("H1"))
    m5_candles_for_htf = list(adapter.get_timeframe_stream("M5"))
    htf_provider = c8.HTFBiasProvider(snapshot, eval_start_dt)
    htf_timeline = htf_provider.build_timeline_from_h1(h1_candles, m5_candles_for_htf)
    # TEMP_DIAG_REMOVE_AFTER_FIX: DIAG_HTF_WIRING
    _created = htf_timeline is not None
    print("DIAG_HTF_WIRING: timeline created", _created)
    if _created:
        _recs = getattr(htf_timeline, "_records",