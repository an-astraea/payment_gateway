"""Razorpay through its REST API (no SDK needed).

MOCK mode: when RAZORPAY_KEY_ID / RAZORPAY_KEY_SECRET are empty, orders and refunds are
simulated so the whole flow can be tested locally without real money.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import secrets

import requests

from ..config import get_settings

log = logging.getLogger(__name__)
API = "https://api.razorpay.com/v1"
MOCK_SIGNATURE = "mock_signature"


class PaymentError(Exception):
    pass


def _auth() -> tuple[str, str]:
    s = get_settings()
    return (s.razorpay_key_id, s.razorpay_key_secret)


def create_order(amount_paise: int, receipt: str, notes: dict) -> str:
    """Create an order. The amount always comes from the server, never the browser."""
    if get_settings().razorpay_mock:
        return f"order_mock_{secrets.token_hex(6)}"
    resp = requests.post(
        f"{API}/orders",
        auth=_auth(),
        json={"amount": amount_paise, "currency": "INR", "receipt": receipt, "notes": notes},
        timeout=20,
    )
    if resp.status_code >= 400:
        log.error("Razorpay order failed: %s %s", resp.status_code, resp.text)
        raise PaymentError("Could not start the payment. Try again in a moment.")
    return resp.json()["id"]


def verify_checkout_signature(order_id: str, payment_id: str, signature: str) -> bool:
    """Signature returned by Checkout: HMAC_SHA256(order_id|payment_id, key_secret)."""
    s = get_settings()
    if s.razorpay_mock:
        return signature == MOCK_SIGNATURE and order_id.startswith("order_mock_")
    expected = hmac.new(
        s.razorpay_key_secret.encode(), f"{order_id}|{payment_id}".encode(), hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def verify_webhook_signature(raw_body: bytes, signature: str) -> bool:
    secret = get_settings().razorpay_webhook_secret
    if not secret:
        return False
    expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature or "")


def refund(payment_id: str, amount_paise: int, notes: dict | None = None) -> str:
    if get_settings().razorpay_mock or payment_id.startswith("pay_mock_"):
        return f"rfnd_mock_{secrets.token_hex(6)}"
    resp = requests.post(
        f"{API}/payments/{payment_id}/refund",
        auth=_auth(),
        json={"amount": amount_paise, "speed": "normal", "notes": notes or {}},
        timeout=20,
    )
    if resp.status_code >= 400:
        log.error("Razorpay refund failed: %s %s", resp.status_code, resp.text)
        raise PaymentError("The refund could not be started. Check the Razorpay dashboard.")
    return resp.json()["id"]
