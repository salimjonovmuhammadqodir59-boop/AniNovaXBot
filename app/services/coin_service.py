from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Transaction, TransactionType, User


class InsufficientCoinsError(Exception):
    pass


async def get_or_create_user(session: AsyncSession, tg_id: int, username: str | None, full_name: str | None,
                              referred_by: int | None = None) -> User:
    user = await session.get(User, tg_id)
    if user is None:
        user = User(id=tg_id, username=username, full_name=full_name, referred_by=referred_by)
        session.add(user)
        await session.commit()
        await session.refresh(user)
    return user


async def change_balance(session: AsyncSession, user: User, delta: int, tx_type: TransactionType,
                          note: str | None = None, money_amount: int | None = None,
                          currency: str | None = None, provider_payment_id: str | None = None, commit: bool = True) -> User:
    """Single choke point for every coin balance change -- always logged as a Transaction."""
    new_balance = user.coins + delta
    if new_balance < 0:
        raise InsufficientCoinsError("Balansda yetarli tanga yo'q")

    user.coins = new_balance
    if delta < 0:
        user.total_spent_coins += abs(delta)

    session.add(Transaction(
        user_id=user.id, type=tx_type, coins_delta=delta,
        money_amount=money_amount, currency=currency,
        provider_payment_id=provider_payment_id, note=note,
    ))
    if commit:
        await session.commit()
        await session.refresh(user)
    else:
        await session.flush()
    return user
