"""Client-facing API: services, availability, booking + payment, manage booking."""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import booking_service as svc
from ..config import get_settings
from ..database import get_db
from ..integrations import razorpay_client as rzp
from ..models import Service
from ..schemas import (
    BookingPublic,
    DayAvailability,
    HoldRequest,
    HoldResponse,
    ReleaseRequest,
    RescheduleRequest,
    ServiceOut,
    VerifyRequest,
)
from ..slots import first_bookable_date, from_db, utcnow

router = APIRouter(prefix="/api", tags=["booking"])


@router.get("/services", response_model=list[ServiceOut])
def list_services(db: Session = Depends(get_db)):
    rows = db.scalars(select(Service).where(Service.is_active.is_(True)).order_by(Service.sort_order, Service.id)).all()
    return [
        ServiceOut(id=s.id, name=s.name, description=s.description, duration_minutes=s.duration_minutes, fee_inr=s.fee_paise // 100)
        for s in rows
    ]


@router.get("/availability", response_model=list[DayAvailability])
def get_availability(
    start: date | None = Query(None, description="First date, defaults to the first bookable date"),
    days: int | None = Query(None, ge=1, le=62),
    db: Session = Depends(get_db),
):
    s = get_settings()
    start = start or first_bookable_date(s.rules(), utcnow())
    days = days or s.booking_horizon_days
    return svc.availability(db, start, days)


@router.post("/bookings/hold", response_model=HoldResponse)
def hold_slot(req: HoldRequest, db: Session = Depends(get_db)):
    """Hold the chosen slot and create the Razorpay order. The booking is confirmed only
    after the payment is verified."""
    b = svc.create_hold(db, req)
    s = get_settings()
    return HoldResponse(
        reference=b.reference,
        hold_expires_at=from_db(b.hold_expires_at),
        order={
            "id": b.razorpay_order_id,
            "amount_paise": b.fee_paise,
            "key_id": s.razorpay_key_id or "mock",
            "mock": s.razorpay_mock,
        },
        client_name=b.client_name,
        client_email=b.client_email,
        client_phone=b.client_phone,
        service_name=b.service_name,
    )


@router.post("/bookings/verify", response_model=BookingPublic)
def verify_payment(req: VerifyRequest, db: Session = Depends(get_db)):
    if not rzp.verify_checkout_signature(req.razorpay_order_id, req.razorpay_payment_id, req.razorpay_signature):
        raise HTTPException(400, "The payment could not be verified. If money was deducted, it will be refunded.")
    b = svc.confirm_payment(db, req.razorpay_order_id, req.razorpay_payment_id)
    msg = None
    if b.status == "refunded_conflict":
        msg = "The slot was booked by someone else before your payment arrived. Your payment has been refunded in full."
    return svc.public_view(b, msg)


@router.post("/bookings/release")
def release(req: ReleaseRequest, db: Session = Depends(get_db)):
    svc.release_hold(db, req.razorpay_order_id)
    return {"ok": True}


@router.get("/manage/{token}", response_model=BookingPublic)
def manage_view(token: str, db: Session = Depends(get_db)):
    return svc.public_view(svc.get_by_token(db, token))


@router.post("/manage/{token}/cancel", response_model=BookingPublic)
def manage_cancel(token: str, db: Session = Depends(get_db)):
    b = svc.client_cancel(db, token)
    return svc.public_view(b, "Your booking is cancelled.")


@router.post("/manage/{token}/reschedule", response_model=BookingPublic)
def manage_reschedule(token: str, req: RescheduleRequest, db: Session = Depends(get_db)):
    b = svc.client_reschedule(db, token, req.date, req.time)
    return svc.public_view(b, "Your booking has been moved.")
