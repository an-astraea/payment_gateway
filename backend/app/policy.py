"""Cancellation, rescheduling and refund policy. Pure Python, unit-tested.

Policy
- Client cancels 24 hours or more before the session: full refund through Razorpay.
- Less than 24 hours before (or a no-show): the client can no longer cancel or reschedule
  through the link and no refund is due. They can contact the company.
- Client may reschedule once, free, if done 24 hours or more before.
- Company (admin) cancels at any time: always a full refund.
- A payment that arrives after its slot went to someone else is refunded in full.
"""
from __future__ import annotations

from datetime import datetime, timedelta


def can_client_change(slot_start_at: datetime, now: datetime, cutoff_hours: int) -> bool:
    return slot_start_at - now >= timedelta(hours=cutoff_hours)


def reschedules_left(used: int, max_reschedules: int) -> int:
    return max(0, max_reschedules - used)


def client_cancel_refund_paise(fee_paise: int, slot_start_at: datetime, now: datetime, cutoff_hours: int) -> int:
    return fee_paise if can_client_change(slot_start_at, now, cutoff_hours) else 0


def admin_cancel_refund_paise(fee_paise: int) -> int:
    return fee_paise
