"""Core booking rules: holds, payment confirmation, expiry, cancellation, rescheduling,
assignment. Routers stay thin and call these functions."""
from __future__ import annotations

import logging
import secrets
from datetime import date, timedelta

from fastapi import HTTPException
from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import coupon_rules, coupons, emails, policy
from .config import get_settings
from .integrations import google_calendar as gcal
from .integrations import razorpay_client as rzp
from .integrations.mailer import send_email
from .models import BlockedDate, Booking, BookingStatus, Employee, Service, SlotLock
from .slots import date_closed_reason, from_db, slot_end, slot_label, slot_start, to_db, utcnow

log = logging.getLogger(__name__)


# ---------------------------------------------------------------- helpers

def _rules():
    return get_settings().rules()


def _blocked(db: Session, start: date, end: date) -> dict[date, str]:
    rows = db.execute(select(BlockedDate.day, BlockedDate.reason).where(BlockedDate.day.between(start, end))).all()
    return {d: r for d, r in rows}


def _new_reference() -> str:
    return "LX-" + "".join(secrets.choice("ABCDEFGHJKLMNPQRSTUVWXYZ23456789") for _ in range(6))


def booking_start(b: Booking):
    return slot_start(_rules(), b.slot_date, b.slot_time)


def date_label(d: date) -> str:
    return d.strftime("%A, %d %B %Y")


def mail_context(b: Booking) -> emails.MailContext:
    s = get_settings()
    return emails.MailContext(
        company=s.company_name,
        reference=b.reference,
        client_name=b.client_name,
        service_name=b.service_name,
        date_label=date_label(b.slot_date),
        slot_label=slot_label(_rules(), b.slot_time) + " IST",
        fee_inr=b.fee_paise // 100,
        meet_link=b.meet_link,
        manage_link=f"{s.frontend_base_url.rstrip('/')}/manage/{b.manage_token}",
        payment_id=b.razorpay_payment_id,
        refund_inr=b.refund_paise // 100,
        employee_name=b.employee.name if b.employee else None,
        client_email=b.client_email,
        client_phone=b.client_phone,
        base_fee_inr=(b.base_fee_paise or b.fee_paise) // 100,
        discount_inr=b.discount_paise // 100,
        coupon_code=b.coupon_code,
    )


def _mail(to: str, content: tuple[str, str, str]) -> None:
    subject, html, text = content
    send_email(to, subject, html, text)


def _attendees(b: Booking) -> list[str]:
    people = [b.client_email]
    if b.employee:
        people.append(b.employee.email)
    return people


# ---------------------------------------------------------------- availability

def release_expired_holds(db: Session) -> int:
    """Safety net: a slot held for an unfinished payment is freed after HOLD_MINUTES."""
    now = to_db(utcnow())
    expired = db.scalars(
        select(Booking).where(Booking.status == BookingStatus.PENDING_PAYMENT, Booking.hold_expires_at < now)
    ).all()
    for b in expired:
        b.status = BookingStatus.EXPIRED
        db.execute(delete(SlotLock).where(SlotLock.booking_id == b.id))
        coupons.release(db, b)
    if expired:
        db.commit()
        log.info("Released %d expired holds", len(expired))
    return len(expired)


def availability(db: Session, start: date, days: int) -> list[dict]:
    release_expired_holds(db)
    rules = _rules()
    end = start + timedelta(days=days - 1)
    blocked = _blocked(db, start, end)
    taken = {
        (d, t)
        for d, t in db.execute(select(SlotLock.slot_date, SlotLock.slot_time).where(SlotLock.slot_date.between(start, end))).all()
    }
    now = utcnow()
    out = []
    for i in range(days):
        d = start + timedelta(days=i)
        reason = date_closed_reason(rules, d, now, set(blocked))
        slots = [
            {"time": t, "label": slot_label(rules, t), "available": reason is None and (d, t) not in taken}
            for t in rules.slot_times
        ]
        out.append({"date": d, "open": reason is None, "closed_reason": reason, "slots": slots})
    return out


def _check_slot_open(db: Session, d: date, t: str) -> None:
    rules = _rules()
    if t not in rules.slot_times:
        raise HTTPException(400, "That time is not one of the available slots.")
    reason = date_closed_reason(rules, d, utcnow(), set(_blocked(db, d, d)))
    messages = {
        "too_soon": "Bookings close one day before. Choose a date from tomorrow onwards.",
        "beyond_horizon": f"Bookings open up to {rules.horizon_days} days ahead.",
        "non_working_day": "Consultations run Monday to Saturday.",
        "holiday": "The office is closed on that date.",
    }
    if reason:
        raise HTTPException(400, messages[reason])


