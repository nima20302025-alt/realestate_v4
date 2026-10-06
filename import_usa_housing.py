# -*- coding: utf-8 -*-
"""
Import USA Housing Dataset.csv (King County / Seattle area) into Supabase properties.

Usage:
    python import_usa_housing.py --csv ../USA_Housing_Dataset.csv --reset
    python import_usa_housing.py --csv path/to/file.csv --limit 2000 --cities "Seattle,Bellevue"
"""
from __future__ import annotations

import argparse
import logging
import math
import re
from pathlib import Path
from typing import Any, List, Optional, Tuple

import pandas as pd

import config
from database import get_connection, init_db

logger = logging.getLogger(__name__)

CONDITION_MAP = {
    1: "Poor",
    2: "Fair",
    3: "Average",
    4: "Good",
    5: "Excellent",
}


def _to_int(val: Any, default: Optional[int] = None) -> Optional[int]:
    if val is None or (isinstance(val, float) and math.isnan(val)):
        return default
    try:
        s = str(val).strip().replace(",", "").replace("$", "")
        if not s or s.lower() in ("nan", "none", "-", "n/a"):
            return default
        return int(float(s))
    except (ValueError, TypeError):
        return default


def _to_float(val: Any, default: float = 0.0) -> float:
    try:
        if val is None or (isinstance(val, float) and math.isnan(val)):
            return default
        return float(val)
    except (ValueError, TypeError):
        return default


def _neighborhood_from_street(street: str, city: str) -> str:
    """Best-effort neighborhood label from street / city."""
    if not street:
        return city or "Unknown"
    # Use last meaningful token of street as a soft neighborhood hint
    tokens = re.findall(r"[A-Za-z]+", str(street))
    if len(tokens) >= 2:
        return " ".join(tokens[-2:]).title()
    return city or "Unknown"


def _guess_property_type(floors: float, bedrooms: int) -> str:
    if floors and floors >= 2.5:
        return "Townhouse"
    if bedrooms <= 2 and floors and floors >= 2:
        return "Condo"
    return "House"


def row_to_record(idx: int, row: pd.Series) -> Optional[Tuple]:
    price = _to_int(row.get("price"))
    if price is None or price < 50_000 or price > 30_000_000:
        return None

    bedrooms = max(0, min(_to_int(row.get("bedrooms"), 1) or 1, 15))
    baths_f = _to_float(row.get("bathrooms"), 1.0)
    bathrooms = max(1, min(int(round(baths_f)), 15))

    area = _to_int(row.get("sqft_living"))
    if area is None or area < 100:
        area = max(400, bedrooms * 350)
    area = min(area, 50_000)

    city = str(row.get("city") or "").strip()
    if not city:
        return None
    city = city.title() if city.islower() or city.isupper() else city

    street = str(row.get("street") or "").strip()
    neighborhood = _neighborhood_from_street(street, city)

    floors = _to_float(row.get("floors"), 1.0)
    prop_type = _guess_property_type(floors, bedrooms)

    year_built = _to_int(row.get("yr_built"))
    cond_raw = _to_int(row.get("condition"), 3) or 3
    condition = CONDITION_MAP.get(cond_raw, "Average")

    waterfront = 1 if _to_int(row.get("waterfront"), 0) else 0
    view = _to_int(row.get("view"), 0) or 0
    # Soft flags from available signals
    pool = 0  # not in this dataset
    garden = 1 if waterfront or view >= 2 else 0
    parking = 1 if area > 1200 else 0  # weak heuristic
    near_metro = 1 if city.lower() == "seattle" and area < 2000 else 0

    statezip = str(row.get("statezip") or "").strip()
    description_parts = [
        f"{prop_type} in {neighborhood}, {city}" + (f" ({statezip})" if statezip else "") + ".",
        f"{bedrooms} bed / {bathrooms} bath, {area} sqft, listed at ${price:,}.",
    ]
    if street:
        description_parts.append(f"Address: {street}.")
    if year_built:
        description_parts.append(f"Built {year_built}.")
    if waterfront:
        description_parts.append("Waterfront property.")
    if view:
        description_parts.append(f"View score: {view}.")
    description = " ".join(description_parts)

    property_id = f"USA{idx + 1:05d}"

    return (
        property_id,
        city,
        neighborhood[:80],
        prop_type,
        "Sale",
        price,
        bedrooms,
        bathrooms,
        area,
        parking,
        0,  # furnished
        0,  # balcony
        garden,
        pool,
        0,  # elevator
        0,  # pet_friendly
        near_metro,
        year_built,
        condition,
        description[:1000],
    )


