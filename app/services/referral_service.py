from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Referral, TransactionType, User
from app.database.settings_repo import get_setting
from app.services.coin_service import change_balance


def parse_ref_payload(start_param: str | None) -> int | None:
    if not start_param or not start_param.startswith("ref_"):
        return None
    raw = start_param.removeprefix("ref_")
    return int(raw) if raw.isdigit() else None


async def register_referral(session: AsyncSession, inviter_id: int, invited_user: User) -> bool:
    """Returns True if a referral bonus was granted."""
    if inviter_id == invited_user.id:
        return False  # can't refer yourself

    inviter = await session.get(User, inviter_id)
    if inviter is None or inviter.is_banned:
        return False

    existing = await session.execute(select(Referral).where(Referral.invited_user_id == invited_user.id))
    if existing.scalar_one_or_none() is not None:
        return False  # this user was already credited to someone once

    bonus = await get_setting(session, "referral_bonus_coins")
    session.add(Referral(inviter_id=inviter_id, invited_user_id=invited_user.id, bonus_coins=bonus))
    await session.commit()

    await change_balance(session, inviter, bonus, TransactionType.REFERRAL_BONUS,
                          note=f"Referral: {invited_user.id} taklif qilindi")
    return True


async def count_referrals(session: AsyncSession, user_id: int) -> int:
    result = await session.execute(select(Referral).where(Referral.inviter_id == user_id))
    return len(result.scalars().all())