# ---------------------------------------------------------------- booking + payment

def create_hold(db: Session, req) -> Booking:
    """Step 4 (Pay): hold the slot and create the Razorpay order."""
    release_expired_holds(db)
    service = db.get(Service, req.service_id)
    if not service or not service.is_active:
        raise HTTPException(404, "That service is not available.")
    _check_slot_open(db, req.date, req.time)

    coupon = None
    discount = 0
    if getattr(req, "coupon_code", None):
        coupon = coupons.validate(db, req.coupon_code, str(req.email))
        discount = coupon_rules.discount_paise(service.fee_paise, coupon.percent)

    now = utcnow()
    b = Booking(
        reference=_new_reference(),
        manage_token=secrets.token_urlsafe(32),
        service_id=service.id,
        service_name=service.name,
        base_fee_paise=service.fee_paise,  # price set by the server
        discount_paise=discount,
        fee_paise=service.fee_paise - discount,  # amount the client pays
        coupon_id=coupon.id if coupon else None,
        coupon_code=coupon.code if coupon else None,
        duration_minutes=service.duration_minutes,
        client_name=req.name.strip(),
        client_email=str(req.email).lower(),
        client_phone=req.phone.strip(),
        slot_date=req.date,
        slot_time=req.time,
        status=BookingStatus.PENDING_PAYMENT,
        hold_expires_at=to_db(now + timedelta(minutes=get_settings().hold_minutes)),
        created_at=to_db(now),
    )
    db.add(b)
    try:
        db.flush()
        db.add(SlotLock(slot_date=req.date, slot_time=req.time, booking_id=b.id))
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Someone has just booked this slot. Choose another time.")
    if coupon:
        try:
            coupons.reserve(db, coupon, b)
        except HTTPException:
            db.rollback()
            raise

    if b.fee_paise == 0:
        # 100% coupon: nothing to pay, so the booking is confirmed straight away
        db.commit()
        _confirm(db, b, payment_id=None)
        return b

    try:
        b.razorpay_order_id = rzp.create_order(b.fee_paise, b.reference, {"booking": b.reference})
    except rzp.PaymentError as e:
        db.rollback()
        raise HTTPException(502, str(e))
    db.commit()
    return b


def _confirm(db: Session, b: Booking, payment_id: str | None) -> None:
    b.status = BookingStatus.CONFIRMED
    b.razorpay_payment_id = payment_id
    b.confirmed_at = to_db(utcnow())
    b.hold_expires_at = None
    coupons.mark_used(db, b)
    db.commit()

    rules = _rules()
    try:
        event_id, meet = gcal.create_event(
            summary=f"{b.service_name}: {b.client_name} ({b.reference})",
            description=(
                f"Consultation booked online.\nBooking ID: {b.reference}\nClient: {b.client_name}\n"
                f"Email: {b.client_email}\nPhone: {b.client_phone}"
            ),
            start=slot_start(rules, b.slot_date, b.slot_time),
            end=slot_end(rules, b.slot_date, b.slot_time),
            attendees=_attendees(b),
        )
        b.calendar_event_id, b.meet_link = event_id, meet
        db.commit()
    except Exception:
        log.exception("Calendar event failed for %s", b.reference)

    _mail(b.client_email, emails.booking_confirmed(mail_context(b)))


def confirm_payment(db: Session, order_id: str, payment_id: str) -> Booking:
    """Called after the checkout signature check, and again by the webhook (idempotent)."""
    b = db.scalar(select(Booking).where(Booking.razorpay_order_id == order_id))
    if not b:
        raise HTTPException(404, "Booking not found for this payment.")
    if b.status in (BookingStatus.CONFIRMED, BookingStatus.REFUNDED_CONFLICT, BookingStatus.CANCELLED):
        return b

    lock = db.scalar(select(SlotLock).where(SlotLock.booking_id == b.id))
    if lock is None:
        # Hold already expired or was released. Take the slot back if it is still free.
        try:
            db.add(SlotLock(slot_date=b.slot_date, slot_time=b.slot_time, booking_id=b.id))
            db.flush()
        except IntegrityError:
            db.rollback()
            b = db.get(Booking, b.id)
            b.razorpay_payment_id = payment_id
            try:
                b.refund_id = rzp.refund(payment_id, b.fee_paise, {"reason": "slot_taken", "booking": b.reference})
                b.refund_paise = b.fee_paise
            except rzp.PaymentError:
                log.exception("Conflict refund failed for %s. Refund it manually.", b.reference)
            b.status = BookingStatus.REFUNDED_CONFLICT
            coupons.release(db, b)  # not used: the client can still use it for another slot
            db.commit()
            _mail(b.client_email, emails.payment_refunded_conflict(mail_context(b)))
            return b
    _confirm(db, b, payment_id)
    return b


