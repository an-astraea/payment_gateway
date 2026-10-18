"""Slot rules. Pure Python (standard library only) so it can be unit-tested anywhere.

The company offers a fixed set of slots per working day (default 10:00, 14:00, 17:00 IST,
one hour each). Each slot takes exactly one booking.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class SlotRules:
    slot_times: tuple[str, ...]
    duration_minutes: int
    working_days: frozenset[int]  # 0 = Monday ... 6 = Sunday
    min_days_ahead: int  # 1 = earliest booking is tomorrow (no same-day booking)
    horizon_days: int  # how far ahead clients can book
    timezone: str = "Asia/Kolkata"

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)


def parse_hhmm(value: str) -> time:
    hours, minutes = value.strip().split(":")
    return time(int(hours), int(minutes))


def is_valid_slot_time(rules: SlotRules, hhmm: str) -> bool:
    return hhmm in rules.slot_times


def slot_start(rules: SlotRules, day: date, hhmm: str) -> datetime:
    """Timezone-aware start of a slot in the company timezone."""
    return datetime.combine(day, parse_hhmm(hhmm), tzinfo=rules.tz)


def slot_end(rules: SlotRules, day: date, hhmm: str) -> datetime:
    return slot_start(rules, day, hhmm) + timedelta(minutes=rules.duration_minutes)


def _fmt(t: datetime) -> str:
    return t.strftime("%I:%M %p").lstrip("0")


def slot_label(rules: SlotRules, hhmm: str, day: date | None = None) -> str:
    """'10:00 AM - 11:00 AM'"""
    day = day or date(2000, 1, 3)
    return f"{_fmt(slot_start(rules, day, hhmm))} - {_fmt(slot_end(rules, day, hhmm))}"


def local_today(rules: SlotRules, now_utc: datetime) -> date:
    return now_utc.astimezone(rules.tz).date()


def first_bookable_date(rules: SlotRules, now_utc: datetime) -> date:
    return local_today(rules, now_utc) + timedelta(days=rules.min_days_ahead)


def last_bookable_date(rules: SlotRules, now_utc: datetime) -> date:
    return local_today(rules, now_utc) + timedelta(days=rules.horizon_days)


def is_working_day(rules: SlotRules, day: date) -> bool:
    return day.weekday() in rules.working_days


def date_closed_reason(
    rules: SlotRules, day: date, now_utc: datetime, blocked: set[date] | frozenset[date] = frozenset()
) -> str | None:
    """None if clients may book this date, otherwise a short reason code."""
    if day < first_bookable_date(rules, now_utc):
        return "too_soon"
    if day > last_bookable_date(rules, now_utc):
        return "beyond_horizon"
    if not is_working_day(rules, day):
        return "non_working_day"
    if day in blocked:
        return "holiday"
    return None


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def to_db(dt: datetime | None) -> datetime | None:
    """Store datetimes as naive UTC (portable across SQLite, PostgreSQL, MySQL)."""
    if dt is None:
        return None
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def from_db(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc)
