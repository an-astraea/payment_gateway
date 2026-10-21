"""Coupon service: generate + email, validate, reserve during payment, mark used."""
from __future__ import annotations

import logging
from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import coupon_rules as rules
from . import emails
from .config import get_settings
from .integrations.mailer import send_email
from .models import Booking, Coupon, Service
from .slots import from_db, to_db, utcnow

log = logging.getLogger(__name__)


def _err(message: str, status: int = 400) -> HTTPException:
    # code "coupon" lets the frontend show the error next to the coupon box
    return HTTPException(status, {"code": "coupon", "message": message})


def coupon_status(c: Coupon) -> str:
    return rules.status(c.is_active, c.used_at, from_db(c.expires_at), utcnow())


def expires_label(c: Coupon) -> str:
    local = from_db(c.expires_at).astimezone(get_settings().rules().tz)
    return local.strftime("%d %b %Y, %I:%M %p IST").replace(" 0", " ")


# ---------------------------------------------------------------- admin

def generate(db: Session, percent: int, client_email: str | None = None) -> tuple[Coupon, bool]:
    """Create a single-use coupon. If an email is given it is also sent. Returns (coupon, emailed)."""
    if percent not in rules.ALLOWED_PERCENTS:
        raise HTTPException(400, "Choose 25, 50, 75 or 100 percent.")
    now = utcnow()
    hours = get_settings().coupon_valid_hours
    for _ in range(10):
        c = Coupon(
            code=rules.new_code(),
            percent=percent,
            client_email="",
            created_at=to_db(now),
            expires_at=to_db(now + timedelta(hours=hours)),
            is_active=True,
        )
        db.add(c)
        try:
            db.commit()
            break
        except IntegrityError:  # code clash, try another
            db.rollback()
    else:
        raise HTTPException(500, "Could not create a unique code. Try again.")
    if client_email:
        return send_to(db, c.id, client_email)
    return c, False


def send_to(db: Session, coupon_id: int, client_email: str | None = None) -> tuple[Coupon, bool]:
    """Email an unused coupon to the client. Without an email, resend to the saved one."""
    c = db.get(Coupon, coupon_id)
    if not c:
        raise HTTPException(404, "Coupon not found.")
    if coupon_status(c) != rules.UNUSED:
        raise HTTPException(400, "Only unused, valid coupons can be sent.")
    email = (client_email or c.client_email or "").strip().lower()
    if not email:
        raise HTTPException(400, "Enter the client's email address.")
    c.client_email = email  # from now on the coupon works only with this email (if locking is on)
    db.commit()
    return c, send(db, c)


def send(db: Session, c: Coupon) -> bool:
    s = get_settings()
    content = emails.coupon_issued(
        company=s.company_name,
        code=c.code,
        percent=c.percent,
        expires_label=expires_label(c),
        book_link=f"{s.frontend_base_url.rstrip('/')}/book",
        valid_hours=s.coupon_valid_hours,
        email_locked=s.coupon_lock_to_email,
    )
    ok = send_email(c.client_email, *content)
    if ok:
        c.emailed_at = to_db(utcnow())
        db.commit()
    return ok


def deactivate(db: Session, coupon_id: int) -> Coupon:
    c = db.get(Coupon, coupon_id)
    if not c:
        raise HTTPException(404, "Coupon not found.")
    if c.used_at is not None:
        raise HTTPException(400, "A used coupon cannot be deactivated.")
    c.is_active = False
    c.deactivated_at = to_db(utcnow())
    db.commit()
    return c


def list_coupons(db: Session, status: str | None = None, limit: int = 300) -> list[dict]:
    rows = db.scalars(select(Coupon).order_by(Coupon.created_at.desc()).limit(limit)).all()
    used_ids = [c.used_booking_id for c in rows if c.used_booking_id]
    bookings = {b.id: b for b in db.scalars(select(Booking).where(Booking.id.in_(used_ids))).all()} if used_ids else {}
    out = [coupon_out(c, bookings.get(c.used_booking_id)) for c in rows]
    return [c for c in out if c["status"] == status] if status else out


