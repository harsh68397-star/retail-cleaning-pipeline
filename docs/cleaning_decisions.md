# Cleaning Decisions Log

This document explains *why* each cleaning step was chosen in
`src/pipeline.py`. Every step is a tradeoff — this log records those
tradeoffs so future contributors (and interviewers) understand them.

## 1. Rename columns (`stage_rename_columns`)
- **What:** snake_case, strip whitespace, drop special chars.
- **Why:** Mixed-case + spaced column names are the #1 source of
  `KeyError`s in analytics code. Standardising at the boundary is
  cheap insurance.
- **Tradeoff:** Loses original column casing. If business glossary
  references uppercase names, we'd need a renaming map.

## 2. Normalize missing tokens (`stage_handle_missing_tokens`)
- **What:** Map `["", "na", "n/a", "null", "none", "?", "-", "nan"]`
  to real NaN, case-insensitively.
- **Why:** Pandas treats `"N/A"` as a *string*, not a missing value.
  Five different NaN representations means `isna().sum()` is wrong.
- **Tradeoff:** A real customer value like the literal string `"?"`
  would be lost. Extremely unlikely in real retail data.

## 3. Clean strings (`stage_clean_strings`)
- **What:** Trim whitespace, collapse runs of spaces, title-case for
  names/cities, upper-case for countries, lower-case for category &
  payment_method.
- **Why:** `"  new york "` and `"new  york"` and `"NEW YORK"` are the
  same city — but `groupby` would treat them as three.
- **Tradeoff:** Title casing fails for names like `McDonald`,
  `LeBlanc`, or `O'Connor`. For analytics we usually accept this
  approximation; for CRM-grade cleaning we'd use a names library.

## 4. Parse dates (`stage_parse_dates`)
- **What:** Try a list of common formats in order, fall back to
  dateutil with `dayfirst=True`.
- **Why:** CSV exports emit dates in whatever format the source
  app uses — MM/DD vs DD/MM is the classic bug. Falling back to
  dateutil catches anything we didn't anticipate.
- **Tradeoff:** Dateutil's `dayfirst` heuristic is sometimes wrong
  (e.g. `01/02/2024` is ambiguous). In production, we'd inspect the
  source's locale and pick the right primary format up front.

## 5. Cast types (`stage_cast_types`)
- **What:** Numeric columns (`quantity`, `unit_price`, `discount`,
  `order_id`) coerced to nullable Int64 / Float64.
- **Why:** Without casting, joins and aggregations silently fail —
  `df.groupby('quantity').sum()` works on strings only for the
  wrong reasons.
- **Tradeoff:** Nullable types (`Int64`, `Float64`) differ from
  NumPy types in some APIs. We accept the typing cost for safety.

## 6. Outliers (`stage_handle_outliers`)
- **What:** IQR-based detection on `unit_price`. Rows outside
  `[Q1 - 3*IQR, Q3 + 3*IQR]` flagged via boolean column, **not** removed.
- **Why:** A fat-finger entry like `$12,999,999` should be reviewed
  by a human, not silently deleted. Flagging keeps the row in place
  for the analyst to decide.
- **Tradeoff:** Using 3×IQR is conservative — we catch only the most
  extreme outliers. For more sensitivity use Z-score or domain rules
  (e.g. unit prices > $10K need manager approval).

## 7. Deduplicate (`stage_deduplicate`)
- **What:** Two-pass: full-row dedup, then `order_id` business-key
  dedup.
- **Why:** A duplicate by `order_id` may differ in fields like
  `customer_name` (e.g. trailing space), so full-row dedup alone
  misses them. The business-key step catches semantic duplicates.
- **Tradeoff:** Keep-first is arbitrary. In production we'd want
  audit logs: which `created_at` won?

## 8. Validate (`stage_validate`)
- **What:** Pandera schema enforces ranges, allowed values, and
  regex on `customer_name` / emails.
- **Why:** Catches schema drift and unit-test-survived bugs (e.g.
  `discount > 1.0`) before they poison downstream aggregates.
- **Tradeoff:** Schema is a contract — change requires updating
  stakeholders. Validation is **soft-fail by default** so the
  pipeline still produces output; set `STRICT=1` to crash.

## 9. Output (`stage_summarize`)
- **What:** Markdown table comparing raw vs cleaned metrics, plus
  two PNG charts of missing-value patterns.
- **Why:** A pipeline nobody can read fails the most important test
  — the stakeholder review. Numbers + pictures are the universal
  language.

---

## What I would do next (production-grade)

1. **Add `pytest` coverage for every stage** (done — see `tests/`).
2. **Move `parse_mixed_dates` to a config-driven format list** so
   different source systems can plug in without code changes.
3. **Replace title-case for `customer_name`** with a name-cleaning
   library (e.g. `probablepeople`) or LLM-based normalization.
4. **Add a `great_expectations` checkpoint** alongside pandera for
   richer data-docs output.
5. **Log every cleaning decision to a Delta/Lake table** so the same
   raw row never gets cleaned twice with different results.
6. **Add a `pyproject.toml`** and publish to an internal package
   index once the pipeline stabilizes.

