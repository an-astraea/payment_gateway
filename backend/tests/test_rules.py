"""Run:  python -m unittest discover -s tests   (or: pytest)
These tests cover the pure rules and need no database or external service."""
import unittest
from datetime import date, datetime, timedelta, timezone

from app import emails, policy
from app.slots import SlotRules, date_closed_reason, first_bookable_date, local_today, slot_label, slot_start

RULES = SlotRules(
    slot_times=("10:00", "14:00", "17:00"),
    duration_minutes=60,
    working_days=frozenset({0, 1, 2, 3, 4, 5}),
    min_days_ahead=1,
    horizon_days=30,
    timezone="Asia/Kolkata",
)
# Friday 16 Oct 2026, 10:00 IST = 04:30 UTC
NOW = datetime(2026, 10, 16, 4, 30, tzinfo=timezone.utc)


class SlotTests(unittest.TestCase):
    def test_labels(self):
        self.assertEqual(slot_label(RULES, "10:00"), "10:00 AM - 11:00 AM")
        self.assertEqual(slot_label(RULES, "14:00"), "2:00 PM - 3:00 PM")
        self.assertEqual(slot_label(RULES, "17:00"), "5:00 PM - 6:00 PM")

    def test_no_same_day_booking(self):
        self.assertEqual(date_closed_reason(RULES, date(2026, 10, 16), NOW), "too_soon")
        self.assertEqual(first_bookable_date(RULES, NOW), date(2026, 10, 17))

    def test_saturday_open_sunday_closed(self):
        self.assertIsNone(date_closed_reason(RULES, date(2026, 10, 17), NOW))  # Saturday
        self.assertEqual(date_closed_reason(RULES, date(2026, 10, 18), NOW), "non_working_day")  # Sunday

    def test_horizon(self):
        self.assertIsNone(date_closed_reason(RULES, date(2026, 11, 14), NOW))  # +29 days, Saturday
        self.assertEqual(date_closed_reason(RULES, date(2026, 11, 16), NOW), "beyond_horizon")  # +31 days

    def test_holiday(self):
        d = date(2026, 10, 20)
        self.assertEqual(date_closed_reason(RULES, d, NOW, {d}), "holiday")

    def test_today_uses_india_time(self):
        late_utc = datetime(2026, 10, 16, 20, 0, tzinfo=timezone.utc)  # 01:30 IST on the 17th
        self.assertEqual(local_today(RULES, late_utc), date(2026, 10, 17))

    def test_slot_start_is_ist(self):
        start = slot_start(RULES, date(2026, 10, 17), "14:00")
        self.assertEqual(start.astimezone(timezone.utc), datetime(2026, 10, 17, 8, 30, tzinfo=timezone.utc))


class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.start = slot_start(RULES, date(2026, 10, 20), "10:00")

    def test_cutoff_exactly_24_hours_allowed(self):
        self.assertTrue(policy.can_client_change(self.start, self.start - timedelta(hours=24), 24))

    def test_cutoff_inside_24_hours_blocked(self):
        self.assertFalse(policy.can_client_change(self.start, self.start - timedelta(hours=23, minutes=59), 24))

    def test_refunds(self):
        fee = 1_000_000
        self.assertEqual(policy.client_cancel_refund_paise(fee, self.start, self.start - timedelta(days=2), 24), fee)
        self.assertEqual(policy.client_cancel_refund_paise(fee, self.start, self.start - timedelta(hours=3), 24), 0)
        self.assertEqual(policy.admin_cancel_refund_paise(fee), fee)

    def test_one_reschedule(self):
        self.assertEqual(policy.reschedules_left(0, 1), 1)
        self.assertEqual(policy.reschedules_left(1, 1), 0)


class EmailTests(unittest.TestCase):
    def ctx(self, **kw):
        base = dict(
            company="Lextria Research", reference="LX-ABC123", client_name="Riya <b>", service_name="Service 1",
            date_label="Saturday, 17 October 2026", slot_label="2:00 PM - 3:00 PM IST", fee_inr=10000,
            meet_link="https://meet.google.com/abc-defg-hij", manage_link="http://localhost:5173/manage/tok",
            payment_id="pay_123",
        )
        base.update(kw)
        return emails.MailContext(**base)

    def test_indian_number_format(self):
        self.assertEqual(emails._inr(10000), "Rs 10,000")
        self.assertEqual(emails._inr(1000000), "Rs 10,00,000")
        self.assertEqual(emails._inr(500), "Rs 500")

    def test_confirmation_has_meet_and_manage_links(self):
        subject, html, text = emails.booking_confirmed(self.ctx())
        self.assertIn("Booking confirmed", subject)
        self.assertIn("https://meet.google.com/abc-defg-hij", html)
        self.assertIn("/manage/tok", html)
        self.assertIn("Rs 10,000", text)

    def test_html_is_escaped(self):
        _, html, _ = emails.booking_confirmed(self.ctx())
        self.assertIn("Riya &lt;b&gt;", html)

    def test_cancel_refund_text(self):
        _, _, text = emails.booking_cancelled(self.ctx(refund_inr=10000))
        self.assertIn("refund of Rs 10,000", text)
        _, _, text = emails.booking_cancelled(self.ctx(refund_inr=0))
        self.assertIn("No refund is due", text)


if __name__ == "__main__":
    unittest.main()
