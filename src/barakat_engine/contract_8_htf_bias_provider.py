"""Contract 8 public boundary.

Production decision criteria intentionally withheld; surrounding lifecycle and
integration interface are retained for the real orchestration layer.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from barakat_engine.types import BiasState
from barakat_engine.strategy_boundary import WithheldDecisionProvider


@dataclass(frozen=True)
class PublicBiasTimeline:
    created_at_utc: datetime
    _records: tuple = ()

    def get_bias_at(self, now_utc: datetime) -> BiasState:
        return BiasState(bias="NEUTRAL", bias_leg_id="withheld", bias_set_at_utc=now_utc)


class HTFBiasProvider(WithheldDecisionProvider):
    def __init__(self, config_snapshot: Any, evaluation_start_utc: datetime) -> None:
        self.config_snapshot = config_snapshot
        self.evaluation_start_utc = evaluation_start_utc

    def build_timeline_from_h1(self, h1_candles: list[Any], m5_candles: list[Any]) -> PublicBiasTimeline:
        return PublicBiasTimeline(created_at_utc=self.evaluation_start_utc)
