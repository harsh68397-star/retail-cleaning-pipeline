"""End-to-end retail data cleaning pipeline.

Run with:
    python src/pipeline.py

Reads:  data/raw/retail_sales_raw.csv
Writes: data/processed/retail_sales_clean.csv
        outputs/before_after_summary.md
        outputs/missing_before.png
        outputs/missing_after.png
"""
import os
import sys
import logging
from datetime import datetime

import numpy as np
import pandas as pd

from src.utils import (
    clean_column_names,
    normalize_missing,
    normalize_string_series,
    normalize_country,
    normalize_category,
    to_numeric_clean,
    parse_mixed_dates,
    quality_report,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
log = logging.getLogger("pipeline")


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_PATH = os.path.join(ROOT, "data", "raw", "retail_sales_raw.csv")
CLEAN_PATH = os.path.join(ROOT, "data", "processed", "retail_sales_clean.csv")
REPORT_PATH = os.path.join(ROOT, "outputs", "before_after_summary.md")
MISSING_BEFORE_PNG = os.path.join(ROOT, "outputs", "missing_before.png")
MISSING_AFTER_PNG = os.path.join(ROOT, "outputs", "missing_after.png")


def stage_load(path=RAW_PATH):
    log.info("Loading raw data from %s", path)
    df = pd.read_csv(path, encoding="utf-8")
    log.info("Raw shape: %s", df.shape)
    return df


def stage_profile(df, label="raw"):
    log.info("--- profile (%s) ---\n%s", label, quality_report(df, label))


def stage_rename_columns(df):
    log.info("Renaming columns to snake_case")
    return clean_column_names(df)


def stage_handle_missing_tokens(df):
    log.info("Normalizing missing-value tokens (N/A, ?, -, null, ...)")
    return normalize_missing(df)


def stage_clean_strings(df):
    log.info("Cleaning string columns (trim, case, whitespace)")
    df = df.copy()
    if "customer_name" in df:
        df["customer_name"] = normalize_string_series(df["customer_name"])
    if "city" in df:
        df["city"] = normalize_string_series(df["city"])
    if "country" in df:
        df["country"] = normalize_country(df["country"])
    if "category" in df:
        df["category"] = normalize_category(df["category"])
    if "payment_method" in df:
        df["payment_method"] = (
            df["payment_method"].astype("string").str.strip().str.lower()
        )
    if "product" in df:
        df["product"] = df["product"].astype("string").str.strip()
    return df


def stage_parse_dates(df):
    log.info("Parsing mixed-format order_date column")
    df = df.copy()
    if "order_date" in df:
        df["order_date"] = parse_mixed_dates(df["order_date"])
    return df


def stage_cast_types(df):
    log.info("Casting numeric columns (quantity, unit_price, discount, order_id)")
    df = df.copy()
    if "order_id" in df:
        df["order_id"] = pd.to_numeric(df["order_id"], errors="coerce").astype("Int64")
    if "quantity" in df:
        df["quantity"] = (
            to_numeric_clean(df["quantity"]).astype("Float64").astype("Int64")
        )
    if "unit_price" in df:
        df["unit_price"] = to_numeric_clean(df["unit_price"]).astype("float64")
    if "discount" in df:
        df["discount"] = to_numeric_clean(df["discount"]).fillna(0.0).astype("float64")
    return df


def stage_handle_outliers(df):
    """Flag, don't drop - return outlier mask + tagged dataframe."""
    log.info("Detecting outliers via IQR on unit_price")
    df = df.copy()
    if "unit_price" not in df or df["unit_price"].dropna().empty:
        return df
    q1 = df["unit_price"].quantile(0.25)
    q3 = df["unit_price"].quantile(0.75)
    iqr = q3 - q1
    upper = q3 + 3 * iqr
    lower = q1 - 3 * iqr
    df["price_outlier_flag"] = (
        (df["unit_price"] > upper) | (df["unit_price"] < lower)
    ).fillna(False).astype(bool)
    n_out = int(df["price_outlier_flag"].sum())
    log.info("Flagged %s outliers in unit_price (outside [%s, %s])",
             n_out, round(lower, 2), round(upper, 2))
    return df


def stage_deduplicate(df):
    """Drop full-row duplicates; then drop duplicates by business key."""
    log.info("Removing duplicates")
    before = len(df)
    df = df.drop_duplicates()
    after_full = len(df)
    log.info("Row-level dedup: %s -> %s rows (%s removed)",
             before, after_full, before - after_full)
    if "order_id" in df:
        before_key = len(df)
        df = df.drop_duplicates(subset=["order_id"], keep="first")
        after_key = len(df)
        log.info("order_id dedup:  %s -> %s rows (%s removed)",
                 before_key, after_key, before_key - after_key)
    return df.reset_index(drop=True)


def stage_validate(df):
    """Validate via pandera. Soft-fail by default (does not crash pipeline)."""
    log.info("Validating against pandera schema (lazy)")
    try:
        from src.validators import validate
        validate(df)
        log.info("Validation OK")
    except Exception as e:
        log.warning("Validation reported issues - pipeline continues")
        log.warning("Detail: %s", str(e)[:500])
        if os.environ.get("STRICT") == "1":
            raise


def _write_missing_chart(df, label, path):
    """Save a missing-values matrix chart via matplotlib."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(8, max(3, df.shape[1] * 0.35)))
        ms = df.isna().astype(int).T
        ax.imshow(ms.values, aspect="auto", cmap="gray_r", vmin=0, vmax=1)
        ax.set_yticks(range(len(ms.index)))
        ax.set_yticklabels(ms.index)
        ax.set_xticks(range(len(ms.columns)))
        ax.set_xticklabels([str(c) for c in ms.columns],
                           rotation=90, fontsize=7)
        ax.set_title(f"Missing values - {label}")
        plt.tight_layout()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        plt.savefig(path, dpi=120)
        plt.close(fig)
        return True
    except Exception as e:
        log.warning("Could not save missing chart %s: %s", path, e)
        return False


def stage_summarize(raw, clean):
    """Write a markdown before/after summary."""
    log.info("Writing before/after summary")
    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)

    def pct_missing(d):
        total_cells = d.size
        if total_cells == 0:
            return 0.0
        return round(d.isna().sum().sum() / total_cells * 100, 2)

    md = []
    md.append("# Before / After Summary\n")
    md.append(f"_Generated: {datetime.now().isoformat(timespec='seconds')}_\n")
    md.append("| Metric | Raw | Cleaned | Change |")
    md.append("|---|---|---|---|")
    md.append(f"| Rows | {len(raw)} | {len(clean)} | {len(clean)-len(raw):+d} |")
    md.append(f"| Columns | {raw.shape[1]} | {clean.shape[1]} | "
              f"{clean.shape[1]-raw.shape[1]:+d} |")
    md.append(f"| Missing-cell % | {pct_missing(raw)}% | {pct_missing(clean)}% | "
              f"{round(pct_missing(clean)-pct_missing(raw), 2):+.2f}pp |")
    md.append(f"| Duplicate rows | {int(raw.duplicated().sum())} | "
              f"{int(clean.duplicated().sum())} | - |")
    md.append("")
    md.append("## Per-column missing counts\n")
    md.append("| Column | Raw missing | Cleaned missing |")
    md.append("|---|---|---|")
    common = [c for c in raw.columns if c in clean.columns]
    for c in common:
        md.append(f"| {c} | {int(raw[c].isna().sum())} | "
                  f"{int(clean[c].isna().sum())} |")
    text = "\n".join(md)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(text)
    return text


def run():
    raw = stage_load()
    stage_profile(raw, "raw")
    _write_missing_chart(raw, "before cleaning", MISSING_BEFORE_PNG)

    df = raw
    df = stage_rename_columns(df)
    df = stage_handle_missing_tokens(df)
    df = stage_clean_strings(df)
    df = stage_parse_dates(df)
    df = stage_cast_types(df)
    df = stage_handle_outliers(df)
    df = stage_deduplicate(df)

    stage_validate(df)
    stage_profile(df, "clean")
    _write_missing_chart(df, "after cleaning", MISSING_AFTER_PNG)

    summary = stage_summarize(raw, df)
    os.makedirs(os.path.dirname(CLEAN_PATH), exist_ok=True)
    df.to_csv(CLEAN_PATH, index=False, encoding="utf-8")
    log.info("Wrote cleaned CSV to %s", CLEAN_PATH)
    log.info("Wrote summary to %s", REPORT_PATH)

    print()
    print(summary)
    return df


if __name__ == "__main__":
    sys.exit(0 if run() is not None else 1)

