# -*- coding: utf-8 -*-
"""Unit tests for matching.py. Run with: pytest"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import patch

from matching import format_comparison, format_property_details, score_properties


def _property(**overrides):
    base = {
        "property_id": "P00001",
        "price": 700_000,
        "bedrooms": 3,
        "parking": 1,
        "pet_friendly": 1,
        "near_metro": 0,
        "garden": 0,
        "balcony": 0,
        "pool": 0,
        "elevator": 0,
        "furnished": 0,
        "city": "Toronto",
        "neighborhood": "Downtown",
        "property_type": "Condo",
        "area_sqft": 900,
        "year_built": 2015,
        "property_condition": "Good",
        "description": "Bright condo downtown.",
    }
    base.update(overrides)
    return base


@patch("matching.get_taste_insights", return_value=[])
@patch("matching.get_customer_interactions", return_value=[])
def test_perfect_match_scores_high(_mock_int, _mock_taste):
    requirements = {"budget_preferred": 700_000, "bedrooms": 3, "parking": True, "pet_friendly": True}
    [scored] = score_properties([_property()], requirements)
    assert scored["match_score"] >= 90


@patch("matching.get_taste_insights", return_value=[])
@patch("matching.get_customer_interactions", return_value=[])
def test_missing_bedrooms_scores_lower_than_matching(_mock_int, _mock_taste):
    requirements = {"budget_preferred": 700_000, "bedrooms": 4}
    [scored] = score_properties([_property(bedrooms=3)], requirements)
    [scored_match] = score_properties([_property(bedrooms=4)], requirements)
    assert scored["match_score"] < scored_match["match_score"]


@patch("matching.get_taste_insights", return_value=[])
@patch("matching.get_customer_interactions")
def test_rejected_property_is_penalized(mock_interactions, _mock_taste):
    mock_interactions.return_value = [
        {"property_id": "P00001", "action": "reject", "reason": "too expensive", "created_at": ""}
    ]
    requirements = {"budget_preferred": 700_000}
    [scored] = score_properties([_property()], requirements, customer_id=1)
    mock_interactions.return_value = []
    [scored_no_history] = score_properties([_property()], requirements, customer_id=2)
    assert scored["match_score"] < scored_no_history["match_score"]


@patch("matching.get_customer_interactions", return_value=[])
@patch("matching.get_taste_insights")
def test_taste_insight_boosts_matching_flag(mock_taste, _mock_int):
    mock_taste.return_value = [
        {"insight": "must have parking", "source_action": "like", "weight": 1.5, "reason": None}
    ]
    requirements = {"budget_preferred": 700_000}
    [with_parking] = score_properties([_property(parking=1)], requirements, customer_id=1)
    [without] = score_properties([_property(parking=0)], requirements, customer_id=1)
    assert with_parking["match_score"] > without["match_score"]


@patch("matching.get_taste_insights", return_value=[])
@patch("matching.get_customer_interactions", return_value=[])
def test_score_is_clamped_between_0_and_100(_mock_int, _mock_taste):
    requirements = {
        "budget_preferred": 700_000,
        "bedrooms": 1,
        "parking": True,
        "pet_friendly": True,
        "near_metro": True,
    }
    [scored] = score_properties([_property(bedrooms=5)], requirements)
    assert 0 <= scored["match_score"] <= 100


def test_format_property_details_includes_id():
    text = format_property_details(_property())
    assert "P00001" in text
    assert "Toronto" in text


def test_format_comparison_has_rows():
    a = _property(property_id="P00001", parking=1)
    b = _property(property_id="P00002", parking=0, price=650_000)
    text = format_comparison([a, b])
    assert "P00001" in text and "P00002" in text
    assert "Parking" in text
