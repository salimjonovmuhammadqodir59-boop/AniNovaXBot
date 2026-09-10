from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import (
    CoinPackage, PaymentOrder, PaymentOrderStatus, TransactionType, User, VipPlan,
)
from app.services.coin_service import change_balance
from app.services.vip_service import grant_vip_days


async def create_order(session: AsyncSession, user: User, kind: str, ref_id: int, provider: str,
                        amount: int) -> PaymentOrder:
    order = PaymentOrder(
        id=str(uuid.uuid4()), user_id=user.id, kind=kind, ref_id=ref_id,
        provider=provider, amount=amount, status=PaymentOrderStatus.PENDING,
    )
    session.add(order)
    await session.commit()
    await session.refresh(order)
    return order


async def get_order(session: AsyncSession, order_id: str) -> PaymentOrder | None:
    return await session.get(PaymentOrder, order_id)


async def fulfil_order(session: AsyncSession, order: PaymentOrder, provider_transaction_id: str | None) -> None:
    """Credits the user once a gateway confirms a completed payment. Idempotent: a second call on an
    already-paid order is a no-op, which matters because gateways may re-send confirmation callbacks."""
    if order.status == PaymentOrderStatus.PAID:
        return

    user = await session.get(User, order.user_id)
    if user is None:
        return

    if order.kind == "coin_package":
        package = await session.get(CoinPackage, order.ref_id)
        if package is not None:
            await change_balance(
                session, user, package.coins, TransactionType.COIN_PURCHASE,
                note=f"{package.coins} tanga sotib olindi ({order.provider})",
                money_amount=order.amount, currency=package.currency,
                provider_payment_id=provider_transaction_id,
            )
    elif order.kind == "vip_plan":
        plan = await session.get(VipPlan, order.ref_id)
        if plan is not None:
            await change_balance(
                session, user, 0, TransactionType.VIP_PURCHASE_MONEY,
                note=f"VIP {plan.days} kun ({order.provider})",
                money_amount=order.amount, currency=plan.currency,
                provider_payment_id=provider_transaction_id,
            )
            await grant_vip_days(session, user, plan.days)

    order.status = PaymentOrderStatus.PAID
    order.provider_transaction_id = provider_transaction_id
    order.paid_at = datetime.now(timezone.utc)
    await session.commit()


async def cancel_order(session: AsyncSession, order: PaymentOrder) -> None:
    if order.status == PaymentOrderStatus.PENDING:
        order.status = PaymentOrderStatus.CANCELLED
        order.cancelled_at = datetime.now(timezone.utc)
        await session.commit()
