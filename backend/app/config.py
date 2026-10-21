from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

from .slots import SlotRules


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    company_name: str = "Lextria Research"
    frontend_base_url: str = "http://localhost:5173"
    cors_origins: str = "http://localhost:5173"

    # Database entry point: any SQLAlchemy URL.
    database_url: str = "sqlite:///./consultation.db"

    timezone: str = "Asia/Kolkata"
    slot_times: str = "10:00,14:00,17:00"
    slot_duration_minutes: int = 60
    working_days: str = "0,1,2,3,4,5"
    min_days_ahead: int = 1
    booking_horizon_days: int = 30
    hold_minutes: int = 15
    change_cutoff_hours: int = 24
    max_reschedules: int = 1
    default_fee_inr: int = 10000

    coupon_valid_hours: int = 24
    coupon_lock_to_email: bool = True

    razorpay_key_id: str = ""
    razorpay_key_secret: str = ""
    razorpay_webhook_secret: str = ""

    google_client_id: str = ""
    google_client_secret: str = ""
    google_refresh_token: str = ""
    google_calendar_id: str = "primary"
    google_send_updates: str = "all"

    smtp_host: str = "smtppro.zoho.in"
    smtp_port: int = 465
    smtp_username: str = ""
    smtp_password: str = ""
    mail_from: str = "info@lextria.in"
    mail_from_name: str = "Lextria Research"

    @property
    def razorpay_mock(self) -> bool:
        return not (self.razorpay_key_id and self.razorpay_key_secret)

    @property
    def google_enabled(self) -> bool:
        return bool(self.google_client_id and self.google_client_secret and self.google_refresh_token)

    @property
    def smtp_enabled(self) -> bool:
        return bool(self.smtp_username and self.smtp_password)

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    def rules(self) -> SlotRules:
        return SlotRules(
            slot_times=tuple(t.strip() for t in self.slot_times.split(",") if t.strip()),
            duration_minutes=self.slot_duration_minutes,
            working_days=frozenset(int(d) for d in self.working_days.split(",") if d.strip()),
            min_days_ahead=self.min_days_ahead,
            horizon_days=self.booking_horizon_days,
            timezone=self.timezone,
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()