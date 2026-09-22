"""Contract 12 public integration boundary; production entry criteria withheld."""
from __future__ import annotations

from typing import Any

from barakat_engine.strategy_boundary import WithheldDecisionProvider


class EntryModule(WithheldDecisionProvider):
    def __init__(self, *, risk_targets_module: Any, config_snapshot: Any) -> None:
        self.risk_targets_module = risk_targets_module
        self.config_snapshot = config_snapshot
