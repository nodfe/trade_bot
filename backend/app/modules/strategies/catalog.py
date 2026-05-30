from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

StrategyKey = Literal["strong_uptrend", "volume_breakout", "pullback_watch"]


@dataclass(frozen=True)
class StrategyDefinition:
    key: StrategyKey
    tags: list[str]
    default_params: dict[str, Any] = field(default_factory=dict)


STRATEGY_CATALOG: list[StrategyDefinition] = [
    StrategyDefinition(
        key="strong_uptrend",
        tags=["trend_following", "momentum", "trending_market"],
        default_params={
            "min_return_20d_pct": 5,
            "min_return_5d_pct": 0,
            "min_volume_ratio": 1.3,
        },
    ),
    StrategyDefinition(
        key="volume_breakout",
        tags=["volume", "momentum", "volatile_market"],
        default_params={
            "min_volume_ratio": 1.8,
            "min_return_5d_pct": 2,
        },
    ),
    StrategyDefinition(
        key="pullback_watch",
        tags=["mean_reversion", "trending_market"],
        default_params={
            "min_return_20d_pct": 5,
            "max_return_5d_pct": 0,
        },
    ),
]


def get_strategy(key: str) -> StrategyDefinition | None:
    for s in STRATEGY_CATALOG:
        if s.key == key:
            return s
    return None