def release_hold(db: Session, order_id: str) -> None:
    """Client closed the checkout or the payment failed: free the slot straight away."""
    b = db.scalar(select(Booking).where(Booking.razorpay_order_id == order_id))
    if b and b.status == BookingStatus.PENDING_PAYMENT:
        b.status = BookingStatus.PAYMENT_FAILED
        db.execute(delete(SlotLock).where(SlotLock.booking_id == b.id))
        coupons.release(db, b)
        db.commit()


# ---------------------------------------------------------------- client changes

def get_by_token(db: Session, token: str) -> Booking:
    b = db.scalar(select(Booking).where(Booking.manage_token == token))
    if not b:
        raise HTTPException(404, "This booking link is not valid.")
    return b


def client_can_change(b: Booking) -> bool:
    return b.status == BookingStatus.CONFIRMED and policy.can_client_change(
        booking_start(b), utcnow(), get_settings().change_cutoff_hours
    )


def _cutoff_error() -> HTTPException:
    h = get_settings().change_cutoff_hours
    return HTTPException(400, f"Changes close {h} hours before the session. Contact us to discuss this booking.")


def client_cancel(db: Session, token: str) -> Booking:
    b = get_by_token(db, token)
    if b.status != BookingStatus.CONFIRMED:
        raise HTTPException(400, "Only confirmed bookings can be cancelled.")
    if not client_can_change(b):
        raise _cutoff_error()
    amount = policy.client_cancel_refund_paise(b.fee_paise, booking_start(b), utcnow(), get_settings().change_cutoff_hours)
    return _cancel(db, b, amount, by="client")


def _cancel(db: Session, b: Booking, refund_paise: int, by: str) -> Booking:
    if refund_paise and b.razorpay_payment_id:
        try:
            b.refund_id = rzp.refund(b.razorpay_payment_id, refund_paise, {"reason": f"cancelled_by_{by}", "booking": b.reference})
            b.refund_paise = refund_paise
        except rzp.PaymentError as e:
            raise HTTPException(502, str(e))
    b.status = BookingStatus.CANCELLED
    b.cancelled_by = by
    b.cancelled_at = to_db(utcnow())
    db.execute(delete(SlotLock).where(SlotLock.booking_id == b.id))
    db.commit()
    try:
        gcal.delete_event(b.calendar_event_id)
    except Exception:
        log.exception("Could not delete calendar event for %s", b.reference)
    ctx = mail_context(b)
    _mail(b.client_email, emails.booking_cancelled(ctx, by_company=(by == "admin")))
    if b.employee:
        _mail(b.employee.email, emails.employee_unassigned(ctx))
    return b


def client_reschedule(db: Session, token: str, new_date: date, new_time: str) -> Booking:
    b = get_by_token(db, token)
    s = get_settings()
    if b.status != BookingStatus.CONFIRMED:
        raise HTTPException(400, "Only confirmed bookings can be rescheduled.")
    if not client_can_change(b):
        raise _cutoff_error()
    if policy.reschedules_left(b.reschedule_count, s.max_reschedules) == 0:
        raise HTTPException(400, "This booking has already been rescheduled once. Contact us to change it again.")
    if (new_date, new_time) == (b.slot_date, b.slot_time):
        raise HTTPException(400, "Choose a different date or time.")
    _check_slot_open(db, new_date, new_time)
    release_expired_holds(db)
    try:
        db.execute(update(SlotLock).where(SlotLock.booking_id == b.id).values(slot_date=new_date, slot_time=new_time))
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "That slot has just been booked. Choose another time.")
    b = db.get(Booking, b.id)
    b.slot_date, b.slot_time = new_date, new_time
    b.reschedule_count += 1
    db.commit()
    rules = _rules()
    try:
        gcal.move_event(b.calendar_event_id, slot_start(rules, new_date, new_time), slot_end(rules, new_date, new_time))
    except Exception:
        log.exception("Could not move calendar event for %s", b.reference)
    ctx = mail_context(b)
    _mail(b.client_email, emails.booking_rescheduled(ctx))
    if b.employee:
        _mail(b.employee.email, emails.employee_assigned(ctx))
    return b