def import_csv(
    csv_path: Path,
    reset: bool,
    limit: Optional[int],
    cities: Optional[List[str]],
) -> int:
    init_db()
    df = pd.read_csv(csv_path, low_memory=False)
    logger.info("Loaded %d rows from %s", len(df), csv_path)

    required = {"price", "city", "bedrooms", "sqft_living"}
    missing = required - set(df.columns)
    if missing:
        raise SystemExit(f"CSV missing required columns: {missing}. Found: {list(df.columns)}")

    if cities:
        allowed = {c.strip().lower() for c in cities}
        df = df[df["city"].astype(str).str.strip().str.lower().isin(allowed)]
        logger.info("After city filter %s: %d rows", cities, len(df))

    df = df.dropna(subset=["price", "city"])
    # drop zero / nonsense prices
    df = df[df["price"] > 0]
    if limit:
        df = df.head(limit)

    records: List[Tuple] = []
    for i, (_, row) in enumerate(df.iterrows()):
        rec = row_to_record(i, row)
        if rec:
            records.append(rec)

    insert_sql = """
        INSERT INTO properties (
            property_id, city, neighborhood, property_type, listing_type,
            price, bedrooms, bathrooms, area_sqft,
            parking, furnished, balcony, garden, pool, elevator,
            pet_friendly, near_metro, year_built, property_condition, description
        ) VALUES (
            %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s
        )
        ON CONFLICT (property_id) DO UPDATE SET
            city = EXCLUDED.city,
            neighborhood = EXCLUDED.neighborhood,
            price = EXCLUDED.price,
            bedrooms = EXCLUDED.bedrooms,
            bathrooms = EXCLUDED.bathrooms,
            area_sqft = EXCLUDED.area_sqft,
            description = EXCLUDED.description
    """
    chunk_size = 200

    with get_connection() as conn:
        with conn.cursor() as cur:
            if reset:
                cur.execute("DELETE FROM property_interactions")
                cur.execute("DELETE FROM appointments")
                cur.execute("DELETE FROM properties")
            for start in range(0, len(records), chunk_size):
                chunk = records[start : start + chunk_size]
                cur.executemany(insert_sql, chunk)
                logger.info("Inserted %d / %d", min(start + chunk_size, len(records)), len(records))

    logger.info("Imported %d properties into Supabase", len(records))
    return len(records)


def main() -> None:
    config.configure_logging()
    parser = argparse.ArgumentParser(description="Import USA Housing Dataset into Supabase.")
    parser.add_argument("--csv", required=True, help="Path to USA Housing Dataset.csv")
    parser.add_argument("--reset", action="store_true", help="Clear properties first")
    parser.add_argument("--limit", type=int, default=None, help="Max rows to import")
    parser.add_argument(
        "--cities",
        type=str,
        default="",
        help="Comma-separated cities to keep (e.g. 'Seattle,Bellevue,Redmond')",
    )
    args = parser.parse_args()

    # Surface missing DATABASE_URL early with a clear message
    if not config.DATABASE_URL:
        raise SystemExit(
            "ERROR: DATABASE_URL is empty.\n"
            "→ Colab Secrets: create DATABASE_URL, enable notebook access, re-run secrets cell.\n"
            "→ Supabase: Project Settings → Database → Connection string (URI)."
        )

    path = Path(args.csv)
    if not path.exists():
        raise SystemExit(f"File not found: {path}")
    cities = [c.strip() for c in args.cities.split(",") if c.strip()] or None
    try:
        n = import_csv(path, reset=args.reset, limit=args.limit, cities=cities)
    except Exception as exc:
        raise SystemExit(f"Import failed: {exc}") from exc
    print(f"Imported {n:,} listings → Supabase")


if __name__ == "__main__":
    main()
