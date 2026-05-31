"""HTTP API for managing strategy subscriptions."""

from __future__ import annotations

from fastapi import APIRouter, Query, status

from app.modules.strategies.subscriptions.schemas import (
    SubscriptionCreate,
    SubscriptionOut,
)
from app.modules.strategies.subscriptions.service import SubscriptionService

router = APIRouter(
    prefix="/strategies/subscriptions",
    tags=["strategies"],
)


@router.get("", response_model=list[SubscriptionOut])
async def list_subscriptions(
    user_id: str | None = Query(default=None),
) -> list[SubscriptionOut]:
    return await SubscriptionService().list_subscriptions(user_id=user_id)


@router.post("", response_model=SubscriptionOut, status_code=status.HTTP_201_CREATED)
async def create_subscription(payload: SubscriptionCreate) -> SubscriptionOut:
    return await SubscriptionService().create_subscription(payload)


@router.delete("/{subscription_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_subscription(subscription_id: str) -> None:
    await SubscriptionService().delete_subscription(subscription_id)
