from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import DailyBonusClaim, TransactionType, User
from app.database.settings_repo import get_setting
from app.services.coin_service import change_balance


class BonusOnCooldownError(Exception):
    def __init__(self, retry_after: timedelta):
        self.retry_after = retry_after


async def claim_daily_bonus(session: AsyncSession, user: User) -> tuple[User, int, int]:
    """Returns (user, coins_awarded, new_streak_day). Raises BonusOnCooldownError if too early."""
    cooldown_hours = await get_setting(session, "daily_bonus_cooldown_hours")
    now = datetime.now(timezone.utc)

    if user.last_bonus_at is not None:
        elapsed = now - user.last_bonus_at
        cooldown = timedelta(hours=cooldown_hours)
        if elapsed < cooldown:
            raise BonusOnCooldownError(cooldown - elapsed)
        # streak continues only if claimed within 48h of the last claim, otherwise resets
        if elapsed > timedelta(hours=cooldown_hours * 2):
            user.bonus_streak = 0

    streak_table = await get_setting(session, "daily_bonus_streak")
    next_day = min(user.bonus_streak + 1, len(streak_table))
    coins = streak_table[next_day - 1]

    user.bonus_streak = next_day
    user.last_bonus_at = now
    session.add(DailyBonusClaim(user_id=user.id, streak_day=next_day, coins_awarded=coins))
    await session.commit()

    user = await change_balance(session, user, coins, TransactionType.DAILY_BONUS,
                                 note=f"Kunlik bonus (kun {next_day})")
    return user, coins, next_day
