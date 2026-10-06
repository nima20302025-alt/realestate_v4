import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import auth_service  # noqa: E402
import security  # noqa: E402

SECRET = "s" * 40


class FakeRepo:
    """In-memory stand-in for repositories.py (only what auth_service touches)."""

    def __init__(self):
        self.customers = {}
        self.codes = []  # dicts: contact, hash, attempts, used
        self.sent_24h = 0
        self.since = None
        self.merged = []
        self.next_id = 1

    def add(self, name="Guest", **extra):
        cid = self.next_id
        self.next_id += 1
        self.customers[cid] = {"customer_id": cid, "name": name, "email": None, "phone": None,
                               "phone_verified": False, "email_verified": False, **extra}
        return cid

    def auth_code_stats(self, contact):
        return {"sent_24h": self.sent_24h + len(self.codes), "seconds_since_last": self.since}

    def store_auth_code(self, contact, channel, code_hash, ttl):
        self.codes.append({"contact": contact, "hash": code_hash, "attempts": 0, "used": False})

    def check_auth_code(self, contact, code_hash, max_attempts=5):
        rows = [c for c in self.codes if c["contact"] == contact and not c["used"]]
        if not rows:
            return "expired"
        row = rows[-1]
        if row["attempts"] >= max_attempts:
            return "locked"
        if row["hash"] == code_hash:
            row["used"] = True
            return "ok"
        row["attempts"] += 1
        return "locked" if row["attempts"] >= max_attempts else "bad"

    def find_customer_by_contact(self, channel, value):
        key = "email" if channel == "email" else "phone"
        for c in self.customers.values():
            if c[key] == value:
                return c
        return None

    def get_customer(self, cid):
        return self.customers.get(cid)

    def set_customer_contact(self, cid, channel, value):
        key = "email" if channel == "email" else "phone"
        self.customers[cid][key] = value
        self.customers[cid][key + "_verified"] = True

    def create_verified_customer(self, name, channel, value):
        cid = self.add(name)
        self.set_customer_contact(cid, channel, value)
        return cid

    def merge_customers(self, a, b):
        self.merged.append((a, b))


class Sender:
    def __init__(self, fail=False):
        self.sent = []
        self.fail = fail

    def __call__(self, channel, contact, code):
        if self.fail:
            raise RuntimeError("provider down")
        self.sent.append((channel, contact, code))


def start(repo, contact="Bob@Example.com", sender=None, configured=True, dev=False):
    sender = sender or Sender()
    return auth_service.start_login(repo, contact, SECRET, is_configured=lambda ch: configured, send=sender, dev_mode=dev)


class StartTests(unittest.TestCase):
    def test_sends_code_and_masks_target(self):
        repo, sender = FakeRepo(), Sender()
        out = start(repo, sender=sender)
        self.assertEqual(out["sent_to"], "b***@example.com")
        self.assertNotIn("dev_code", out)
        self.assertEqual(sender.sent[0][:2], ("email", "bob@example.com"))
        # only a hash is stored, never the code
        self.assertNotIn(sender.sent[0][2], repo.codes[0]["hash"])

    def test_not_configured_is_refused_unless_dev(self):
        with self.assertRaises(auth_service.AuthError) as cm:
            start(FakeRepo(), configured=False)
        self.assertEqual(cm.exception.status, 503)
        out = start(FakeRepo(), configured=False, dev=True)
        self.assertRegex(out["dev_code"], r"^\d{6}$")

    def test_cooldown_and_daily_cap(self):
        repo = FakeRepo()
        repo.since = 10
        with self.assertRaises(auth_service.AuthError) as cm:
            start(repo)
        self.assertEqual(cm.exception.status, 429)
        repo.since, repo.sent_24h = 3600, 6
        with self.assertRaises(auth_service.AuthError) as cm:
            start(repo)
        self.assertEqual(cm.exception.status, 429)

    def test_provider_failure_is_a_clean_502(self):
        with self.assertRaises(auth_service.AuthError) as cm:
            start(FakeRepo(), sender=Sender(fail=True))
        self.assertEqual(cm.exception.status, 502)
        self.assertNotIn("provider down", cm.exception.message)

    def test_bad_contact(self):
        with self.assertRaises(auth_service.AuthError) as cm:
            start(FakeRepo(), contact="nope")
        self.assertEqual(cm.exception.status, 400)


def verify(repo, code, current, contact="bob@example.com"):
    return auth_service.verify_login(repo, contact, code, current, SECRET)


class VerifyTests(unittest.TestCase):
    def issue(self, repo, contact="bob@example.com"):
        sender = Sender()
        start(repo, contact=contact, sender=sender)
        return sender.sent[-1][2]

    def test_guest_gets_the_contact_attached(self):
        repo = FakeRepo()
        guest = repo.add()
        code = self.issue(repo)
        out = verify(repo, code, guest)
        self.assertEqual(out, {"customer_id": guest, "switched": False, "merged": False})
        self.assertTrue(repo.customers[guest]["email_verified"])

    def test_existing_account_wins_and_guest_data_is_merged(self):
        repo = FakeRepo()
        owner = repo.add("Bob", email="bob@example.com")
        guest = repo.add()
        out = verify(repo, self.issue(repo), guest)
        self.assertEqual(out["customer_id"], owner)
        self.assertTrue(out["switched"] and out["merged"])
        self.assertEqual(repo.merged, [(guest, owner)])

    def test_verified_account_is_not_merged_into_another(self):
        repo = FakeRepo()
        owner = repo.add("Bob", email="bob@example.com")
        other = repo.add("Eve", phone="+12065550123", phone_verified=True)
        out = verify(repo, self.issue(repo), other)
        self.assertTrue(out["switched"])
        self.assertFalse(out["merged"])
        self.assertEqual(repo.merged, [])
        self.assertEqual(out["customer_id"], owner)

    def test_no_session_creates_account(self):
        repo = FakeRepo()
        out = verify(repo, self.issue(repo), None)
        self.assertTrue(repo.customers[out["customer_id"]]["email_verified"])

    def test_wrong_code_then_lockout_even_with_the_right_code(self):
        repo = FakeRepo()
        guest = repo.add()
        good = self.issue(repo)
        wrong = "000000" if good != "000000" else "111111"
        for i in range(4):
            with self.assertRaises(auth_service.AuthError) as cm:
                verify(repo, wrong, guest)
            self.assertEqual(cm.exception.status, 400)
        with self.assertRaises(auth_service.AuthError) as cm:
            verify(repo, wrong, guest)
        self.assertEqual(cm.exception.status, 429)  # fifth miss locks the code
        with self.assertRaises(auth_service.AuthError):
            verify(repo, good, guest)  # too late, even for the right code

    def test_code_is_single_use_and_bound_to_the_contact(self):
        repo = FakeRepo()
        guest = repo.add()
        code = self.issue(repo)
        verify(repo, code, guest)
        with self.assertRaises(auth_service.AuthError):
            verify(repo, code, guest)  # already used
        other = self.issue(repo, contact="eve@example.com")
        with self.assertRaises(auth_service.AuthError):
            verify(repo, other, guest, contact="bob@example.com")  # code belongs to eve

    def test_format(self):
        with self.assertRaises(auth_service.AuthError) as cm:
            verify(FakeRepo(), "12", None)
        self.assertEqual(cm.exception.status, 400)


if __name__ == "__main__":
    unittest.main()
