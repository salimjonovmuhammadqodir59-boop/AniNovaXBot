from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import (
    BigInteger, Boolean, DateTime, Enum, ForeignKey, Integer, Numeric,
    String, Text, UniqueConstraint, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


# ---------------------------------------------------------------- enums ----
class WatchAccessMode(str, enum.Enum):
    PAY_EVERY_TIME = "pay_every_time"
    PAY_ONCE = "pay_once"


class TransactionType(str, enum.Enum):
    COIN_PURCHASE = "coin_purchase"
    COIN_SPEND = "coin_spend"
    ADMIN_GRANT = "admin_grant"
    ADMIN_DEDUCT = "admin_deduct"
    REFERRAL_BONUS = "referral_bonus"
    DAILY_BONUS = "daily_bonus"
    VIP_PURCHASE_COINS = "vip_purchase_coins"
    VIP_PURCHASE_MONEY = "vip_purchase_money"


class BroadcastStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


# ---------------------------------------------------------------- users ----
class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)  # telegram_id
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    coins: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    is_vip: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    vip_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    is_banned: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    referred_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=True)

    bonus_streak: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    last_bonus_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    total_spent_coins: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    total_views: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    language: Mapped[str] = mapped_column(String(8), default="uz", server_default="uz")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_active_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    favorites: Mapped[list["Favorite"]] = relationship(back_populates="user")


class AdminLog(Base):
    __tablename__ = "admin_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    admin_id: Mapped[int] = mapped_column(BigInteger, index=True)
    action: Mapped[str] = mapped_column(String(128))
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ---------------------------------------------------------------- catalog --
class Genre(Base):
    __tablename__ = "genres"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)  # e.g. "⚔️ Jangari"


anime_genre_table = "anime_genres"


class AnimeGenre(Base):
    __tablename__ = anime_genre_table

    anime_id: Mapped[int] = mapped_column(ForeignKey("animes.id", ondelete="CASCADE"), primary_key=True)
    genre_id: Mapped[int] = mapped_column(ForeignKey("genres.id", ondelete="CASCADE"), primary_key=True)


class Anime(Base):
    __tablename__ = "animes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[int] = mapped_column(Integer, unique=True, index=True)  # 🔢 short numeric code

    title: Mapped[str] = mapped_column(String(255), index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    poster_file_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    banner_file_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    poster_dhash: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)  # for image search

    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    quality: Mapped[str | None] = mapped_column(String(32), nullable=True)  # "720p / 1080p"

    rating_sum: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    rating_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    views: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    is_vip_only: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    is_published: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    genres: Mapped[list[Genre]] = relationship(secondary=anime_genre_table)
    episodes: Mapped[list["Episode"]] = relationship(back_populates="anime", order_by="Episode.number")

    @property
    def average_rating(self) -> float:
        # rating_sum accumulates (stars * 10) per vote so fractional seed ratings (e.g. an
        # admin-entered 4.8) stay exact while still using plain Integer columns.
        return round((self.rating_sum / 10) / self.rating_count, 1) if self.rating_count else 0.0


