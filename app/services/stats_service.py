from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import (
    Anime, Episode, Favorite, Transaction, TransactionType, User, WatchHistory,
)
from app.services.referral_service import count_referrals


async def user_stats(session: AsyncSession, user: User) -> dict:
    watched_episodes = await session.execute(
        select(func.count(WatchHistory.id)).where(WatchHistory.user_id == user.id)
    )
    distinct_animes = await session.execute(
        select(func.count(func.distinct(Episode.anime_id)))
        .join(WatchHistory, WatchHistory.episode_id == Episode.id)
        .where(WatchHistory.user_id == user.id)
    )
    bonus_total = await session.execute(
        select(func.coalesce(func.sum(Transaction.coins_delta), 0))
        .where(Transaction.user_id == user.id, Transaction.type == TransactionType.DAILY_BONUS)
    )
    referrals = await count_referrals(session, user.id)

    return {
        "animes_watched": distinct_animes.scalar_one(),
        "episodes_watched": watched_episodes.scalar_one(),
        "coins_spent": user.total_spent_coins,
        "referrals": referrals,
        "bonus_earned": bonus_total.scalar_one(),
    }


async def favorites_list(session: AsyncSession, user_id: int) -> list[Anime]:
    result = await session.execute(
        select(Anime).join(Favorite, Favorite.anime_id == Anime.id).where(Favorite.user_id == user_id)
    )
    return list(result.scalars().all())


async def admin_dashboard(session: AsyncSession) -> dict:
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    total_users = (await session.execute(select(func.count(User.id)))).scalar_one()
    active_users = (await session.execute(
        select(func.count(User.id)).where(User.last_active_at >= now - timedelta(days=7))
    )).scalar_one()
    vip_users = (await session.execute(
        select(func.count(User.id)).where(User.is_vip.is_(True), User.vip_expires_at > now)
    )).scalar_one()
    total_animes = (await session.execute(select(func.count(Anime.id)))).scalar_one()
    total_episodes = (await session.execute(select(func.count(Episode.id)))).scalar_one()
    total_views = (await session.execute(select(func.coalesce(func.sum(Anime.views), 0)))).scalar_one()
    coins_in_circulation = (await session.execute(select(func.coalesce(func.sum(User.coins), 0)))).scalar_one()

    today_revenue = (await session.execute(
        select(func.coalesce(func.sum(Transaction.money_amount), 0))
        .where(Transaction.money_amount.is_not(None), Transaction.created_at >= today_start)
    )).scalar_one()
    month_revenue = (await session.execute(
        select(func.coalesce(func.sum(Transaction.money_amount), 0))
        .where(Transaction.money_amount.is_not(None), Transaction.created_at >= month_start)
    )).scalar_one()
    total_payments = (await session.execute(
        select(func.count(Transaction.id)).where(Transaction.money_amount.is_not(None))
    )).scalar_one()

    return {
        "total_users": total_users,
        "active_users": active_users,
        "vip_users": vip_users,
        "total_animes": total_animes,
        "total_episodes": total_episodes,
        "total_views": total_views,
        "coins_in_circulation": coins_in_circulation,
        "today_revenue": today_revenue,
        "month_revenue": month_revenue,
        "total_payments": total_payments,
    }
