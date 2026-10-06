import os
import sys
import unittest
from datetime import date, datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from webutils import (  # noqa: E402
    build_ics,
    compare_winners,
    extract_address,
    parse_slot,
    pct_vs,
    to_card,
)

PROP = {
    "property_id": "USA00001",
    "city": "Seattle",
    "neighborhood": "Ballard",
    "property_type": "House",
    "listing_type": "Sale",
    "price": 900000,
    "bedrooms": 3,
    "bathrooms": 2,
    "area_sqft": 1800,
    "year_built": 1999,
    "parking": 1,
    "description": "House in Ballard, Seattle (WA 98107). Address: 123 Main St. Nice.",
}


class WebUtilsTests(unittest.TestCase):
    def test_card_fields(self):
        c = to_card(PROP)
        self.assertEqual(c["price_per_sqft"], 500)
        self.assertTrue(c["parking"])
        self.assertFalse(c["garden"])
        self.assertEqual(c["address"], "123 Main St, Seattle, WA 98107")
        self.assertIn("google.com/maps", c["maps_url"])

    def test_address_missing(self):
        self.assertEqual(extract_address(None), {"street": None, "statezip": None})

    def test_winners(self):
        a = to_card(PROP)
        b = to_card({**PROP, "property_id": "USA00002", "price": 700000, "area_sqft": 1600, "year_built": 1980})
        w = compare_winners([a, b])
        self.assertEqual(w["price"], ["USA00002"])
        self.assertEqual(w["area_sqft"], ["USA00001"])
        self.assertIn(w["overall"], ("USA00001", "USA00002"))

    def test_all_tied_is_no_winner(self):
        a = to_card(PROP)
        b = to_card({**PROP, "property_id": "USA00002"})
        w = compare_winners([a, b])
        self.assertIsNone(w["price"])
        self.assertIsNone(w["overall"])

    def test_slot_validation(self):
        today = date(2026, 10, 3)
        self.assertEqual(parse_slot("2026-10-05", "10:00", today), date(2026, 10, 5))
        for d, t in [("nope", "10:00"), ("2026-10-05", "10:30"), ("2026-10-05", "08:00"), ("2026-09-20", "10:00"), ("2027-12-01", "10:00")]:
            with self.assertRaises(ValueError):
                parse_slot(d, t, today)

    def test_ics(self):
        ics = build_ics(
            {"appointment_id": 7, "property_id": "USA00001", "appointment_date": "2026-10-06", "appointment_time": "10:00",
             "property_type": "House", "neighborhood": "Ballard", "city": "Seattle", "price": 900000,
             "notes": "bringing kids, parking; thanks", "address": "123 Main St, Seattle, WA 98107"},
            now=datetime(2026, 10, 3, tzinfo=timezone.utc),
        )
        self.assertIn("DTSTART:20261006T100000", ics)
        self.assertIn("DTEND:20261006T110000", ics)
        self.assertIn("UID:viewing-7@luxehome", ics)
        self.assertIn("bringing kids\\, parking\\; thanks", ics)
        self.assertTrue(ics.endswith("END:VCALENDAR\r\n"))

    def test_pct(self):
        self.assertEqual(pct_vs(900, 1000), -10.0)
        self.assertIsNone(pct_vs(None, 1000))


if __name__ == "__main__":
    unittest.main()
