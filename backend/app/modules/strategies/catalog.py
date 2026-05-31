from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

StrategyKey = Literal[
    "strong_uptrend",
    "volume_breakout",
    "pullback_watch",
    "first_limit_up_low",
    "leader_streak",
    "zt_relay",
    "lhb_follow",
    "oversold_bounce",
    "broken_board_dip",
    "strong_pullback_ma5",
]


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
            "min_volume_ratio": 1.3,
            "min_return_5d_pct": 0,
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
    StrategyDefinition(
        key="first_limit_up_low",
        tags=["limit_up", "starter_signal", "low_position"],
        default_params={
            "min_quiet_days": 20,
            "max_high_60d_ratio": 0.85,
        },
    ),
    StrategyDefinition(
        key="leader_streak",
        tags=["limit_up", "leader", "momentum"],
        default_params={
            "min_streak": 2,
            "min_volume_ratio": 1.2,
        },
    ),
    StrategyDefinition(
        key="zt_relay",
        tags=["limit_up", "relay", "short_term"],
        default_params={
            "max_open_gap_pct": 5,
            "min_volume_ratio": 1.0,
        },
    ),
    StrategyDefinition(
        key="lhb_follow",
        tags=["dragon_tiger", "smart_money", "short_term"],
        default_params={
            "min_net_buy_yi": 0.3,
            "lhb_lookback_days": 1,
            "max_open_gap_pct": 5,
        },
    ),
]


def get_strategy(key: str) -> StrategyDefinition | None:
    for s in STRATEGY_CATALOG:
        if s.key == key:
            return s
    return None
