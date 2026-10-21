"""Admin dashboard API.

AUTH: there is no login yet (it will be added later). Every route depends on
`require_admin`, so protecting the whole dashboard means changing that one function."""
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import booking_service as svc
from .. import coupon_rules, coupons
from ..config import get_settings
from ..database import get_db
from ..models import BlockedDate, Employee
from ..schemas import (
    AdminBookingOut,
    AdminDay,
    AssignRequest,
    BlockedDateIn,
    BlockedDateOut,
    CouponConfig,
    CouponCreate,
    CouponOut,
    CouponSend,
    EmployeeIn,
    EmployeeOut,
    EmployeeUpdate,
)
from ..slots import local_today, utcnow


def require_admin() -> None:
    """Placeholder for authentication. Replace with a real check (session, JWT, SSO...)."""
    return None


router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_admin)])


@router.get("/days", response_model=list[AdminDay])
def booked_days(
    start: date | None = Query(None, description="First day shown, defaults to today"),
    days: int = Query(7, ge=1, le=62),
    db: Session = Depends(get_db),
):
    start = start or local_today(get_settings().rules(), utcnow())
    return svc.admin_days(db, start, days)


@router.post("/bookings/{booking_id}/assign", response_model=AdminBookingOut)
def assign(booking_id: int, req: AssignRequest, db: Session = Depends(get_db)):
    return svc.admin_booking(svc.assign_employee(db, booking_id, req.employee_id))


@router.post("/bookings/{booking_id}/cancel", response_model=AdminBookingOut)
def cancel(booking_id: int, db: Session = Depends(get_db)):
    return svc.admin_booking(svc.admin_cancel(db, booking_id))


# ---------- employees

def _emp(e: Employee) -> EmployeeOut:
    return EmployeeOut(id=e.id, name=e.name, email=e.email, is_active=e.is_active)


@router.get("/employees", response_model=list[EmployeeOut])
def list_employees(db: Session = Depends(get_db)):
    return [_emp(e) for e in db.scalars(select(Employee).order_by(Employee.name)).all()]


@router.post("/employees", response_model=EmployeeOut, status_code=201)
def add_employee(req: EmployeeIn, db: Session = Depends(get_db)):
    e = Employee(name=req.name.strip(), email=str(req.email).lower())
    db.add(e)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "An employee with this email already exists.")
    return _emp(e)


@router.patch("/employees/{employee_id}", response_model=EmployeeOut)
def update_employee(employee_id: int, req: EmployeeUpdate, db: Session = Depends(get_db)):
    e = db.get(Employee, employee_id)
    if not e:
        raise HTTPException(404, "Employee not found.")
    if req.name is not None:
        e.name = req.name.strip()
    if req.email is not None:
        e.email = str(req.email).lower()
    if req.is_active is not None:
        e.is_active = req.is_active
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "An employee with this email already exists.")
    return _emp(e)


# ---------- holidays / blocked dates

@router.get("/blocked-dates", response_model=list[BlockedDateOut])
def list_blocked(db: Session = Depends(get_db)):
    today = local_today(get_settings().rules(), utcnow())
    rows = db.scalars(select(BlockedDate).where(BlockedDate.day >= today - timedelta(days=1)).order_by(BlockedDate.day)).all()
    return [BlockedDateOut(id=r.id, date=r.day, reason=r.reason) for r in rows]


@router.post("/blocked-dates", response_model=BlockedDateOut, status_code=201)
def add_blocked(req: BlockedDateIn, db: Session = Depends(get_db)):
    r = BlockedDate(day=req.date, reason=req.reason.strip())
    db.add(r)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "This date is already blocked.")
    return BlockedDateOut(id=r.id, date=r.day, reason=r.reason)


@router.delete("/blocked-dates/{blocked_id}", status_code=204)
def remove_blocked(blocked_id: int, db: Session = Depends(get_db)):
    r = db.get(BlockedDate, blocked_id)
    if r:
        db.delete(r)
        db.commit()


# ---------- coupons

@router.get("/coupons/config", response_model=CouponConfig)
def coupon_config():
    s = get_settings()
    return CouponConfig(percents=list(coupon_rules.ALLOWED_PERCENTS), valid_hours=s.coupon_valid_hours, lock_to_email=s.coupon_lock_to_email)


@router.get("/coupons", response_model=list[CouponOut])
def list_coupons(status: str | None = Query(None, pattern="^(unused|used|expired|deactivated)$"), db: Session = Depends(get_db)):
    return coupons.list_coupons(db, status)


@router.post("/coupons", response_model=CouponOut, status_code=201)
def create_coupon(req: CouponCreate, db: Session = Depends(get_db)):
    """Generate a single-use coupon. Email it now (client_email) or later with /send."""
    c, emailed = coupons.generate(db, req.percent, str(req.client_email) if req.client_email else None)
    return coupons.coupon_out(c, emailed=emailed)


@router.post("/coupons/{coupon_id}/send", response_model=CouponOut)
def send_coupon(coupon_id: int, req: CouponSend, db: Session = Depends(get_db)):
    """Email a coupon to the client (or resend it to the saved email)."""
    c, emailed = coupons.send_to(db, coupon_id, str(req.client_email) if req.client_email else None)
    return coupons.coupon_out(c, emailed=emailed)


@router.post("/coupons/{coupon_id}/deactivate", response_model=CouponOut)
def deactivate_coupon(coupon_id: int, db: Session = Depends(get_db)):
    return coupons.coupon_out(coupons.deactivate(db, coupon_id))