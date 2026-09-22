"""
Verify which config was used for a run by comparing resolved_config_snapshot_hash.
Usage: python Tools/verify_run_config.py <run_dir> [config_path] [--out_root DIR]
Pass --out_root Runs if you ran the backtest with --out_root Runs (so overrides match).
"""
import json
import sys
from pathlib import Path

# run from repo root
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from barakat_engine import contract_3_config_resolver as c3

BASE_PRESET = "config/presets/public_engine_preset.json"


def main():
    args = [a for a in sys.argv[1:] if a != "--out_root"]
    out_root = None
    if "--out_root" in sys.argv and sys.argv.index("--out_root") + 1 < len(sys.argv):
        out_root = sys.argv[sys.argv.index("--out_root") + 1]
    if len(args) < 1:
        print("Usage: verify_run_config.py <run_dir> [config_path] [--out_root DIR]")
        print("Example: verify_run_config.py runs/example config/examples/public_backtest.example.json --out_root runs")
        sys.exit(1)
    run_arg = Path(args[0])
    config_path = args[1] if len(args) > 1 else "config/examples/public_backtest.example.json"
    if run_arg.is_dir():
        audit_file = run_arg / "audit_header.json"
    else:
        audit_file = run_arg
    if not audit_file.exists():
        print(f"Not found: {audit_file}")
        sys.exit(1)
    with open(audit_file, encoding="utf-8") as f:
        audit = json.load(f)
    run_hash = audit.get("resolved_config_snapshot_hash") or audit.get("config_snapshot_hash")
    if not run_hash:
        print("No resolved_config_snapshot_hash in audit. Keys:", list(audit.keys()))
        sys.exit(1)
    print(f"Run audit hash:  {run_hash}")
    overrides = {"run_output_root": out_root} if out_root else {}
    envelope = {
        "base_preset_id_or_path": BASE_PRESET,
        "config_file_path": config_path,
        "overrides": overrides,
    }
    try:
        snapshot, current_hash = c3.resolve_config(envelope)
    except Exception as e:
        print(f"Resolve failed: {e}")
        sys.exit(1)
    print(f"Config hash for {config_path}: {current_hash}")
    match = run_hash == current_hash
    print(f"Match: {match}")
    if not match:
        print("\nResolved snapshot (relevant keys):")
        for k in sorted(snapshot.keys()):
            if k in ("evaluation_start_timestamp", "evaluation_end_timestamp", "csv_paths",
                     "max_open_positions", "strategy_provider"):
                print(f"  {k}: {snapshot[k]}")
    if not match:
        print("\n--> The run was NOT executed with the config you passed.")
        print("    Re-run the backtest with the current config to verify behaviour.")
    sys.exit(0 if match else 1)


if __name__ == "__main__":
    main()