def coupon_out(c: Coupon, booking: Booking | None = None, emailed: bool | None = None) -> dict:
    return {
        "id": c.id,
        "code": c.code,
        "percent": c.percent,
        "client_email": c.client_email,
        "status": coupon_status(c),
        "created_at": from_db(c.created_at),
        "expires_at": from_db(c.expires_at),
        "emailed": bool(c.emailed_at) if emailed is None else emailed,
        "used_at": from_db(c.used_at),
        "booking_reference": booking.reference if booking else None,
        "booking_client_name": booking.client_name if booking else None,
        "amount_paid_inr": booking.fee_paise // 100 if booking else None,
        "discount_inr": booking.discount_paise // 100 if booking else None,
    }


# ---------------------------------------------------------------- client

def validate(db: Session, code: str, email: str, booking_id: int | None = None) -> Coupon:
    code = rules.normalize(code)
    if not rules.looks_valid(code):
        raise _err("This coupon code is not valid. Check it and try again.")
    c = db.scalar(select(Coupon).where(Coupon.code == code))
    if not c:
        raise _err("This coupon code is not valid. Check it and try again.")
    st = coupon_status(c)
    if st == rules.USED:
        raise _err("This coupon has already been used.")
    if st == rules.DEACTIVATED:
        raise _err("This coupon is no longer valid.")
    if st == rules.EXPIRED:
        raise _err("This coupon has expired. Please ask us for a new one.")
    if get_settings().coupon_lock_to_email and c.client_email and c.client_email != (email or "").strip().lower():
        raise _err("This coupon was sent to a different email address. Use that email in your details.")
    if c.reserved_booking_id and c.reserved_booking_id != booking_id and c.reserved_until and from_db(c.reserved_until) > utcnow():
        raise _err("This coupon is being used in another booking right now. Try again in a few minutes.", 409)
    return c


def check(db: Session, code: str, service_id: int, email: str) -> dict:
    service = db.get(Service, service_id)
    if not service or not service.is_active:
        raise HTTPException(404, "That service is not available.")
    c = validate(db, code, email)
    discount = rules.discount_paise(service.fee_paise, c.percent)
    return {
        "code": c.code,
        "percent": c.percent,
        "base_fee_inr": service.fee_paise // 100,
        "discount_inr": discount // 100,
        "total_inr": (service.fee_paise - discount) // 100,
    }


def reserve(db: Session, c: Coupon, b: Booking) -> None:
    """Atomically reserve the coupon for this booking's payment window."""
    now = to_db(utcnow())
    result = db.execute(
        update(Coupon)
        .where(
            Coupon.id == c.id,
            Coupon.used_at.is_(None),
            Coupon.is_active.is_(True),
            or_(Coupon.reserved_booking_id.is_(None), Coupon.reserved_until < now, Coupon.reserved_booking_id == b.id),
        )
        .values(reserved_booking_id=b.id, reserved_until=b.hold_expires_at)
        .execution_options(synchronize_session=False)
    )
    if result.rowcount != 1:
        raise _err("This coupon is being used in another booking right now. Try again in a few minutes.", 409)


def release(db: Session, b: Booking) -> None:
    """Payment not completed: the coupon stays unused (caller commits)."""
    if b.coupon_id:
        db.execute(
            update(Coupon)
            .where(Coupon.id == b.coupon_id, Coupon.reserved_booking_id == b.id)
            .values(reserved_booking_id=None, reserved_until=None)
            .execution_options(synchronize_session=False)
        )


def mark_used(db: Session, b: Booking) -> None:
    """Payment succeeded: the coupon is used for good (caller commits)."""
    if not b.coupon_id:
        return
    c = db.get(Coupon, b.coupon_id)
    if c is None:
        return
    if c.used_at is not None and c.used_booking_id != b.id:
        log.warning("Coupon %s was already used by booking %s; %s also paid with it", c.code, c.used_booking_id, b.reference)
        return
    c.used_at = to_db(utcnow())
    c.used_booking_id = b.id
    c.reserved_booking_id = None
    c.reserved_until = None