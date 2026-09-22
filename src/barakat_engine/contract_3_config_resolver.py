"""Contract 3 — immutable, deterministic configuration resolution.

The production strategy schema is intentionally withheld. The configuration
resolution, canonicalisation, validation, merge order and hash behaviour are
the real public implementation.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import MappingProxyType
from typing import Any

from barakat_engine.guardrails import gr_fail, require_inputs, require_outputs

CONTRACT = "CONTRACT_3"
EDGE = "0→3"
ALLOWED_KEYS = frozenset({
    "execution_mode", "evaluation_start_timestamp", "evaluation_end_timestamp",
    "adapter_type", "csv_paths", "strategy_provider", "execution_policy_provider", "diagnostics_enabled",
    "diagnostic_sinks_enabled", "diagnostic_verbosity", "run_output_root",
    "run_output_naming_scheme", "max_open_positions",
})
FORBIDDEN_KEYS = frozenset({"run_id", "run_uuid", "broker_credentials"})
EXECUTION_MODES = frozenset({"backtest", "replay", "demo"})
ADAPTER_TYPES = frozenset({"CSV"})
DIAGNOSTIC_VERBOSITY_LEVELS = frozenset({"low", "normal", "high"})
DEFAULTS = {"diagnostics_enabled": False, "diagnostic_verbosity": "normal", "max_open_positions": 1, "strategy_provider": "withheld", "execution_policy_provider": "single_trade"}


def _validate_keys(obj: dict[str, Any], layer_name: str) -> None:
    for key in obj:
        if key in FORBIDDEN_KEYS:
            gr_fail(CONTRACT, "B6", EDGE, "INPUTS", f"forbidden key in {layer_name}: {key!r}")
        if key not in ALLOWED_KEYS:
            gr_fail(CONTRACT, "B6", EDGE, "INPUTS", f"unknown config key in {layer_name}: {key!r}")


def _load_json_object(path: Path, label: str) -> dict[str, Any]:
    require_inputs(path.exists(), CONTRACT, "B9", EDGE, f"{label} file not found: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        gr_fail(CONTRACT, "B9", EDGE, "INPUTS", f"{label} could not be read: {exc}")
    require_inputs(isinstance(value, dict), CONTRACT, "B3", EDGE, f"{label} must be a JSON object")
    return value


def _freeze_for_json(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        return int(value) if value.is_integer() else value
    if isinstance(value, dict):
        return {key: _freeze_for_json(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [_freeze_for_json(item) for item in value]
    gr_fail(CONTRACT, "B4", EDGE, "OUTPUTS", f"config value is not JSON-serializable: {type(value).__name__}")


def _canonical_json_dumps(value: Any) -> str:
    return json.dumps(_freeze_for_json(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def resolve_config(envelope: dict[str, Any]) -> tuple[MappingProxyType, str]:
    """Resolve base → config source → overrides into an immutable hashed snapshot."""
    base_raw = envelope.get("base_preset_id_or_path")
    require_inputs(isinstance(base_raw, str) and base_raw.strip(), CONTRACT, "B3", EDGE, "base_preset_id_or_path is required")
    sources = [envelope.get("config_file_path"), envelope.get("config_object"), envelope.get("config_blob")]
    require_inputs(sum(item is not None for item in sources) == 1, CONTRACT, "B6", EDGE, "exactly one config source is required")
    base = _load_json_object(Path(base_raw), "base_preset")
    _validate_keys(base, "base_preset")
    if envelope.get("config_file_path") is not None:
        source = _load_json_object(Path(envelope["config_file_path"]), "config_file")
    elif envelope.get("config_object") is not None:
        source = envelope["config_object"]
        require_inputs(isinstance(source, dict), CONTRACT, "B3", EDGE, "config_object must be an object")
    else:
        try:
            source = json.loads(envelope["config_blob"])
        except json.JSONDecodeError as exc:
            gr_fail(CONTRACT, "B9", EDGE, "INPUTS", f"config_blob JSON parse failed: {exc}")
        require_inputs(isinstance(source, dict), CONTRACT, "B3", EDGE, "config_blob must contain an object")
    overrides = envelope.get("overrides") or {}
    require_inputs(isinstance(overrides, dict), CONTRACT, "B6", EDGE, "overrides must be an object")
    _validate_keys(source, "config_source")
    _validate_keys(overrides, "overrides")
    merged = {**base, **source, **overrides}
    for key, value in DEFAULTS.items():
        merged.setdefault(key, value)
    require_inputs(merged.get("execution_mode") in EXECUTION_MODES, CONTRACT, "B9", EDGE, "invalid execution_mode")
    require_inputs(merged.get("adapter_type") in ADAPTER_TYPES, CONTRACT, "B9", EDGE, "public build supports CSV adapter only")
    require_inputs(isinstance(merged.get("csv_paths"), dict), CONTRACT, "B9", EDGE, "CSV adapter requires csv_paths")
    require_inputs(isinstance(merged["diagnostics_enabled"], bool), CONTRACT, "B9", EDGE, "diagnostics_enabled must be boolean")
    require_inputs(merged["diagnostic_verbosity"] in DIAGNOSTIC_VERBOSITY_LEVELS, CONTRACT, "B9", EDGE, "invalid diagnostic_verbosity")
    require_inputs(isinstance(merged["max_open_positions"], int) and merged["max_open_positions"] >= 1, CONTRACT, "B6", EDGE, "max_open_positions must be positive")
    if merged["execution_mode"] in {"backtest", "replay"}:
        require_inputs(bool(merged.get("evaluation_start_timestamp")) and bool(merged.get("evaluation_end_timestamp")), CONTRACT, "B9", EDGE, "finite runs require evaluation boundaries")
    snapshot_dict = dict(sorted(_freeze_for_json(merged).items()))
    snapshot = MappingProxyType(snapshot_dict)
    digest = hashlib.sha256(_canonical_json_dumps(snapshot_dict).encode("utf-8")).hexdigest()
    require_outputs(bool(digest), CONTRACT, "B4", EDGE, "configuration hash must be non-empty")
    return snapshot, digest


def peek_resolved_config(base_preset_path: str, config_path: str) -> dict[str, Any]:
    snapshot, digest = resolve_config({"base_preset_id_or_path": base_preset_path, "config_file_path": config_path, "overrides": {}})
    return {"resolved_config_snapshot_hash": digest, "execution_mode": snapshot["execution_mode"], "adapter_type": snapshot["adapter_type"], "run_output_root": snapshot.get("run_output_root"), "csv_paths": snapshot["csv_paths"]}
