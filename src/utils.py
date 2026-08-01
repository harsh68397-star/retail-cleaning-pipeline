"""Reusable helper functions for the retail cleaning pipeline."""
import re
import pandas as pd
import numpy as np

NULL_LIKE = {"", "na", "n/a", "null", "none", "?", "-", "nan"}


def clean_column_names(df):
    """snake_case headers, strip whitespace, drop illegal chars."""
    df = df.copy()
    new_cols = (
        df.columns.astype(str)
        .str.strip()
        .str.lower()
        .str.replace(r"[^a-z0-9_]+", "_", regex=True)
        .str.replace(r"_+", "_", regex=True)
        .str.strip("_")
    )
    df.columns = new_cols
    return df


def normalize_string_series(s):
    """Trim + collapse spaces + title-case. Keeps NaN as NaN."""
    return (
        s.astype("string")
         .str.strip()
         .str.replace(r"\s+", " ", regex=True)
         .str.title()
    )


def normalize_country(s):
    return s.astype("string").str.strip().str.upper()


def normalize_category(s):
    return s.astype("string").str.strip().str.lower()


def normalize_missing(df, null_like=NULL_LIKE):
    """Map missing-like tokens (case-insensitive) to real NaN."""
    df = df.copy()
    obj_cols = df.select_dtypes(include=["object", "string"]).columns
    lower_nulls = {n.lower() for n in null_like}
    for c in obj_cols:
        df[c] = (
            df[c].astype("string").str.strip().str.lower()
              .where(lambda x: ~x.isin(lower_nulls), other=np.nan)
        )
    return df


_NUMERIC_KEEP = re.compile(r"[0-9.\-]")


def to_numeric_clean(s):
    """Strip currency/commas/quotes from numeric strings."""
    if s.dtype.kind in "biufc":
        return s

    def _strip(x):
        if pd.isna(x):
            return np.nan
        cleaned = "".join(_NUMERIC_KEEP.findall(str(x)))
        if cleaned in ("", "-", ".", "-."):
            return np.nan
        try:
            return float(cleaned)
        except ValueError:
            return np.nan

    return s.map(_strip).astype("Float64")


def parse_mixed_dates(s):
    """Parse a Series with mixed date formats into datetime64[ns]."""
    out = pd.Series([pd.NaT] * len(s), index=s.index, dtype="datetime64[ns]")
    COMMON_FORMATS = [
        "%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d",
        "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y",
        "%m/%d/%Y", "%m-%d-%Y", "%m.%d.%Y",
        "%b %d, %Y", "%B %d, %Y", "%b %d %Y", "%B %d %Y",
    ]
    s_str = s.astype("string").str.strip()
    for fmt in COMMON_FORMATS:
        mask = out.isna() & s_str.notna()
        if not mask.any():
            break
        try:
            parsed = pd.to_datetime(s_str[mask], format=fmt, errors="coerce")
        except (ValueError, TypeError):
            parsed = pd.Series([pd.NaT] * int(mask.sum()), index=s_str[mask].index)
        out.loc[mask] = parsed
    leftover = out.isna() & s_str.notna()
    if leftover.any():
        try:
            out.loc[leftover] = pd.to_datetime(
                s_str[leftover], errors="coerce", dayfirst=True
            )
        except Exception:
            pass
    return out


def quality_report(df, label="data"):
    """Return a small text summary of data quality."""
    lines = [f"=== Quality report: {label} ===",
             f"Rows: {len(df):,}",
             f"Columns: {df.shape[1]}", ""]
    lines.append(f"{'column':<22}{'dtype':<14}{'missing':<10}{'unique':<10}")
    lines.append("-" * 56)
    for c in df.columns:
        n_missing = int(df[c].isna().sum())
        n_unique = int(df[c].nunique(dropna=True))
        lines.append(f"{c:<22}{str(df[c].dtype):<14}{n_missing:<10}{n_unique:<10}")
    return "\n".join(lines)


if __name__ == "__main__":
    sample = pd.DataFrame({" Name ": [" alice ", None, "BOB"],
                           "Price": ["1,299.99", "?", "24.99"]})
    sample = clean_column_names(sample)
    sample = normalize_missing(sample)
    sample["price_clean"] = to_numeric_clean(sample["price"])
    print(sample)
    print()
    print(quality_report(sample, "self-test"))

