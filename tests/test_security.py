import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import security  # noqa: E402

SECRET = "x" * 40


class SessionTokenTests(unittest.TestCase):
    def test_roundtrip(self):
        tok = security.make_session_token(42, SECRET, days=1, now=1000)
        self.assertEqual(security.read_session_token(tok, SECRET, now=1001), 42)

    def test_expired(self):
        tok = security.make_session_token(42, SECRET, days=1, now=1000)
        self.assertIsNone(security.read_session_token(tok, SECRET, now=1000 + 86400 + 1))

    def test_wrong_secret_and_tampering(self):
        tok = security.make_session_token(42, SECRET, now=1000)
        self.assertIsNone(security.read_session_token(tok, "y" * 40, now=1001))
        payload, sig = tok.split(".")
        forged = security.make_session_token(7, SECRET, now=1000).split(".")[0]
        self.assertIsNone(security.read_session_token(forged + "." + sig, SECRET, now=1001))

    def test_garbage(self):
        for bad in (None, "", "abc", "a.b.c", "." * 3, "é.é", "x" * 600):
            self.assertIsNone(security.read_session_token(bad, SECRET))


class ContactTests(unittest.TestCase):
    def test_email(self):
        self.assertEqual(security.normalize_contact("  Bob@Example.COM "), ("email", "bob@example.com"))

    def test_phone_variants(self):
        for raw in ("(206) 555-0123", "206-555-0123", "1 206 555 0123", "+1 206 555 0123"):
            self.assertEqual(security.normalize_contact(raw), ("phone", "+12065550123"))
        self.assertEqual(security.normalize_contact("+98 912 345 6789"), ("phone", "+989123456789"))

    def test_invalid(self):
        for raw in ("", "abc", "12345", "a@b", "@x.com", "0912 345 6789"):
            with self.assertRaises(ValueError):
                security.normalize_contact(raw)

    def test_mask(self):
        self.assertEqual(security.mask_contact("email", "bob@example.com"), "b***@example.com")
        self.assertTrue(security.mask_contact("phone", "+12065550123").endswith("23"))
        self.assertNotIn("5550", security.mask_contact("phone", "+12065550123"))


class CodeTests(unittest.TestCase):
    def test_code_shape_and_binding(self):
        code = security.new_code()
        self.assertRegex(code, r"^\d{6}$")
        a = security.hash_code("a@b.com", code, SECRET)
        self.assertNotEqual(a, security.hash_code("c@d.com", code, SECRET))
        self.assertNotEqual(a, security.hash_code("a@b.com", code, "z" * 40))


class RateLimiterTests(unittest.TestCase):
    def test_window(self):
        rl = security.RateLimiter()
        for i in range(3):
            self.assertTrue(rl.check("k", 3, 60, now=100 + i)[0])
        ok, retry = rl.check("k", 3, 60, now=103)
        self.assertFalse(ok)
        self.assertGreaterEqual(retry, 1)
        self.assertLessEqual(retry, 61)
        self.assertTrue(rl.check("k", 3, 60, now=161)[0])  # oldest hit expired

    def test_keys_are_independent(self):
        rl = security.RateLimiter()
        self.assertTrue(rl.check("a", 1, 60, now=1)[0])
        self.assertFalse(rl.check("a", 1, 60, now=2)[0])
        self.assertTrue(rl.check("b", 1, 60, now=2)[0])

    def test_rejected_calls_do_not_extend_the_block(self):
        rl = security.RateLimiter()
        rl.check("k", 1, 10, now=0)
        for t in range(1, 9):
            rl.check("k", 1, 10, now=t)
        self.assertTrue(rl.check("k", 1, 10, now=11)[0])


if __name__ == "__main__":
    unittest.main()
