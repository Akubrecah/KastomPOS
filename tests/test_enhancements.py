# Tests for KastomPOS Swahili translation and item expiry date helper logic

import pytest
from datetime import datetime, date
from app.core.translations import translate

def test_translation_swahili():
    # Test translation to Swahili
    assert translate("Home", "sw") == "Nyumbani"
    assert translate("Dashboard", "sw") == "Dashibodi"
    assert translate("POS", "sw") == "POS"
    
    # Test translation fallback to English when lang is en
    assert translate("Home", "en") == "Home"
    assert translate("Dashboard", "en") == "Dashboard"
    
    # Test fallback to input string when key is not found
    assert translate("Unknown Key", "sw") == "Unknown Key"
    assert translate("Unknown Key", "en") == "Unknown Key"

def parse_expiry_date(expiry_date_str):
    if expiry_date_str:
        try:
            return datetime.strptime(expiry_date_str, "%Y-%m-%d").date()
        except ValueError:
            pass
    return None

def test_expiry_date_parsing():
    # Valid date format
    assert parse_expiry_date("2026-06-14") == date(2026, 6, 14)
    assert parse_expiry_date("2027-12-31") == date(2027, 12, 31)
    
    # Invalid date formats
    assert parse_expiry_date("14-06-2026") is None
    assert parse_expiry_date("invalid-date") is None
    
    # Empty and None values
    assert parse_expiry_date("") is None
    assert parse_expiry_date(None) is None
