"""Subscription service: CRUD + dispatch logic.

Dispatch flow:
1. Load enabled subscriptions.
2. Filter to those due based on the cron schedule and ``last_dispatched_at``.
3. For each due subscription, run the screener via ``MarketDataService``.
4. Build a Feishu screen-result card and push via the registered bot adapter.
5. Update ``last_dispatched_at`` so the same minute slot doesn't re-fire.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from uuid import uuid4

from loguru import logger

from app.core.exceptions import BadRequestError, NotFoundError
from app.modules.market_data.schemas import StockScreenParams
from app.modules.market_data.service import MarketDataService
from app.modules.strategies.subscriptions.cron import (
    CronParseError,
    is_due,
    parse_cron,
)
from app.modules.strategies.subscriptions.models import StrategySubscription
from app.modules.strategies.subscriptions.repository import (
    SubscriptionRepository,
)
from app.modules.strategies.subscriptions.schemas import (
    SubscriptionCreate,
    SubscriptionOut,
)


def _to_out(sub: StrategySubscription) -> SubscriptionOut:
    raw_params = sub.params_json
    params: dict[str, Any] | None = None
    if raw_params:
        try:
            params = json.loads(raw_params)
        except json.JSONDecodeError:
            params = None
    return SubscriptionOut(
        id=sub.id,
        user_id=sub.user_id,
        strategy_key=sub.strategy_key,
        params=params,
        bot_channel_id=sub.bot_channel_id,
        schedule=sub.schedule,
        enabled=sub.enabled,
        last_dispatched_at=sub.last_dispatched_at,
        created_at=sub.created_at,
    )


class SubscriptionService:
    def __init__(
        self,
        repo: SubscriptionRepository | None = None,
        market_data: MarketDataService | None = None,
        bot_sender=None,
    ) -> None:
        self.repo = repo or SubscriptionRepository()
        self.market_data = market_data or MarketDataService()
        # Optional injection for tests; production resolves lazily inside dispatch.
        self._bot_sender = bot_sender

    # ----- CRUD -----

    async def list_subscriptions(self, *, user_id: str | None = None) -> list[SubscriptionOut]:
        subs = await self.repo.list_all(user_id=user_id)
        return [_to_out(s) for s in subs]

    async def create_subscription(self, payload: SubscriptionCreate) -> SubscriptionOut:
        try:
            parse_cron(payload.schedule)
        except CronParseError as exc:
            raise BadRequestError(f"Invalid schedule: {exc}") from exc

        sub = StrategySubscription(
            id=str(uuid4()),
            user_id=payload.user_id,
            strategy_key=payload.strategy_key,
            params_json=(json.dumps(payload.params) if payload.params is not None else None),
            bot_channel_id=payload.bot_channel_id,
            schedule=payload.schedule,
            enabled=payload.enabled,
            last_dispatched_at=None,
            created_at=datetime.now(),
        )
        created = await self.repo.create(sub)
        return _to_out(created)

    async def delete_subscription(self, sub_id: str) -> None:
        ok = await self.repo.delete(sub_id)
        if not ok:
            raise NotFoundError(f"Subscription {sub_id} not found")

    # ----- Dispatch -----

    def _resolve_bot_sender(self):
        if self._bot_sender is not None:
            return self._bot_sender
        # Late-bound resolution to avoid pulling Feishu credentials at import.
        from app.modules.bot.adapters.feishu.adapter import FeishuAdapter

        return FeishuAdapter()

    async def dispatch_due(self, *, now: datetime | None = None) -> list[str]:
        """Fire all subscriptions whose schedule is due now.

        Returns the list of subscription ids that were dispatched.
        """
        now = now or datetime.now()
        subs = await self.repo.list_all(enabled=True)
        dispatched: list[str] = []
        for sub in subs:
            try:
                due = is_due(
                    sub.schedule,
                    now=now,
                    last_dispatched_at=sub.last_dispatched_at,
                )
            except CronParseError:
                logger.warning(f"subscription {sub.id} has invalid cron {sub.schedule!r}; skipping")
                continue
            if not due:
                continue
            try:
                await self._dispatch_one(sub)
                await self.repo.update_dispatched_at(sub.id, now)
                dispatched.append(sub.id)
            except Exception as exc:  # pragma: no cover (defensive)
                logger.exception(f"subscription dispatch failed id={sub.id} err={exc}")
        return dispatched

    async def _dispatch_one(self, sub: StrategySubscription) -> None:
        """Run the screener for the subscription and push a card to the bot."""
        params_dict: dict[str, Any] = {}
        if sub.params_json:
            try:
                raw = json.loads(sub.params_json)
                if isinstance(raw, dict):
                    params_dict = raw
            except json.JSONDecodeError:
                params_dict = {}

        # Filter to fields accepted by StockScreenParams.
        allowed = set(StockScreenParams.model_fields.keys())
        screen_params = StockScreenParams(**{k: v for k, v in params_dict.items() if k in allowed})

        result = await self.market_data.screen_stocks(sub.strategy_key, screen_params)

        card = self.build_signal_card(sub, result)
        sender = self._resolve_bot_sender()
        await sender.send_card(sub.bot_channel_id, card)

    @staticmethod
    def build_signal_card(sub: StrategySubscription, result) -> Any:
        """Build a Feishu CardMessage describing the strategy signal.

        Imported lazily to keep the module importable without optional bot deps.
        """
        from app.modules.bot.adapters.base import CardMessage

        title = f"策略信号 · {sub.strategy_key}"
        message = f"用户 {sub.user_id} · 命中 {result.total} 只 · 展示前 {len(result.items)} 只"
        card = CardMessage(title=title, subtitle=message, header_color="blue")
        if not result.items:
            card.add_text("当前无匹配标的，请稍后再看。")
            return card
        for item in result.items[:10]:
            label = f"{item.symbol} {item.name}"
            value_parts: list[str] = []
            if item.return_20d_pct is not None:
                value_parts.append(f"20d {item.return_20d_pct:+.2f}%")
            if item.match_reason:
                value_parts.append(item.match_reason)
            card.add_field(label, " · ".join(value_parts) or "-")
        card.add_note(f"订阅 {sub.id} · 触发时间 {datetime.now().isoformat()}")
        return card
