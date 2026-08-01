"""Unit tests for the cleaning pipeline. Run with: pytest -q"""
import os
import sys

import numpy as np
import pandas as pd
import pytest

# Make src/ importable when running pytest from project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils import (
    NULL_LIKE,
    clean_column_names,
    normalize_missing,
    normalize_string_series,
    to_numeric_clean,
    parse_mixed_dates,
)
from src.pipeline import (
    stage_rename_columns,
    stage_handle_missing_tokens,
    stage_clean_strings,
    stage_parse_dates,
    stage_cast_types,
    stage_deduplicate,
)


# ---- utils ----

def test_clean_column_names_snake_cases():
    df = pd.DataFrame(columns=["  Order ID ", "Unit$Price ", " DATE "])
    out = clean_column_names(df)
    assert list(out.columns) == ["order_id", "unit_price", "date"]


def test_normalize_missing_handles_null_like_tokens():
    df = pd.DataFrame({"x": ["N/A", "?", "ok", "", "NULL", "  -  ", "0"]})
    out = normalize_missing(df)
    # '0' survives (real value), rest become NaN
    assert pd.isna(out["x"].iloc[0])
    assert pd.isna(out["x"].iloc[1])
    assert out["x"].iloc[2] == "ok"
    assert pd.isna(out["x"].iloc[3])
    assert pd.isna(out["x"].iloc[4])
    assert pd.isna(out["x"].iloc[5])
    assert out["x"].iloc[6] == "0"


def test_to_numeric_clean_strips_commas_and_currency():
    s = pd.Series(['"1,299.99"', "$24.99", "1,000", "abc", None])
    out = to_numeric_clean(s)
    assert out.iloc[0] == 1299.99
    assert out.iloc[1] == 24.99
    assert out.iloc[2] == 1000.0
    assert pd.isna(out.iloc[3])
    assert pd.isna(out.iloc[4])


def test_parse_mixed_dates_handles_common_formats():
    s = pd.Series([
        "12/05/2024", "2024-05-13", "May 14, 2024",
        "15-05-2024", "2024.05.16", "05/17/2024",
        None,
    ])
    out = parse_mixed_dates(s)
    parsed = out.dropna()
    assert len(parsed) == 6
    # All should parse to 2024 May
    assert all(parsed.dt.year == 2024)
    assert all(parsed.dt.month == 5)


def test_normalize_string_series_titlecases():
    s = pd.Series(["  alice johnson  ", "BOB SMITH", None])
    out = normalize_string_series(s)
    assert out.iloc[0] == "Alice Johnson"
    assert out.iloc[1] == "Bob Smith"
    assert pd.isna(out.iloc[2])


# ---- pipeline stages ----

@pytest.fixture
def raw_df():
    return pd.DataFrame({
        "  Order ID ": [1, 2, 2, 3, 4],
        "order_date": ["12/05/2024", "N/A", "N/A", "2024-05-13", "2024-05-14"],
        "customer_name": ["  Alice ", "bob", "bob", None, " CARL "],
        "quantity": [2, 5, 5, -1, 1],
        "unit_price": ['"1,299.99"', "?", "?", "24.99", "2499.00"],
        "discount": ["0.10", "", "", "0.00", "0.05"],
        "country": ["usa", "USA", "USA", "france", "France"],
        "category": ["Electronics", "Furniture", "Furniture",
                     "electronics", "FURNITURE"],
        "payment_method": ["Credit", "debit", "debit", "PAYPAL", "credit"],
    })


def test_stage_rename_columns(raw_df):
    out = stage_rename_columns(raw_df)
    assert all(c == c.lower().strip() for c in out.columns)


def test_stage_deduplicate_removes_duplicates(raw_df):
    # rename first so the pipeline can find business key
    df = stage_rename_columns(raw_df)
    out = stage_deduplicate(df)
    # original has 2 rows of (order_id=2) which are full duplicates
    assert len(out) == 4
    assert out["order_id"].is_unique


def test_stage_handle_missing_tokens(raw_df):
    out = stage_handle_missing_tokens(raw_df)
    # '?' in unit_price became NaN
    assert pd.isna(out["unit_price"].iloc[1])


def test_end_to_end_smoke():
    """Quick run with a tiny DataFrame to ensure pipeline doesn't crash."""
    df = pd.DataFrame({
        "order_id": [1, 1, 2],
        "order_date": ["2024-01-01", "2024-01-01", "n/a"],
        "customer_name": ["Alice", "Alice", "Bob"],
        "city": ["NY", "NY", "SF"],
        "country": ["USA", "USA", "USA"],
        "product": ["Laptop", "Laptop", "Mouse"],
        "category": ["Electronics", "Electronics", "Electronics"],
        "quantity": [1, 1, 2],
        "unit_price": ["1,000.00", "1,000.00", "24.99"],
        "discount": ["0.1", "0.1", "0"],
        "sales_rep_email": ["a@b.com", "a@b.com", "a@b.com"],
        "customer_email": ["c@d.com", "c@d.com", "e@f.com"],
        "payment_method": ["credit", "credit", "debit"],
        "notes": ["", "", ""],
    })
    df = stage_rename_columns(df)
    df = stage_handle_missing_tokens(df)
    df = stage_clean_strings(df)
    df = stage_parse_dates(df)
    df = stage_cast_types(df)
    # Now dedup
    df = stage_deduplicate(df)
    # Duplicate of order_id=1 should be gone
    assert len(df) == 2

