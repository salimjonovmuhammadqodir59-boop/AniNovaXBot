from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Subscription, TransactionType, User, VipPlan
from app.services.coin_service import change_balance, InsufficientCoinsError


def is_vip_active(user: User) -> bool:
    if not user.is_vip or user.vip_expires_at is None:
        return False
    return user.vip_expires_at > datetime.now(timezone.utc)


def vip_days_left(user: User) -> int:
    if not is_vip_active(user):
        return 0
    return max(0, (user.vip_expires_at - datetime.now(timezone.utc)).days)


async def grant_vip_days(session: AsyncSession, user: User, days: int) -> User:
    now = datetime.now(timezone.utc)
    base = user.vip_expires_at if (user.vip_expires_at and user.vip_expires_at > now) else now
    user.vip_expires_at = base + timedelta(days=days)
    user.is_vip = True
    await session.commit()
    await session.refresh(user)
    return user


async def buy_vip_with_coins(session: AsyncSession, user: User, plan: VipPlan) -> User:
    if not plan.price_coins:
        raise ValueError("Bu reja tangalar orqali sotib olinmaydi")
    try:
        user = await change_balance(
            session, user, -plan.price_coins, TransactionType.VIP_PURCHASE_COINS,
            note=f"VIP {plan.days} kun (tangalar orqali)",
        )
    except InsufficientCoinsError:
        raise
    user = await grant_vip_days(session, user, plan.days)
    session.add(Subscription(user_id=user.id, plan_id=plan.id, expires_at=user.vip_expires_at, paid_with="coins"))
    await session.commit()
    return user


async def activate_vip_after_payment(session: AsyncSession, user: User, plan: VipPlan,
                                      provider_payment_id: str | None = None) -> User:
    await change_balance(
        session, user, 0, TransactionType.VIP_PURCHASE_MONEY,
        note=f"VIP {plan.days} kun (pul orqali)",
        money_amount=plan.price_money, currency=plan.currency,
        provider_payment_id=provider_payment_id,
    )
    user = await grant_vip_days(session, user, plan.days)
    session.add(Subscription(user_id=user.id, plan_id=plan.id, expires_at=user.vip_expires_at, paid_with="money"))
    await session.commit()
    return user
