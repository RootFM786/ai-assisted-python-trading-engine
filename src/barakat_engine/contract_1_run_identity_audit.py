"""
Contract 1 — RunIdentity & Audit (Phase 0).

Generate run identity at execution start; return run_output_dir and creation timestamp.
Called exactly once per run as RunHarness orchestration Step 1.

Authority: CONTRACT_1_RunIdentity_Audit_SECTION_B__PATCHED_S2 DONE.txt
"""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from barakat_engine.guardrails import (
    gr_fail,
    require_inputs,
    require_outputs,
)

CONTRACT = "CONTRACT_1"
EDGE = "0→1"
VALID_EXECUTION_MODES = frozenset({"backtest", "replay", "demo", "live"})


@dataclass(frozen=True)
class RunIdentityOutput:
    """RunIdentityOutput (Contract 1 B4): run_id, run_uuid, timestamp_utc_created, run_output_dir."""
    run_id: str
    run_uuid: str
    timestamp_utc_created: str
    run_output_dir: str


def create_run_identity(
    run_output_root: str,
    execution_mode: str,
    instrument_id: str,
) -> RunIdentityOutput:
    """
    Create run identity at execution start. Called exactly once per run (Step 1).

    Inputs (LOCKED): run_output_root, execution_mode ∈ {backtest, replay, demo, live}, instrument_id.
    Outputs (LOCKED): run_id, run_uuid (= run_id), timestamp_utc_created, run_output_dir.
    run_output_dir MUST equal run_output_root + "/" + run_id + "/"
    """
    # --- INPUTS (SEAM=INPUTS) ---
    require_inputs(
        isinstance(run_output_root, str) and (run_output_root or "").strip() != "",
        CONTRACT,
        "B3",
        EDGE,
        "run_output_root must be a non-empty string",
    )
    require_inputs(
        execution_mode in VALID_EXECUTION_MODES,
        CONTRACT,
        "B3",
        EDGE,
        f"execution_mode must be one of {sorted(VALID_EXECUTION_MODES)}; got {execution_mode!r}",
    )
    require_inputs(
        isinstance(instrument_id, str) and (instrument_id or "").strip() != "",
        CONTRACT,
        "B3",
        EDGE,
        "instrument_id must be a non-empty string",
    )

    run_output_root = run_output_root.strip()
    instrument_id = instrument_id.strip()

    # Generate identity at execution start; unique and unknown prior to execution.
    run_id = str(uuid.uuid4())
    run_uuid = run_id
    timestamp_utc_created = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    run_output_dir = run_output_root + "/" + run_id + "/"

    # --- OUTPUTS (SEAM=OUTPUTS) ---
    require_outputs(
        run_id != "" and run_uuid != "",
        CONTRACT,
        "B4",
        EDGE,
        "run_id and run_uuid must be non-empty",
    )
    require_outputs(
        run_uuid == run_id,
        CONTRACT,
        "B4",
        EDGE,
        "run_uuid MUST equal run_id",
    )
    require_outputs(
        (run_output_root + "/" + run_id + "/") == run_output_dir,
        CONTRACT,
        "B4",
        EDGE,
        "run_output_dir MUST equal run_output_root + '/' + run_id + '/'",
    )
    require_outputs(
        timestamp_utc_created != "",
        CONTRACT,
        "B4",
        EDGE,
        "timestamp_utc_created must be non-empty",
    )

    return RunIdentityOutput(
        run_id=run_id,
        run_uuid=run_uuid,
        timestamp_utc_created=timestamp_utc_created,
        run_output_dir=run_output_dir,
    )


def peek_run_identity(run_output_root: str = "runs/_selftest") -> dict:
    """
    Phase 0 helper: manual test only; not used by engine.

    Calls create_run_identity(run_output_root, "backtest", "PUBLIC_INSTRUMENT"),
    creates run_output_dir if required, returns dict with run_id, run_uuid, run_output_dir, timestamp_utc_created.
    HARD FAIL if run_uuid != run_id, run_output_dir != run_output_root + "/" + run_id + "/",
    or run_output_dir cannot be created.
    """
    out = create_run_identity(run_output_root, "backtest", "PUBLIC_INSTRUMENT")

    # Enforce run_uuid == run_id
    if out.run_uuid != out.run_id:
        gr_fail(
            CONTRACT,
            "B4",
            EDGE,
            "OUTPUTS",
            f"peek_run_identity: run_uuid must equal run_id; got run_uuid={out.run_uuid!r} run_id={out.run_id!r}",
        )

    # Enforce run_output_dir == run_output_root + "/" + run_id + "/"
    expected_dir = run_output_root.strip() + "/" + out.run_id + "/"
    if out.run_output_dir != expected_dir:
        gr_fail(
            CONTRACT,
            "B4",
            EDGE,
            "OUTPUTS",
            f"peek_run_identity: run_output_dir must equal run_output_root + '/' + run_id + '/'; "
            f"got run_output_dir={out.run_output_dir!r} expected={expected_dir!r}",
        )

    # Create run_output_dir; HARD FAIL if cannot create
    try:
        os.makedirs(out.run_output_dir, exist_ok=True)
    except OSError as e:
        gr_fail(
            CONTRACT,
            "B9",
            EDGE,
            "OUTPUTS",
            f"peek_run_identity: cannot create run_output_dir {out.run_output_dir!r}: {e}",
        )

    return {
        "run_id": out.run_id,
        "run_uuid": out.run_uuid,
        "run_output_dir": out.run_output_dir,
        "timestamp_utc_created": out.timestamp_utc_created,
    }
