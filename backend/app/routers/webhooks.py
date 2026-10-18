"""Razorpay webhook: a server-to-server backup that confirms a booking even if the client
closed the browser right after paying. Configure in Razorpay Dashboard > Webhooks:
URL  https://<your-api-domain>/api/webhooks/razorpay   events: payment.captured, order.paid"""
import json
import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from .. import booking_service as svc
from ..database import get_db
from ..integrations import razorpay_client as rzp

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


@router.post("/razorpay")
async def razorpay_webhook(
    request: Request,
    x_razorpay_signature: str = Header(default=""),
    db: Session = Depends(get_db),
):
    raw = await request.body()
    if not rzp.verify_webhook_signature(raw, x_razorpay_signature):
        raise HTTPException(400, "Invalid signature")
    event = json.loads(raw)
    name = event.get("event")
    payment = event.get("payload", {}).get("payment", {}).get("entity", {})
    order_id, payment_id = payment.get("order_id"), payment.get("id")
    if name in ("payment.captured", "order.paid") and order_id and payment_id:
        try:
            svc.confirm_payment(db, order_id, payment_id)
        except HTTPException as e:
            log.warning("Webhook for unknown order %s: %s", order_id, e.detail)
    # payment.failed is ignored on purpose: Razorpay lets the client retry inside the same
    # checkout. The slot is released when the client closes the checkout, or after HOLD_MINUTES.
    return {"ok": True}
