from __future__ import annotations

import csv
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from barakat_engine import contract_2_clock as c2
from barakat_engine import contract_3_config_resolver as c3
from barakat_engine import contract_5_data_adapter as c5
from barakat_engine import contract_6_execution_state_machine as c6
from barakat_engine import contract_15_mandatory_sink_logger as c15
from barakat_engine.types import EngineStepStatus, NormalizedClosedCandle


class PublicEngineTests(unittest.TestCase):
    def test_clock_derives_utc_close(self) -> None:
        opened = datetime(2025, 1, 1, 9, 0, tzinfo=timezone.utc)
        self.assertEqual(c2.derive_close_timestamp("M5", opened), datetime(2025, 1, 1, 9, 5, tzinfo=timezone.utc))

    def test_config_is_immutable_and_hashed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "base.json"
            base.write_text('{"execution_mode":"backtest","adapter_type":"CSV","csv_paths":{"M5":"m5.csv","H1":"h1.csv"},"run_output_root":"runs"}', encoding="utf-8")
            snapshot, digest = c3.resolve_config({"base_preset_id_or_path": str(base), "config_object": {"evaluation_start_timestamp":"2025-01-01T00:00:00Z", "evaluation_end_timestamp":"2025-01-01T01:00:00Z"}})
            self.assertEqual(len(digest), 64)
            with self.assertRaises(TypeError):
                snapshot["execution_mode"] = "demo"  # type: ignore[index]

    def test_csv_adapter_normalises_utc_candle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp) / "m5.csv"
            data.write_text("time,open,high,low,close\n2025-01-01T00:00:00Z,1,2,0.5,1.5\n", encoding="utf-8")
            candle = c5.peek_first_n(str(data), 1)[0]
            self.assertEqual(candle.candle_open_time_utc.utcoffset(), timezone.utc.utcoffset(candle.candle_open_time_utc))
            self.assertEqual(candle.close, 1.5)

    def test_state_machine_advances_without_private_provider(self) -> None:
        engine = c6.ExecutionStateMachine(
            run_id="public-test",
            execution_mode="backtest",
            evaluation_start_timestamp=datetime(2025, 1, 1, tzinfo=timezone.utc),
            evaluation_end_timestamp=datetime(2025, 1, 2, tzinfo=timezone.utc),
            config_snapshot={"execution_policy_provider": "single_trade", "max_open_positions": 1},
        )
        candle = NormalizedClosedCandle(datetime(2025, 1, 1, 0, 0, tzinfo=timezone.utc), 1, 2, 0.5, 1.5)
        self.assertEqual(engine.on_candle_close(candle), EngineStepStatus.CONTINUE)

    def test_logger_creates_audit_sinks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_id = "safe-run"
            root = Path(tmp) / "runs"
            logger = c15.MandatorySinkLogger(run_id, run_id, str(root), str(root / run_id), "backtest")
            logger.close()
            self.assertTrue((root / run_id / "executed_trade_log.csv").exists())

    def test_verification_tool_accepts_synthetic_log(self) -> None:
        root = Path(__file__).resolve().parents[1]
        log = root / "examples" / "sample-output" / "verification_trade_log.synthetic.csv"
        result = subprocess.run([sys.executable, str(root / "tools" / "verify_realised_r.py"), str(log)], capture_output=True, text=True, check=True)
        self.assertIn("Realised R verification", result.stdout)

    def test_outcome_verifier_accepts_full_synthetic_log(self) -> None:
        root = Path(__file__).resolve().parents[1]
        log = root / "examples" / "sample-output" / "outcome_verification_log.synthetic.csv"
        fixture = root / "examples" / "data" / "synthetic_m5.csv"
        result = subprocess.run(
            [sys.executable, str(root / "tools" / "verify_outcomes_against_m5.py"), str(log), str(fixture)],
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertIn("All checked trades", result.stdout)


if __name__ == "__main__":
    unittest.main()
