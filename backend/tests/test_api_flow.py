"""End-to-end API test in MOCK payment mode (no Razorpay, Google or SMTP needed).
Run after installing requirements:  pytest -q   (or python -m unittest discover -s tests -t .)"""
import os
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path

DB = Path(__file__).with_name("test_booking.db")
os.environ.update(
    DATABASE_URL=f"sqlite:///{DB}",
    RAZORPAY_KEY_ID="",
    RAZORPAY_KEY_SECRET="",
    GOOGLE_REFRESH_TOKEN="",
    SMTP_USERNAME="",
    SMTP_PASSWORD="",
)
if DB.exists():
    DB.unlink()

try:
    from fastapi.testclient import TestClient
except ImportError:  # requirements not installed
    TestClient = None


@unittest.skipIf(TestClient is None, "Install backend requirements to run the API tests")
class BookingFlowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from app.main import app

        cls.ctx = TestClient(app)
        cls.client = cls.ctx.__enter__()
        days = cls.client.get("/api/availability").json()
        min_day = date.today() + timedelta(days=3)  # far enough to allow changes (24 h cut-off)
        cls.day = next(d["date"] for d in days if d["open"] and date.fromisoformat(d["date"]) >= min_day)

    @classmethod
    def tearDownClass(cls):
        cls.ctx.__exit__(None, None, None)

    # helpers
    def hold(self, time, email="riya@example.com"):
        return self.client.post(
            "/api/bookings/hold",
            json={"service_id": 1, "date": self.day, "time": time, "name": "Riya Sharma", "email": email, "phone": "+91 98765 43210"},
        )

    def pay(self, order_id, n):
        return self.client.post(
            "/api/bookings/verify",
            json={"razorpay_order_id": order_id, "razorpay_payment_id": f"pay_mock_{n}", "razorpay_signature": "mock_signature"},
        )

    def free_times(self):
        day = self.client.get("/api/availability", params={"start": self.day, "days": 1}).json()[0]
        return [s["time"] for s in day["slots"] if s["available"]]

    def token(self, reference):
        from sqlalchemy import select

        from app.database import SessionLocal
        from app.models import Booking

        with SessionLocal() as db:
            return db.scalar(select(Booking.manage_token).where(Booking.reference == reference))

    # the flow, in order
    def test_full_flow(self):
        services = self.client.get("/api/services").json()
        self.assertEqual([s["name"] for s in services], ["Service 1", "Service 2", "Service 3"])
        self.assertEqual(services[0]["fee_inr"], 10000)
        self.assertEqual(self.free_times(), ["10:00", "14:00", "17:00"])

        # 1. hold + double-booking protection
        held = self.hold("10:00")
        self.assertEqual(held.status_code, 200, held.text)
        self.assertTrue(held.json()["order"]["mock"])
        self.assertEqual(self.hold("10:00", "arjun@example.com").status_code, 409)
        self.assertEqual(self.free_times(), ["14:00", "17:00"])  # held slot hidden

        # 2. payment confirms the booking
        paid = self.pay(held.json()["order"]["id"], 1)
        self.assertEqual(paid.json()["status"], "confirmed")
        self.assertEqual(self.free_times(), ["14:00", "17:00"])  # only 2 slots left
        bad = self.client.post(
            "/api/bookings/verify",
            json={"razorpay_order_id": held.json()["order"]["id"], "razorpay_payment_id": "x", "razorpay_signature": "forged"},
        )
        self.assertEqual(bad.status_code, 400)

        # 3. admin dashboard + assignment
        admin_day = self.client.get("/api/admin/days", params={"start": self.day, "days": 1}).json()[0]
        self.assertEqual(admin_day["booked_count"], 1)
        booking_id = admin_day["slots"][0]["booking"]["id"]
        emp = self.client.post("/api/admin/employees", json={"name": "Anusha", "email": "anusha@lextria.in"}).json()
        assigned = self.client.post(f"/api/admin/bookings/{booking_id}/assign", json={"employee_id": emp["id"]}).json()
        self.assertEqual(assigned["employee_name"], "Anusha")

        # 4. reschedule once, then blocked
        token = self.token(held.json()["reference"])
        moved = self.client.post(f"/api/manage/{token}/reschedule", json={"date": self.day, "time": "14:00"})
        self.assertEqual(moved.status_code, 200, moved.text)
        self.assertEqual(self.free_times(), ["10:00", "17:00"])
        again = self.client.post(f"/api/manage/{token}/reschedule", json={"date": self.day, "time": "10:00"})
        self.assertEqual(again.status_code, 400)

        # 5. cancel more than 24 h before: full refund, slot freed
        cancelled = self.client.post(f"/api/manage/{token}/cancel").json()
        self.assertEqual(cancelled["status"], "cancelled")
        self.assertEqual(cancelled["refund_inr"], 10000)
        self.assertEqual(self.free_times(), ["10:00", "14:00", "17:00"])

        # 6. closing checkout releases the slot at once
        h2 = self.hold("17:00").json()
        self.client.post("/api/bookings/release", json={"razorpay_order_id": h2["order"]["id"]})
        self.assertIn("17:00", self.free_times())

        # 7. late payment after someone else took the slot: refunded
        h3 = self.hold("17:00", "arjun@example.com").json()
        self.pay(h3["order"]["id"], 3)
        late = self.pay(h2["order"]["id"], 2).json()
        self.assertEqual(late["status"], "refunded_conflict")
        self.assertEqual(late["refund_inr"], 10000)

        # 8. abandoned hold expires after HOLD_MINUTES
        from app.database import SessionLocal
        from app.models import Booking

        h4 = self.hold("10:00").json()
        with SessionLocal() as db:
            from sqlalchemy import update

            db.execute(update(Booking).where(Booking.reference == h4["reference"]).values(hold_expires_at=datetime(2000, 1, 1)))
            db.commit()
        self.assertIn("10:00", self.free_times())


