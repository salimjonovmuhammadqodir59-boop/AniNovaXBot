from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Setting

# Defaults used the first time a key is read and nothing is in DB yet.
# Admins can change all of these live via the admin panel -- nothing here
# is hard-coded into business logic, it only seeds the settings table.
DEFAULTS: dict[str, object] = {
    "watch_access_mode": "pay_every_time",   # or "pay_once"
    "daily_bonus_base": 10,
    "daily_bonus_streak": [10, 15, 20, 30, 45, 70, 100],  # day1..day7
    "daily_bonus_cooldown_hours": 24,
    "referral_bonus_coins": 50,
    "coins_to_vip_threshold": 500,
    "coins_to_vip_days": 30,
    "default_episode_price": 5,
    "default_episode_free": False,
}


async def get_setting(session: AsyncSession, key: str):
    row = await session.get(Setting, key)
    if row is None:
        return DEFAULTS.get(key)
    try:
        return json.loads(row.value)
    except (json.JSONDecodeError, TypeError):
        return row.value


async def set_setting(session: AsyncSession, key: str, value) -> None:
    row = await session.get(Setting, key)
    payload = json.dumps(value)
    if row is None:
        session.add(Setting(key=key, value=payload))
    else:
        row.value = payload
    await session.commit()


async def all_settings(session: AsyncSession) -> dict:
    result = await session.execute(select(Setting))
    stored = {row.key: row.value for row in result.scalars()}
    merged = dict(DEFAULTS)
    for k, v in stored.items():
        try:
            merged[k] = json.loads(v)
        except (json.JSONDecodeError, TypeError):
            merged[k] = v
    return merged
