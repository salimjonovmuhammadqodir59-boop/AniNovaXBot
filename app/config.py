from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    BOT_TOKEN: str
    BOT_USERNAME: str = "AniNovaXBot"
    ADMIN_IDS: str = ""

    DATABASE_URL: str

    def model_post_init(self, __context) -> None:
        if self.DATABASE_URL.startswith("postgresql://"):
            object.__setattr__(self, "DATABASE_URL", self.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1))
        elif self.DATABASE_URL.startswith("postgres://"):
            object.__setattr__(self, "DATABASE_URL", self.DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1))

    USE_WEBHOOK: bool = False
    WEBHOOK_URL: str = ""
    WEBHOOK_PATH: str = "/webhook"
    WEBAPP_HOST: str = "0.0.0.0"
    WEBAPP_PORT: int = 10000

    PAYMENT_PROVIDER_TOKEN: str = ""  # Telegram native payments (Stripe/Payme-as-Telegram-provider), optional

    # ----- Payme (https://developer.help.paycom.uz) -----
    PAYME_MERCHANT_ID: str = ""
    PAYME_SECRET_KEY: str = ""
    PAYME_TEST_MODE: bool = True

    # ----- Click (https://docs.click.uz) -----
    CLICK_MERCHANT_ID: str = ""
    CLICK_SERVICE_ID: str = ""
    CLICK_SECRET_KEY: str = ""
    CLICK_MERCHANT_USER_ID: str = ""

    # ----- Uzum Bank (https://developer.uzumbank.uz) -----
    UZUM_MERCHANT_ID: str = ""
    UZUM_SECRET_KEY: str = ""

    PAYMENTS_WEBAPP_HOST: str = "0.0.0.0"
    PAYMENTS_WEBAPP_PORT: int = 10001

    DEFAULT_LANGUAGE: str = "uz"
    LOG_LEVEL: str = "INFO"

    @property
    def admin_ids(self) -> set[int]:
        return {int(x) for x in self.ADMIN_IDS.split(",") if x.strip().isdigit()}

    @property
    def payment_test_mode(self) -> bool:
        return not bool(self.PAYMENT_PROVIDER_TOKEN)

    @property
    def full_webhook_url(self) -> str:
        return f"{self.WEBHOOK_URL.rstrip('/')}{self.WEBHOOK_PATH}"


settings = Settings()