# ---------------------------------------------------------------- admin

def admin_cancel(db: Session, booking_id: int) -> Booking:
    b = db.get(Booking, booking_id)
    if not b or b.status != BookingStatus.CONFIRMED:
        raise HTTPException(400, "Only confirmed bookings can be cancelled.")
    return _cancel(db, b, policy.admin_cancel_refund_paise(b.fee_paise), by="admin")


def assign_employee(db: Session, booking_id: int, employee_id: int) -> Booking:
    b = db.get(Booking, booking_id)
    if not b or b.status != BookingStatus.CONFIRMED:
        raise HTTPException(400, "Only confirmed bookings can be assigned.")
    emp = db.get(Employee, employee_id)
    if not emp or not emp.is_active:
        raise HTTPException(404, "Employee not found.")
    if b.employee_id == emp.id:
        return b
    previous = b.employee
    b.employee = emp
    db.commit()
    try:
        gcal.set_attendees(b.calendar_event_id, _attendees(b))
    except Exception:
        log.exception("Could not add %s to the calendar event", emp.email)
    ctx = mail_context(b)
    _mail(emp.email, emails.employee_assigned(ctx))
    if previous:
        ctx.employee_name = previous.name
        _mail(previous.email, emails.employee_unassigned(ctx))
    return b


def admin_days(db: Session, start: date, days: int) -> list[dict]:
    release_expired_holds(db)
    rules = _rules()
    end = start + timedelta(days=days - 1)
    blocked = _blocked(db, start, end)
    active = db.scalars(
        select(Booking).where(
            Booking.slot_date.between(start, end),
            Booking.status.in_([BookingStatus.CONFIRMED, BookingStatus.PENDING_PAYMENT]),
        )
    ).all()
    by_slot = {(b.slot_date, b.slot_time): b for b in active}
    out = []
    for i in range(days):
        d = start + timedelta(days=i)
        slots = []
        for t in rules.slot_times:
            b = by_slot.get((d, t))
            slots.append({"time": t, "label": slot_label(rules, t), "booking": admin_booking(b) if b else None})
        out.append(
            {
                "date": d,
                "working_day": d.weekday() in rules.working_days,
                "holiday": blocked.get(d),
                "booked_count": sum(1 for s in slots if s["booking"] and s["booking"]["status"] == BookingStatus.CONFIRMED),
                "slots": slots,
            }
        )
    return out


def admin_booking(b: Booking) -> dict:
    return {
        "id": b.id,
        "reference": b.reference,
        "status": b.status,
        "service_name": b.service_name,
        "fee_inr": b.fee_paise // 100,
        "base_fee_inr": (b.base_fee_paise or b.fee_paise) // 100,
        "discount_inr": b.discount_paise // 100,
        "coupon_code": b.coupon_code,
        "client_name": b.client_name,
        "client_email": b.client_email,
        "client_phone": b.client_phone,
        "meet_link": b.meet_link,
        "employee_id": b.employee_id,
        "employee_name": b.employee.name if b.employee else None,
        "hold_expires_at": from_db(b.hold_expires_at),
        "reschedule_count": b.reschedule_count,
    }


def public_view(b: Booking, message: str | None = None) -> dict:
    s = get_settings()
    return {
        "reference": b.reference,
        "status": b.status,
        "service_name": b.service_name,
        "fee_inr": b.fee_paise // 100,
        "base_fee_inr": (b.base_fee_paise or b.fee_paise) // 100,
        "discount_inr": b.discount_paise // 100,
        "coupon_code": b.coupon_code,
        "date": b.slot_date,
        "time": b.slot_time,
        "slot_label": slot_label(_rules(), b.slot_time),
        "client_name": b.client_name,
        "client_email": b.client_email,
        "meet_link": b.meet_link,
        "can_change": client_can_change(b),
        "reschedules_left": policy.reschedules_left(b.reschedule_count, s.max_reschedules),
        "refund_inr": b.refund_paise // 100,
        "message": message,
    }