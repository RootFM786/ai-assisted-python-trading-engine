"""Contract 16 public diagnostic sink framework.

Production decision criteria intentionally withheld. File lifecycle, sink
enablement and safe CSV serialization remain available for inspection.
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Any


class DiagnosticSinkLogger:
    def __init__(self, *, run_id: str, run_uuid: str, run_output_dir: str, diagnostics_enabled: bool, diagnostic_sinks_enabled: list[str], diagnostic_verbosity: str) -> None:
        self.enabled = diagnostics_enabled
        self.run_id = run_id
        self.run_uuid = run_uuid
        self.output_dir = Path(run_output_dir)
        self.sinks = tuple(diagnostic_sinks_enabled)
        self.verbosity = diagnostic_verbosity
        self._handles: list[Any] = []
        if self.enabled:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            for sink in self.sinks:
                handle = (self.output_dir / Path(sink).name).open("w", newline="", encoding="utf-8")
                csv.writer(handle).writerow(["run_id", "timestamp_utc", "event", "details"])
                self._handles.append(handle)

    def on_candle_close(self, ctx: Any) -> None:
        return None

    def flush(self) -> None:
        for handle in self._handles:
            handle.flush()

    def close(self) -> None:
        for handle in self._handles:
            handle.close()