@unittest.skipIf(TestClient is None, "Install backend requirements to run the API tests")
class CouponFlowTest(BookingFlowTest):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        days = cls.client.get("/api/availability").json()
        cls.day = next(d["date"] for d in days if d["open"] and d["date"] > cls.day)  # a fresh date

    def hold(self, time, email="riya@example.com", coupon=None):
        body = {"service_id": 1, "date": self.day, "time": time, "name": "Riya Sharma", "email": email, "phone": "+91 98765 43210"}
        if coupon:
            body["coupon_code"] = coupon
        return self.client.post("/api/bookings/hold", json=body)

    def test_full_flow(self):  # replaces the parent test in this class
        pass

    def test_coupon_flow(self):
        # generate first (no email yet), then send it to the client
        c = self.client.post("/api/admin/coupons", json={"percent": 25})
        self.assertEqual(c.status_code, 201, c.text)
        code = c.json()["code"]
        self.assertRegex(code, r"^LEX-[A-Z0-9]{5}$")
        self.assertEqual((c.json()["status"], c.json()["client_email"]), ("unused", ""))
        sent = self.client.post(f"/api/admin/coupons/{c.json()['id']}/send", json={"client_email": "meera@example.com"})
        self.assertEqual(sent.json()["client_email"], "meera@example.com")

        # preview on the payment step
        chk = self.client.post("/api/coupons/check", json={"code": code.lower(), "service_id": 1, "email": "meera@example.com"}).json()
        self.assertEqual((chk["base_fee_inr"], chk["discount_inr"], chk["total_inr"]), (10000, 2500, 7500))

        # locked to the email it was sent to
        wrong = self.client.post("/api/coupons/check", json={"code": code, "service_id": 1, "email": "other@example.com"})
        self.assertEqual(wrong.status_code, 400)
        self.assertEqual(wrong.json()["detail"]["code"], "coupon")

        # closing the payment window does not use up the coupon
        h1 = self.hold("17:00", "meera@example.com", code).json()
        self.assertEqual(h1["order"]["amount_paise"], 750_000)
        self.client.post("/api/bookings/release", json={"razorpay_order_id": h1["order"]["id"]})
        self.assertEqual(self.client.post("/api/coupons/check", json={"code": code, "service_id": 1, "email": "meera@example.com"}).status_code, 200)

        # paying uses it for good
        h2 = self.hold("17:00", "meera@example.com", code).json()
        paid = self.pay(h2["order"]["id"], 50).json()
        self.assertEqual((paid["fee_inr"], paid["discount_inr"], paid["coupon_code"]), (7500, 2500, code))
        again = self.client.post("/api/coupons/check", json={"code": code, "service_id": 1, "email": "meera@example.com"})
        self.assertIn("already been used", again.json()["detail"]["message"])

        listed = {x["code"]: x for x in self.client.get("/api/admin/coupons").json()}
        self.assertEqual(listed[code]["status"], "used")
        self.assertEqual(listed[code]["amount_paid_inr"], 7500)
        self.assertEqual(self.client.post(f"/api/admin/coupons/{listed[code]['id']}/deactivate").status_code, 400)

        # deactivated and expired coupons are rejected
        c2 = self.client.post("/api/admin/coupons", json={"percent": 75, "client_email": "meera@example.com"}).json()
        self.client.post(f"/api/admin/coupons/{c2['id']}/deactivate")
        d = self.client.post("/api/coupons/check", json={"code": c2["code"], "service_id": 1, "email": "meera@example.com"})
        self.assertIn("no longer valid", d.json()["detail"]["message"])

        c3 = self.client.post("/api/admin/coupons", json={"percent": 50, "client_email": "meera@example.com"}).json()
        from sqlalchemy import update

        from app.database import SessionLocal
        from app.models import Coupon

        with SessionLocal() as db:
            db.execute(update(Coupon).where(Coupon.id == c3["id"]).values(expires_at=datetime(2000, 1, 1)))
            db.commit()
        e = self.client.post("/api/coupons/check", json={"code": c3["code"], "service_id": 1, "email": "meera@example.com"})
        self.assertIn("expired", e.json()["detail"]["message"])

        # only 25 / 50 / 75 / 100 allowed
        self.assertEqual(self.client.post("/api/admin/coupons", json={"percent": 30}).status_code, 422)

        # an unsent coupon is not locked to any email
        open_c = self.client.post("/api/admin/coupons", json={"percent": 50}).json()
        ok = self.client.post("/api/coupons/check", json={"code": open_c["code"], "service_id": 1, "email": "anyone@example.com"})
        self.assertEqual(ok.json()["total_inr"], 5000)

        # 100%: free booking, confirmed with no payment step
        free = self.client.post("/api/admin/coupons", json={"percent": 100, "client_email": "ravi@example.com"}).json()
        h = self.hold("10:00", "ravi@example.com", free["code"]).json()
        self.assertIsNone(h["order"])
        self.assertEqual((h["booking"]["status"], h["booking"]["fee_inr"], h["booking"]["discount_inr"]), ("confirmed", 0, 10000))
        listed = {x["code"]: x for x in self.client.get("/api/admin/coupons").json()}
        self.assertEqual(listed[free["code"]]["status"], "used")
        token = self.token(h["reference"])
        cancelled = self.client.post(f"/api/manage/{token}/cancel").json()
        self.assertEqual((cancelled["status"], cancelled["refund_inr"]), ("cancelled", 0))


if __name__ == "__main__":
    unittest.main()