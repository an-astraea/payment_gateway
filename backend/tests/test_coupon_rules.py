import unittest
from datetime import datetime, timedelta, timezone

from app import coupon_rules as r
from app import emails


class CouponRuleTests(unittest.TestCase):
    def test_code_format(self):
        for _ in range(200):
            code = r.new_code()
            self.assertTrue(r.looks_valid(code), code)
            self.assertTrue(code.startswith("LEX-"))
            self.assertFalse(set(code[4:]) & set("01IO"))  # no look-alike characters

    def test_normalize(self):
        self.assertEqual(r.normalize("  lex-7kq2m "), "LEX-7KQ2M")
        self.assertEqual(r.normalize("LEX7KQ2M"), "LEX-7KQ2M")
        self.assertFalse(r.looks_valid(r.normalize("HELLO")))

    def test_discounts(self):
        fee = 1_000_000  # Rs 10,000
        self.assertEqual(r.discount_paise(fee, 25), 250_000)
        self.assertEqual(r.discount_paise(fee, 50), 500_000)
        self.assertEqual(r.discount_paise(fee, 75), 750_000)
        self.assertEqual(r.discount_paise(fee, 100), fee)  # free booking
        self.assertEqual(r.discount_paise(99_900, 25), 24_900)  # Rs 999 -> Rs 249 off (whole rupees)
        with self.assertRaises(ValueError):
            r.discount_paise(fee, 30)

    def test_status(self):
        now = datetime(2026, 10, 20, 10, tzinfo=timezone.utc)
        later, earlier = now + timedelta(hours=1), now - timedelta(seconds=1)
        self.assertEqual(r.status(True, None, later, now), r.UNUSED)
        self.assertEqual(r.status(True, None, earlier, now), r.EXPIRED)
        self.assertEqual(r.status(False, None, later, now), r.DEACTIVATED)
        self.assertEqual(r.status(True, now, earlier, now), r.USED)  # used stays used

    def test_coupon_email(self):
        subject, html, text = emails.coupon_issued("Lextria Research", "LEX-7KQ2M", 25, "21 Oct 2026, 3:00 PM IST", "http://x/book", 24, True)
        self.assertIn("25%", subject)
        self.assertIn("LEX-7KQ2M", html)
        self.assertIn("only with this email", text)


if __name__ == "__main__":
    unittest.main()