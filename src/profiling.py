"""Quick data profiling helpers (separate from the main pipeline)."""
import pandas as pd


def quick_profile(df: pd.DataFrame) -> pd.DataFrame:
    """Return a DataFrame summary: dtype, missing%, n_unique, sample."""
    rows = []
    for c in df.columns:
        rows.append({
            "column": c,
            "dtype": str(df[c].dtype),
            "missing": int(df[c].isna().sum()),
            "missing_pct": round(df[c].isna().mean() * 100, 2),
            "unique": int(df[c].nunique(dropna=True)),
            "example": df[c].dropna().iloc[0] if df[c].dropna().size else None,
        })
    return pd.DataFrame(rows).sort_values("missing_pct", ascending=False)


if __name__ == "__main__":
    import os, sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    raw_path = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                            "data", "raw", "retail_sales_raw.csv")
    df = pd.read_csv(raw_path, encoding="utf-8")
    print(quick_profile(df).to_string(index=False))

