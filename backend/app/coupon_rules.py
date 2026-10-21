"""Coupon rules. Pure Python (standard library only) so they can be unit-tested anywhere.

- Codes look like LEX-7KQ2M (5 characters, no look-alikes such as 0/O or 1/I).
- Discounts are 25, 50, 75 or 100 percent, rounded down to whole rupees. 100% = free booking.
- A coupon is single-use and expires a set number of hours after it is generated.
"""
from __future__ import annotations

import re
import secrets
from datetime import datetime

PREFIX = "LEX-"
ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
CODE_LENGTH = 5
ALLOWED_PERCENTS = (25, 50, 75, 100)
CODE_PATTERN = re.compile(r"^LEX-[A-Z0-9]{5}$")

UNUSED, USED, EXPIRED, DEACTIVATED = "unused", "used", "expired", "deactivated"


def new_code() -> str:
    return PREFIX + "".join(secrets.choice(ALPHABET) for _ in range(CODE_LENGTH))


def normalize(code: str) -> str:
    """'  lex-7kq2m ' and 'LEX7KQ2M' both become 'LEX-7KQ2M'."""
    c = re.sub(r"\s+", "", code or "").upper()
    if c.startswith("LEX") and not c.startswith(PREFIX):
        c = PREFIX + c[3:]
    return c


def looks_valid(code: str) -> bool:
    return bool(CODE_PATTERN.match(code))


def discount_paise(fee_paise: int, percent: int) -> int:
    """Discount in paise, rounded down to whole rupees."""
    if percent not in ALLOWED_PERCENTS:
        raise ValueError("Discount must be 25, 50, 75 or 100 percent")
    return (fee_paise * percent // 100) // 100 * 100


def status(is_active: bool, used_at: datetime | None, expires_at: datetime, now: datetime) -> str:
    if used_at is not None:
        return USED
    if not is_active:
        return DEACTIVATED
    if now >= expires_at:
        return EXPIRED
    return UNUSED