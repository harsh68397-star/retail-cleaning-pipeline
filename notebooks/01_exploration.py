"""01_exploration.py - Initial data quality assessment.

Run with: python notebooks/01_exploration.py

This mirrors what you'd do inside a Jupyter notebook - load the raw
data, run quick quality checks, and write a few notes about what
needs cleaning. The actual cleaning happens in src/pipeline.py.
"""
import os, sys

# make src/ importable
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import pandas as pd

from src.profiling import quick_profile

RAW = os.path.join(ROOT, "data", "raw", "retail_sales_raw.csv")

print("=" * 70)
print("STEP 1: Load the raw data")
print("=" * 70)
df = pd.read_csv(RAW, encoding="utf-8")
print(f"Shape: {df.shape}")
print()
print("First 5 rows:")
print(df.head())
print()
print("Column dtypes:")
print(df.dtypes)
print()

print("=" * 70)
print("STEP 2: Quick profile (per-column missing % and unique counts)")
print("=" * 70)
print(quick_profile(df).to_string(index=False))
print()

print("=" * 70)
print("STEP 3: Distinct sample values per column (find the mess)")
print("=" * 70)
for c in df.columns:
    vals = df[c].dropna().unique()
    sample = list(vals[:8])
    print(f"\n{c}  ({len(vals)} unique values):")
    for v in sample:
        print(f"    {v!r}")
print()

print("=" * 70)
print("STEP 4: Cleaning notes (what to fix)")
print("=" * 70)
notes = [
    "1.  Column names: spaces and mixed case -> snake_case via clean_column_names",
    "2.  order_date: 5+ different formats -> parse_mixed_dates",
    "3.  Missing values: 'N/A', '?', '-', 'NULL', ''  -> normalize_missing",
    "4.  Customer name: leading/trailing spaces, mixed case -> normalize_string_series",
    "5.  City / Country: case + whitespace -> normalize_country / normalize_string_series",
    "6.  Category: mixed case -> normalize_category (lowercase canonical)",
    "7.  Payment method: 'Credit'/'credit'/'CREDIT' -> lowercase",
    "8.  unit_price / quantity: numeric stored as text, commas, quotes -> to_numeric_clean",
    "9.  discount: missing == 0 -> fillna(0)",
    "10. Outliers: IQR-based detection on unit_price -> flag, don't drop",
    "11. Duplicates: full-row dedup, then business-key (order_id) dedup",
    "12. Validation: pandera schema enforces column ranges / categories",
    "13. Visualize missingness before/after -> outputs/missing_before.png",
]
for n in notes:
    print(n)

