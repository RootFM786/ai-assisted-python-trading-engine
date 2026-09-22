"""
V1 backtest runner: CLI entrypoint that builds RunRequest and invokes the
full V1 harness (run_v1) — wiring Contracts 7–14 + sinks 15/16.

Usage:
    PYTHONPATH=src python -m barakat_engine.run_backtest --config config/examples/public_backtest.example.json
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from barakat_engine import contract_3_config_resolver as c3
from barakat_engine.contract_0_run_harness_orchestration import (
    AdapterInput,
    ExternalStopSignal,
    RunRequest,
    run_v1,
)


BASE_PRESET_ID_OR_PATH = "config/presets/public_engine_preset.json"
INSTRUMENT_ID = "PUBLIC_INSTRUMENT"
EXECUTION_MODE = "backtest"
ADAPTER_TYPE = "CSV"


def _build_config_envelope(config_path: str, out_root: str | None = None) -> dict[str, Any]:
    overrides: dict[str, Any] = {}
    if out_root is not None:
        overrides["run_output_root"] = out_root
    return {
        "base_preset_id_or_path": BASE_PRESET_ID_OR_PATH,
        "config_file_path": config_path,
        "overrides": overrides,
    }


def _build_adapter_input() -> AdapterInput:
    return AdapterInput(adapter_type=ADAPTER_TYPE, adapter_params={})


def _build_run_request(config_path: str, out_root: str | None = None) -> RunRequest:
    envelope = _build_config_envelope(config_path, out_root)
    adapter_input = _build_adapter_input()
    return RunRequest(
        instrument_id=INSTRUMENT_ID,
        execution_mode=EXECUTION_MODE,
        config_input=envelope,
        adapter_input=adapter_input,
        run_boundaries=None,
    )


def _external_stop_provider_stub() -> ExternalStopSignal:
    return ExternalStopSignal(stop_requested=False)


def _get_run_output_root(request: RunRequest, out_root: str | None) -> str:
    if out_root is not None:
        return out_root
    snapshot, _ = c3.resolve_config(request.config_input)
    root = snapshot.get("run_output_root")
    if root is None or not str(root).strip():
        raise RuntimeError("ResolvedConfigSnapshot.run_output_root is required")
    return str(root).strip()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="V1 backtest runner: build RunRequest and invoke full V1 harness.",
    )
    parser.add_argument("--config", required=True, metavar="PATH",
                        help="Path to a public-safe config JSON.")
    parser.add_argument("--out_root", default=None, metavar="DIR",
                        help="Override run_output_root.")
    parser.add_argument("--construct_only", action="store_true",
                        help="Run Steps 1–8 then exit before candle loop.")
    args = parser.parse_args()

    request = _build_run_request(args.config, args.out_root)
    run_output_root = _get_run_output_root(request, args.out_root)
    status = run_v1(
        request,
        run_output_root,
        _external_stop_provider_stub,
        build_metadata=None,
        construct_only=args.construct_only,
    )
    print(status)
    return 0 if status in ("TERMINATED_OK", "CONSTRUCT_ONLY") else 1


if __name__ == "__main__":
    sys.exit(main())
