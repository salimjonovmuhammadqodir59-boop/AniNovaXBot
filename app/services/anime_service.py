from __future__ import annotations

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database.models import Anime, Episode, Genre, Rating, WatchHistory, User
from app.database.settings_repo import get_setting
from app.services.coin_service import change_balance
from app.database.models import TransactionType
from app.services.vip_service import is_vip_active


async def get_anime_by_id(session: AsyncSession, anime_id: int) -> Anime | None:
    result = await session.execute(
        select(Anime).options(selectinload(Anime.genres), selectinload(Anime.episodes)).where(Anime.id == anime_id)
    )
    return result.scalar_one_or_none()


async def all_animes_paginated(session: AsyncSession, page: int = 0, page_size: int = 8) -> list[Anime]:
    result = await session.execute(
        select(Anime).where(Anime.is_published.is_(True))
        .order_by(Anime.title).offset(page * page_size).limit(page_size)
    )
    return list(result.scalars().all())


async def find_by_image_hash(session: AsyncSession, image_bytes: bytes, max_distance: int = 10) -> Anime | None:
    """Reverse-image lookup using a perceptual hash (dHash) matched against stored poster hashes."""
    import io
    import imagehash
    from PIL import Image

    try:
        img = Image.open(io.BytesIO(image_bytes))
        query_hash = imagehash.dhash(img)
    except Exception:
        return None

    result = await session.execute(select(Anime).where(Anime.poster_dhash.is_not(None)))
    best_match: Anime | None = None
    best_distance = max_distance + 1
    for anime in result.scalars().all():
        try:
            stored_hash = imagehash.hex_to_hash(anime.poster_dhash)
        except (TypeError, ValueError):
            continue
        distance = query_hash - stored_hash
        if distance < best_distance:
            best_distance = distance
            best_match = anime
    return best_match if best_distance <= max_distance else None


async def compute_poster_dhash(image_bytes: bytes) -> str | None:
    import io
    import imagehash
    from PIL import Image

    try:
        img = Image.open(io.BytesIO(image_bytes))
        return str(imagehash.dhash(img))
    except Exception:
        return None


async def find_by_code(session: AsyncSession, code: int) -> Anime | None:
    result = await session.execute(
        select(Anime).options(selectinload(Anime.genres)).where(Anime.code == code, Anime.is_published.is_(True))
    )
    return result.scalar_one_or_none()


async def fuzzy_search_by_name(session: AsyncSession, query: str, limit: int = 20) -> list[Anime]:
    from rapidfuzz import process, fuzz

    result = await session.execute(select(Anime).where(Anime.is_published.is_(True)))
    all_animes = result.scalars().all()
    if not all_animes:
        return []

    choices = {a.id: a.title for a in all_animes}
    matches = process.extract(query, choices, scorer=fuzz.WRatio, limit=limit, score_cutoff=55)
    by_id = {a.id: a for a in all_animes}
    return [by_id[match[2]] for match in matches]


async def list_by_genre(session: AsyncSession, genre_id: int, page: int = 0, page_size: int = 8) -> list[Anime]:
    result = await session.execute(
        select(Anime)
        .join(Anime.genres)
        .where(Genre.id == genre_id, Anime.is_published.is_(True))
        .offset(page * page_size)
        .limit(page_size)
    )
    return list(result.scalars().unique().all())


async def latest_animes(session: AsyncSession, page: int = 0, page_size: int = 8) -> list[Anime]:
    result = await session.execute(
        select(Anime).where(Anime.is_published.is_(True))
        .order_by(Anime.created_at.desc()).offset(page * page_size).limit(page_size)
    )
    return list(result.scalars().all())


async def top_rated(session: AsyncSession, page: int = 0, page_size: int = 8) -> list[Anime]:
    result = await session.execute(
        select(Anime).where(Anime.is_published.is_(True), Anime.rating_count > 0)
        .order_by((Anime.rating_sum / func.nullif(Anime.rating_count, 0)).desc())
        .offset(page * page_size).limit(page_size)
    )
    return list(result.scalars().all())


