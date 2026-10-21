import datetime as dt
from typing import Literal

from pydantic import BaseModel, EmailStr, Field


class ServiceOut(BaseModel):
    id: int
    name: str
    description: str
    duration_minutes: int
    fee_inr: int


class SlotOut(BaseModel):
    time: str
    label: str
    available: bool


class DayAvailability(BaseModel):
    date: dt.date
    open: bool
    closed_reason: str | None = None
    slots: list[SlotOut]


class HoldRequest(BaseModel):
    service_id: int
    date: dt.date
    time: str = Field(pattern=r"^\d{2}:\d{2}$")
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    phone: str = Field(min_length=7, max_length=20, pattern=r"^[0-9+\-\s]+$")
    coupon_code: str | None = Field(None, max_length=20)


class OrderOut(BaseModel):
    id: str
    amount_paise: int
    currency: str = "INR"
    key_id: str
    mock: bool


class HoldResponse(BaseModel):
    reference: str
    hold_expires_at: dt.datetime | None
    order: OrderOut | None  # None for a free (100% coupon) booking
    booking: "BookingPublic | None" = None  # set when the booking was confirmed without payment
    client_name: str
    client_email: str
    client_phone: str
    service_name: str


class VerifyRequest(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


class ReleaseRequest(BaseModel):
    razorpay_order_id: str


class BookingPublic(BaseModel):
    reference: str
    status: str
    service_name: str
    fee_inr: int
    base_fee_inr: int = 0
    discount_inr: int = 0
    coupon_code: str | None = None
    date: dt.date
    time: str
    slot_label: str
    client_name: str
    client_email: str
    meet_link: str | None
    can_change: bool
    reschedules_left: int
    refund_inr: int = 0
    message: str | None = None


class RescheduleRequest(BaseModel):
    date: dt.date
    time: str = Field(pattern=r"^\d{2}:\d{2}$")


class EmployeeIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr


class EmployeeUpdate(BaseModel):
    name: str | None = None
    email: EmailStr | None = None
    is_active: bool | None = None


class EmployeeOut(BaseModel):
    id: int
    name: str
    email: str
    is_active: bool


class AssignRequest(BaseModel):
    employee_id: int


class BlockedDateIn(BaseModel):
    date: dt.date
    reason: str = ""


class BlockedDateOut(BaseModel):
    id: int
    date: dt.date
    reason: str


class AdminBookingOut(BaseModel):
    id: int
    reference: str
    status: str
    service_name: str
    fee_inr: int
    base_fee_inr: int = 0
    discount_inr: int = 0
    coupon_code: str | None = None
    client_name: str
    client_email: str
    client_phone: str
    meet_link: str | None
    employee_id: int | None
    employee_name: str | None
    hold_expires_at: dt.datetime | None
    reschedule_count: int


class AdminSlot(BaseModel):
    time: str
    label: str
    booking: AdminBookingOut | None


class AdminDay(BaseModel):
    date: dt.date
    working_day: bool
    holiday: str | None
    booked_count: int
    slots: list[AdminSlot]


class CouponCheckRequest(BaseModel):
    code: str = Field(min_length=3, max_length=20)
    service_id: int
    email: EmailStr


class CouponCheckOut(BaseModel):
    code: str
    percent: int
    base_fee_inr: int
    discount_inr: int
    total_inr: int


class CouponCreate(BaseModel):
    percent: Literal[25, 50, 75, 100]
    client_email: EmailStr | None = None  # optional: the admin can email it after generating


class CouponSend(BaseModel):
    client_email: EmailStr | None = None  # empty = resend to the saved email


class CouponOut(BaseModel):
    id: int
    code: str
    percent: int
    client_email: str
    status: str  # unused | used | expired | deactivated
    created_at: dt.datetime
    expires_at: dt.datetime
    emailed: bool
    used_at: dt.datetime | None
    booking_reference: str | None
    booking_client_name: str | None
    amount_paid_inr: int | None
    discount_inr: int | None


class CouponConfig(BaseModel):
    percents: list[int]
    valid_hours: int
    lock_to_email: bool


HoldResponse.model_rebuild()