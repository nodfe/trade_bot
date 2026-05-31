"""Tests for the strategy subscription module (CRUD + dispatch)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any

import pytest

from app.core.exceptions import BadRequestError, NotFoundError
from app.modules.market_data.schemas import (
    StockScreenItemOut,
    StockScreenResultOut,
)
from app.modules.strategies.subscriptions.cron import (
    CronParseError,
    cron_matches,
    is_due,
    parse_cron,
)
from app.modules.strategies.subscriptions.models import StrategySubscription
from app.modules.strategies.subscriptions.schemas import SubscriptionCreate
from app.modules.strategies.subscriptions.service import (
    SubscriptionService,
)


class _InMemoryRepo:
    def __init__(self) -> None:
        self.rows: dict[str, StrategySubscription] = {}

    async def list_all(
        self, *, enabled: bool | None = None, user_id: str | None = None
    ) -> list[StrategySubscription]:
        out = list(self.rows.values())
        if enabled is not None:
            out = [s for s in out if s.enabled == enabled]
        if user_id is not None:
            out = [s for s in out if s.user_id == user_id]
        return out

    async def get(self, sub_id: str) -> StrategySubscription | None:
        return self.rows.get(sub_id)

    async def create(self, sub: StrategySubscription) -> StrategySubscription:
        self.rows[sub.id] = sub
        return sub

    async def delete(self, sub_id: str) -> bool:
        return self.rows.pop(sub_id, None) is not None

    async def update_dispatched_at(self, sub_id: str, when) -> None:
        if sub_id in self.rows:
            self.rows[sub_id].last_dispatched_at = when


class _StubMarketDataService:
    def __init__(self, items: list[StockScreenItemOut]) -> None:
        self._items = items
        self.calls: list[tuple[str, Any]] = []

    async def screen_stocks(
        self, screen_type: str, params=None, *, as_of_date=None
    ) -> StockScreenResultOut:
        self.calls.append((screen_type, params))
        return StockScreenResultOut(
            screen_type=screen_type,
            total=len(self._items),
            items=self._items,
        )


class _MockBotSender:
    def __init__(self) -> None:
        self.cards_sent: list[tuple[str, Any]] = []
        self.texts_sent: list[tuple[str, str]] = []

    async def send_card(self, chat_id: str, card) -> str | None:
        self.cards_sent.append((chat_id, card))
        return "card-id"

    async def send_text(self, chat_id: str, text: str) -> str | None:
        self.texts_sent.append((chat_id, text))
        return "msg-id"


def _make_items() -> list[StockScreenItemOut]:
    return [
        StockScreenItemOut(
            symbol="600519",
            name="贵州茅台",
            market="SH",
            industry=None,
            latest_close=1700.0,
            return_5d_pct=2.5,
            return_20d_pct=8.4,
            volume_ratio_5d=1.4,
            trend_bias="bullish",
            match_reason="20日动量+均线多头",
        ),
        StockScreenItemOut(
            symbol="000858",
            name="五粮液",
            market="SZ",
            industry=None,
            latest_close=180.0,
            return_5d_pct=1.2,
            return_20d_pct=5.6,
            volume_ratio_5d=1.3,
            trend_bias="bullish",
            match_reason="放量上行",
        ),
    ]


# ---------------------------------------------------------------------------
# Cron parsing
# ---------------------------------------------------------------------------


def test_cron_matches_basic_weekly_schedule() -> None:
    expr = "30 9 * * 1"  # Monday 09:30
    monday_0930 = datetime(2026, 6, 1, 9, 30)  # 2026-06-01 is a Monday.
    assert cron_matches(expr, monday_0930)
    tuesday_0930 = datetime(2026, 6, 2, 9, 30)
    assert not cron_matches(expr, tuesday_0930)
    monday_0931 = datetime(2026, 6, 1, 9, 31)
    assert not cron_matches(expr, monday_0931)


def test_cron_supports_step_and_range() -> None:
    expr = "*/15 9-11 * * *"
    assert cron_matches(expr, datetime(2026, 6, 1, 10, 0))
    assert cron_matches(expr, datetime(2026, 6, 1, 11, 45))
    assert not cron_matches(expr, datetime(2026, 6, 1, 12, 0))
    assert not cron_matches(expr, datetime(2026, 6, 1, 9, 7))


def test_cron_invalid_expression_raises() -> None:
    with pytest.raises(CronParseError):
        parse_cron("not-a-cron")


def test_is_due_respects_last_dispatched() -> None:
    expr = "30 9 * * 1"
    monday_0930 = datetime(2026, 6, 1, 9, 30)
    # First time: due.
    assert is_due(expr, now=monday_0930, last_dispatched_at=None)
    # If we already dispatched at exactly the same minute, not due again.
    assert not is_due(expr, now=monday_0930, last_dispatched_at=monday_0930)
    # If we dispatched a minute later (e.g. clock skew), still not due.
    assert not is_due(
        expr,
        now=monday_0930,
        last_dispatched_at=monday_0930 + timedelta(minutes=1),
    )


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_and_list_subscription() -> None:
    repo = _InMemoryRepo()
    market = _StubMarketDataService([])
    bot = _MockBotSender()
    svc = SubscriptionService(
        repo=repo,  # type: ignore[arg-type]
        market_data=market,  # type: ignore[arg-type]
        bot_sender=bot,
    )

    out = await svc.create_subscription(
        SubscriptionCreate(
            user_id="u1",
            strategy_key="strong_uptrend",
            params={"min_return_20d_pct": 5},
            bot_channel_id="oc_chat_xyz",
            schedule="30 9 * * 1",
        )
    )
    assert out.user_id == "u1"
    assert out.strategy_key == "strong_uptrend"
    assert out.params == {"min_return_20d_pct": 5}
    assert out.bot_channel_id == "oc_chat_xyz"
    assert out.enabled is True

    listed = await svc.list_subscriptions()
    assert len(listed) == 1
    assert listed[0].id == out.id

    by_user = await svc.list_subscriptions(user_id="u1")
    assert len(by_user) == 1
    by_other = await svc.list_subscriptions(user_id="u2")
    assert by_other == []


@pytest.mark.asyncio
async def test_create_rejects_invalid_cron() -> None:
    repo = _InMemoryRepo()
    svc = SubscriptionService(
        repo=repo,  # type: ignore[arg-type]
        market_data=_StubMarketDataService([]),  # type: ignore[arg-type]
        bot_sender=_MockBotSender(),
    )
    with pytest.raises(BadRequestError):
        await svc.create_subscription(
            SubscriptionCreate(
                user_id="u1",
                strategy_key="strong_uptrend",
                bot_channel_id="oc",
                schedule="not a cron",
            )
        )


@pytest.mark.asyncio
async def test_delete_subscription() -> None:
    repo = _InMemoryRepo()
    svc = SubscriptionService(
        repo=repo,  # type: ignore[arg-type]
        market_data=_StubMarketDataService([]),  # type: ignore[arg-type]
        bot_sender=_MockBotSender(),
    )
    created = await svc.create_subscription(
        SubscriptionCreate(
            user_id="u1",
            strategy_key="strong_uptrend",
            bot_channel_id="oc",
            schedule="30 9 * * 1",
        )
    )
    await svc.delete_subscription(created.id)
    assert await svc.list_subscriptions() == []

    with pytest.raises(NotFoundError):
        await svc.delete_subscription("nonexistent")


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dispatch_due_pushes_card_to_bot() -> None:
    repo = _InMemoryRepo()
    market = _StubMarketDataService(_make_items())
    bot = _MockBotSender()
    svc = SubscriptionService(
        repo=repo,  # type: ignore[arg-type]
        market_data=market,  # type: ignore[arg-type]
        bot_sender=bot,
    )

    # Create one due (Monday 09:30) and one not-due (Tuesday) subscription.
    sub_due = StrategySubscription(
        id="sub-due",
        user_id="u1",
        strategy_key="strong_uptrend",
        params_json=json.dumps({"min_return_20d_pct": 5}),
        bot_channel_id="oc_due",
        schedule="30 9 * * 1",
        enabled=True,
        created_at=datetime.now(),
        last_dispatched_at=None,
    )
    sub_not_due = StrategySubscription(
        id="sub-not-due",
        user_id="u2",
        strategy_key="volume_breakout",
        params_json=None,
        bot_channel_id="oc_skip",
        schedule="30 9 * * 2",  # Tuesday only
        enabled=True,
        created_at=datetime.now(),
        last_dispatched_at=None,
    )
    sub_disabled = StrategySubscription(
        id="sub-off",
        user_id="u3",
        strategy_key="strong_uptrend",
        params_json=None,
        bot_channel_id="oc_off",
        schedule="30 9 * * 1",
        enabled=False,
        created_at=datetime.now(),
        last_dispatched_at=None,
    )
    await repo.create(sub_due)
    await repo.create(sub_not_due)
    await repo.create(sub_disabled)

    # 2026-06-01 is a Monday.
    now = datetime(2026, 6, 1, 9, 30)
    dispatched = await svc.dispatch_due(now=now)

    assert dispatched == ["sub-due"]
    assert len(bot.cards_sent) == 1
    chat_id, card = bot.cards_sent[0]
    assert chat_id == "oc_due"
    # Card payload must contain the picks.
    field_labels = [e.get("label", "") for e in card.elements if e.get("type") == "field"]
    assert any("600519" in label for label in field_labels)
    assert any("000858" in label for label in field_labels)
    # Card title should reference the strategy.
    assert "strong_uptrend" in card.title

    # Second-tier check: market_data was called with the strategy_key and the
    # filtered params we passed.
    assert market.calls
    call_strategy, params = market.calls[0]
    assert call_strategy == "strong_uptrend"
    assert params is not None
    assert params.min_return_20d_pct == 5

    # last_dispatched_at should now be set so it doesn't refire.
    assert sub_due.last_dispatched_at == now
    second_pass = await svc.dispatch_due(now=now)
    assert second_pass == []
    assert len(bot.cards_sent) == 1  # no new card


@pytest.mark.asyncio
async def test_dispatch_due_skips_invalid_cron_subscription() -> None:
    repo = _InMemoryRepo()
    bot = _MockBotSender()
    svc = SubscriptionService(
        repo=repo,  # type: ignore[arg-type]
        market_data=_StubMarketDataService(_make_items()),  # type: ignore[arg-type]
        bot_sender=bot,
    )
    bad = StrategySubscription(
        id="bad",
        user_id="u",
        strategy_key="strong_uptrend",
        params_json=None,
        bot_channel_id="oc",
        schedule="garbage",
        enabled=True,
        created_at=datetime.now(),
        last_dispatched_at=None,
    )
    await repo.create(bad)

    dispatched = await svc.dispatch_due(now=datetime(2026, 6, 1, 9, 30))
    assert dispatched == []
    assert bot.cards_sent == []