async def most_viewed(session: AsyncSession, page: int = 0, page_size: int = 8) -> list[Anime]:
    result = await session.execute(
        select(Anime).where(Anime.is_published.is_(True))
        .order_by(Anime.views.desc()).offset(page * page_size).limit(page_size)
    )
    return list(result.scalars().all())


async def get_episode(session: AsyncSession, anime_id: int, number: int) -> Episode | None:
    result = await session.execute(
        select(Episode).where(Episode.anime_id == anime_id, Episode.number == number)
    )
    return result.scalar_one_or_none()


async def has_already_paid(session: AsyncSession, user_id: int, episode_id: int) -> bool:
    result = await session.execute(
        select(WatchHistory).where(WatchHistory.user_id == user_id, WatchHistory.episode_id == episode_id)
    )
    return result.scalar_one_or_none() is not None


class NotEnoughCoinsError(Exception):
    pass


async def preview_watch_price(session: AsyncSession, user: User, episode: Episode) -> int:
    """Same rules as unlock_episode but read-only, used to decide whether to show a pay screen."""
    if episode.is_free:
        return 0
    if episode.vip_free and is_vip_active(user):
        return 0
    watch_mode = await get_setting(session, "watch_access_mode")
    if watch_mode == "pay_once" and await has_already_paid(session, user.id, episode.id):
        return 0
    return episode.price_coins


async def unlock_episode(session: AsyncSession, user: User, episode: Episode) -> int:
    """Handles the coin deduction rules for watching an episode.
    Returns the number of coins actually charged (0 if free/VIP/already paid)."""
    if episode.is_free:
        price = 0
    elif episode.vip_free and is_vip_active(user):
        price = 0
    else:
        watch_mode = await get_setting(session, "watch_access_mode")  # pay_every_time | pay_once
        if watch_mode == "pay_once" and await has_already_paid(session, user.id, episode.id):
            price = 0
        else:
            price = episode.price_coins

    if price > 0:
        if user.coins < price:
            raise NotEnoughCoinsError()
        await change_balance(
            session, user, -price, TransactionType.COIN_SPEND,
            note=f"Anime #{episode.anime_id} — {episode.number}-qism",
            commit=False,
        )

    episode.views += 1
    # Keep anime-level statistics in sync with episode-level views.
    anime = await session.get(Anime, episode.anime_id)
    if anime is not None:
        anime.views += 1
    user.total_views += 1

    # watch_history is also the pay-once unlock marker, so it has a unique
    # (user, episode) key. Reuse the row on subsequent watches instead of
    # violating that constraint.
    result = await session.execute(
        select(WatchHistory).where(
            WatchHistory.user_id == user.id,
            WatchHistory.episode_id == episode.id,
        )
    )
    history = result.scalar_one_or_none()
    if history is None:
        session.add(WatchHistory(user_id=user.id, episode_id=episode.id, paid_coins=price))
    else:
        history.paid_coins = max(history.paid_coins, price)
        from datetime import datetime, timezone
        history.watched_at = datetime.now(timezone.utc)

    await session.flush()
    return price


async def rate_anime(session: AsyncSession, user_id: int, anime: Anime, stars: int) -> Anime:
    stars = max(1, min(5, stars))
    scaled = stars * 10
    result = await session.execute(
        select(Rating).where(Rating.user_id == user_id, Rating.anime_id == anime.id)
    )
    existing = result.scalar_one_or_none()
    if existing:
        anime.rating_sum += scaled - (existing.stars * 10)
        existing.stars = stars
    else:
        anime.rating_sum += scaled
        anime.rating_count += 1
        session.add(Rating(user_id=user_id, anime_id=anime.id, stars=stars))
    await session.commit()
    await session.refresh(anime)
    return anime
