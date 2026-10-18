"""Email content. Each function returns (subject, html, text). Pure Python."""
from __future__ import annotations

from dataclasses import dataclass
from html import escape


@dataclass
class MailContext:
    company: str
    reference: str
    client_name: str
    service_name: str
    date_label: str  # "Wednesday, 14 October 2026"
    slot_label: str  # "2:00 PM - 3:00 PM IST"
    fee_inr: int
    meet_link: str | None = None
    manage_link: str | None = None
    payment_id: str | None = None
    refund_inr: int = 0
    employee_name: str | None = None
    client_email: str | None = None
    client_phone: str | None = None


def _inr(amount: int) -> str:
    s = str(amount)
    if len(s) <= 3:
        return f"Rs {s}"
    head, tail = s[:-3], s[-3:]
    parts = []
    while len(head) > 2:
        parts.insert(0, head[-2:])
        head = head[:-2]
    if head:
        parts.insert(0, head)
    return "Rs " + ",".join(parts + [tail])


def _rows(rows: list[tuple[str, str]]) -> str:
    cells = "".join(
        f'<tr><td style="padding:6px 16px 6px 0;color:#5B6670">{escape(k)}</td>'
        f'<td style="padding:6px 0;color:#17202B"><strong>{escape(v)}</strong></td></tr>'
        for k, v in rows
    )
    return f'<table style="border-collapse:collapse;font-size:15px">{cells}</table>'


def _wrap(company: str, heading: str, body: str) -> str:
    return (
        '<div style="font-family:Arial,Helvetica,sans-serif;max-width:560px;margin:0 auto;color:#17202B">'
        f'<p style="font-size:13px;color:#0E5E54;margin:0 0 8px">{escape(company)}</p>'
        f'<h1 style="font-size:22px;margin:0 0 16px">{escape(heading)}</h1>{body}'
        f'<p style="font-size:13px;color:#5B6670;margin-top:28px">This email was sent by {escape(company)}.</p></div>'
    )


def _button(url: str, label: str) -> str:
    return (
        f'<p style="margin:20px 0"><a href="{escape(url)}" style="background:#0E5E54;color:#fff;'
        f'padding:11px 18px;border-radius:6px;text-decoration:none;display:inline-block">{escape(label)}</a></p>'
    )


def _text(lines: list[str]) -> str:
    return "\n".join(lines)


def booking_confirmed(c: MailContext) -> tuple[str, str, str]:
    subject = f"Booking confirmed: {c.service_name} on {c.date_label}"
    rows = [
        ("Booking ID", c.reference),
        ("Service", c.service_name),
        ("Date", c.date_label),
        ("Time", c.slot_label),
        ("Amount paid", _inr(c.fee_inr)),
        ("Payment ID", c.payment_id or "-"),
    ]
    meet = (
        _button(c.meet_link, "Join Google Meet") + f'<p style="font-size:14px">Meeting link: {escape(c.meet_link)}</p>'
        if c.meet_link
        else "<p>Your Google Meet link will follow in a separate email.</p>"
    )
    manage = (
        f'<p style="font-size:14px;color:#5B6670">Need to reschedule or cancel? You can do it up to 24 hours '
        f'before the session: <a href="{escape(c.manage_link)}">manage your booking</a>. '
        f"Cancelling 24 hours or more before gives a full refund.</p>"
        if c.manage_link
        else ""
    )
    html = _wrap(
        c.company,
        "Your consultation is booked",
        f"<p>Hello {escape(c.client_name)},</p><p>Thank you. Your payment was received and your slot is confirmed.</p>"
        f"{_rows(rows)}{meet}{manage}",
    )
    text = _text(
        [f"Hello {c.client_name},", "Your consultation is booked.", ""]
        + [f"{k}: {v}" for k, v in rows]
        + ["", f"Google Meet: {c.meet_link or 'link to follow'}", f"Manage your booking: {c.manage_link or '-'}"]
    )
    return subject, html, text


def booking_rescheduled(c: MailContext) -> tuple[str, str, str]:
    subject = f"Booking moved: {c.service_name} on {c.date_label}"
    rows = [("Booking ID", c.reference), ("New date", c.date_label), ("New time", c.slot_label)]
    html = _wrap(
        c.company,
        "Your consultation has a new time",
        f"<p>Hello {escape(c.client_name)},</p>{_rows(rows)}"
        + (_button(c.meet_link, "Join Google Meet") if c.meet_link else "")
        + "<p style='font-size:14px;color:#5B6670'>The Google Meet link stays the same. "
        "A booking can be rescheduled once.</p>",
    )
    text = _text([f"Hello {c.client_name},", "Your consultation has a new time."] + [f"{k}: {v}" for k, v in rows])
    return subject, html, text


def booking_cancelled(c: MailContext, by_company: bool = False) -> tuple[str, str, str]:
    subject = f"Booking cancelled: {c.reference}"
    lead = (
        "We had to cancel your consultation. We are sorry for the change."
        if by_company
        else "Your consultation has been cancelled as requested."
    )
    refund_line = (
        f"A refund of {_inr(c.refund_inr)} has been started. It usually reaches your account in 5-7 working days."
        if c.refund_inr
        else "No refund is due for this cancellation."
    )
    rows = [("Booking ID", c.reference), ("Service", c.service_name), ("Was scheduled", f"{c.date_label}, {c.slot_label}")]
    html = _wrap(c.company, "Booking cancelled", f"<p>Hello {escape(c.client_name)},</p><p>{lead}</p>{_rows(rows)}<p>{refund_line}</p>")
    text = _text([f"Hello {c.client_name},", lead] + [f"{k}: {v}" for k, v in rows] + [refund_line])
    return subject, html, text


def payment_refunded_conflict(c: MailContext) -> tuple[str, str, str]:
    subject = "Your payment has been refunded"
    msg = (
        f"Your payment for {c.service_name} on {c.date_label}, {c.slot_label} arrived after the payment window "
        f"closed, and the slot had already been booked. We have refunded {_inr(c.refund_inr)} in full. "
        "It usually reaches your account in 5-7 working days. Please choose another slot."
    )
    html = _wrap(c.company, "Payment refunded", f"<p>Hello {escape(c.client_name)},</p><p>{escape(msg)}</p>")
    return subject, html, _text([f"Hello {c.client_name},", msg])


def employee_assigned(c: MailContext) -> tuple[str, str, str]:
    subject = f"Session assigned to you: {c.date_label}, {c.slot_label}"
    rows = [
        ("Booking ID", c.reference),
        ("Service", c.service_name),
        ("Date", c.date_label),
        ("Time", c.slot_label),
        ("Client", c.client_name),
        ("Client email", c.client_email or "-"),
        ("Client phone", c.client_phone or "-"),
    ]
    html = _wrap(
        c.company,
        "A consultation has been assigned to you",
        f"<p>Hello {escape(c.employee_name or '')},</p>{_rows(rows)}"
        + (_button(c.meet_link, "Open Google Meet") if c.meet_link else "<p>Meet link not available yet.</p>"),
    )
    text = _text([f"Hello {c.employee_name},", "A consultation has been assigned to you."] + [f"{k}: {v}" for k, v in rows] + [f"Meet: {c.meet_link or '-'}"])
    return subject, html, text


def employee_unassigned(c: MailContext) -> tuple[str, str, str]:
    subject = f"Session reassigned: {c.reference}"
    msg = f"The session on {c.date_label}, {c.slot_label} ({c.reference}) is no longer assigned to you."
    return subject, _wrap(c.company, "Session reassigned", f"<p>Hello {escape(c.employee_name or '')},</p><p>{escape(msg)}</p>"), msg