class Episode(Base):
    __tablename__ = "episodes"
    __table_args__ = (UniqueConstraint("anime_id", "number", name="uq_anime_episode_number"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    anime_id: Mapped[int] = mapped_column(ForeignKey("animes.id", ondelete="CASCADE"), index=True)
    number: Mapped[int] = mapped_column(Integer)

    video_file_id: Mapped[str] = mapped_column(String(255))
    quality: Mapped[str | None] = mapped_column(String(32), nullable=True)

    price_coins: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    is_free: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    vip_free: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    views: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    anime: Mapped[Anime] = relationship(back_populates="episodes")


# ---------------------------------------------------------------- user data
class Favorite(Base):
    __tablename__ = "favorites"
    __table_args__ = (UniqueConstraint("user_id", "anime_id", name="uq_user_favorite"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    anime_id: Mapped[int] = mapped_column(ForeignKey("animes.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped[User] = relationship(back_populates="favorites")


class WatchHistory(Base):
    __tablename__ = "watch_history"
    __table_args__ = (UniqueConstraint("user_id", "episode_id", name="uq_user_episode_watch"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    episode_id: Mapped[int] = mapped_column(ForeignKey("episodes.id", ondelete="CASCADE"), index=True)
    paid_coins: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    watched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Rating(Base):
    __tablename__ = "ratings"
    __table_args__ = (UniqueConstraint("user_id", "anime_id", name="uq_user_anime_rating"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    anime_id: Mapped[int] = mapped_column(ForeignKey("animes.id", ondelete="CASCADE"), index=True)
    stars: Mapped[int] = mapped_column(Integer)  # 1..5
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ---------------------------------------------------------------- economy --
class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    type: Mapped[TransactionType] = mapped_column(Enum(TransactionType))
    coins_delta: Mapped[int] = mapped_column(Integer)  # positive = credit, negative = debit
    money_amount: Mapped[int | None] = mapped_column(Integer, nullable=True)  # in tiyin/kopeks or smallest unit
    currency: Mapped[str | None] = mapped_column(String(8), nullable=True)
    provider_payment_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CoinPackage(Base):
    __tablename__ = "coin_packages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    coins: Mapped[int] = mapped_column(Integer)
    price: Mapped[int] = mapped_column(Integer)  # smallest currency unit (e.g. so'm)
    currency: Mapped[str] = mapped_column(String(8), default="UZS", server_default="UZS")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")


class VipPlan(Base):
    __tablename__ = "vip_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    days: Mapped[int] = mapped_column(Integer)
    price_coins: Mapped[int | None] = mapped_column(Integer, nullable=True)
    price_money: Mapped[int | None] = mapped_column(Integer, nullable=True)
    currency: Mapped[str] = mapped_column(String(8), default="UZS", server_default="UZS")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")


class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    plan_id: Mapped[int | None] = mapped_column(ForeignKey("vip_plans.id"), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    paid_with: Mapped[str] = mapped_column(String(16))  # "coins" | "money"


class DailyBonusClaim(Base):
    __tablename__ = "daily_bonuses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    streak_day: Mapped[int] = mapped_column(Integer)
    coins_awarded: Mapped[int] = mapped_column(Integer)
    claimed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Referral(Base):
    __tablename__ = "referrals"
    __table_args__ = (UniqueConstraint("invited_user_id", name="uq_referral_invited_once"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    inviter_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    invited_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    bonus_coins: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ---------------------------------------------------------------- content --
class Advertisement(Base):
    __tablename__ = "advertisements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    photo_file_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    button_text: Mapped[str | None] = mapped_column(String(64), nullable=True)
    button_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    target_audience: Mapped[str] = mapped_column(String(16), default="all", server_default="all")  # all|non_vip|new
    frequency_views: Mapped[int] = mapped_column(Integer, default=10, server_default="10")  # show every N actions
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Broadcast(Base):
    __tablename__ = "broadcasts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    admin_id: Mapped[int] = mapped_column(BigInteger)
    content_type: Mapped[str] = mapped_column(String(16))  # text|photo|video|animation
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    button_text: Mapped[str | None] = mapped_column(String(64), nullable=True)
    button_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[BroadcastStatus] = mapped_column(Enum(BroadcastStatus), default=BroadcastStatus.PENDING)
    sent_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    failed_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    total_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PaymentOrderStatus(str, enum.Enum):
    PENDING = "pending"
    PAID = "paid"
    CANCELLED = "cancelled"


class PaymentOrder(Base):
    """A pending/completed purchase created before redirecting the user to Payme/Click/Uzum.
    The gateway's webhook looks this row up by `id` (sent as the merchant account/order param)."""
    __tablename__ = "payment_orders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)  # uuid4
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(16))  # "coin_package" | "vip_plan"
    ref_id: Mapped[int] = mapped_column(Integer)  # CoinPackage.id or VipPlan.id
    provider: Mapped[str] = mapped_column(String(16))  # "payme" | "click" | "uzum" | "telegram"
    amount: Mapped[int] = mapped_column(Integer)  # in smallest currency unit (tiyin for Payme, so'm for Click/Uzum)
    status: Mapped[PaymentOrderStatus] = mapped_column(Enum(PaymentOrderStatus), default=PaymentOrderStatus.PENDING)
    provider_transaction_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PaymeTransaction(Base):
    """Mirrors Payme's own transaction lifecycle (Merchant API state machine) 1:1, keyed by Payme's
    transaction id. Kept separate from PaymentOrder because Payme may probe/retry with its own ids."""
    __tablename__ = "payme_transactions"

    payme_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    order_id: Mapped[str] = mapped_column(ForeignKey("payment_orders.id", ondelete="CASCADE"), index=True)
    amount: Mapped[int] = mapped_column(Integer)  # tiyin
    state: Mapped[int] = mapped_column(Integer, default=1)  # 1=created,2=performed,-1=cancelled,-2=cancelled after perform
    reason: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at_ms: Mapped[int] = mapped_column(BigInteger)
    perform_time_ms: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")
    cancel_time_ms: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")


class Setting(Base):
    """Generic key/value store for admin-tunable settings (coin prices, bonus amounts, watch mode, etc.)."""
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
