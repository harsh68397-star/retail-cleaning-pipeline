
# Retail Cleaning Pipeline

> A reproducible, end-to-end data cleaning pipeline built with Python & pandas.
> Turned 26 rows of dirty retail CSV into 24 clean, schema-validated rows in one command.

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![pandas](https://img.shields.io/badge/pandas-2.x-green)
![pandera](https://img.shields.io/badge/pandera-validated-purple)
![tests](https://img.shields.io/badge/tests-9%20passed-success)

## The Problem

Real-world CSVs look nothing like textbook examples. The sample dataset in
`data/raw/retail_sales_raw.csv` is a realistic mess:

| Issue | Example |
|---|---|
| Mixed date formats | `12/05/2024`, `2024-05-13`, `May 14, 2024`, `15-05-2024`, `2024.05.16` |
| 7 representations of "missing" | `N/A`, `?`, `-`, `NULL`, `na`, `""`, `nan` |
| Whitespace + casing | `  Alice Johnson  `, `new york`, `USA`, `usa` |
| Numeric-as-text | `"1,299.99"` (with quotes and comma) |
| Duplicates (full-row) | Same order_id twice, slightly different whitespace |
| Fat-finger price | One row at $12,999,999 |
| Encoding edge cases | `München`, `Naïve` |

## What the pipeline does

```
+---------------------+       +------------------------+       +------------------+
|  data/raw/*.csv     | ----> |  src/pipeline.py       | ----> | data/processed/  |
|  (messy CSV)        |       |  (9 cleaning stages)   |       | (clean CSV)      |
+---------------------+       +------------------------+       +------------------+
                                          |
                                          v
                                  outputs/before_after_summary.md
                                  outputs/missing_before.png
                                  outputs/missing_after.png
```

### The 9 stages

1. **Load** the CSV.
2. **Rename** columns → `snake_case`, stripped of whitespace and special chars.
3. **Normalize missing tokens** → all variants of `N/A`, `?`, `-`, `null`, `nan` become real `NaN`.
4. **Clean strings** → trim, collapse whitespace, normalize case (`Title`, `UPPER`, `lower`).
5. **Parse dates** → recognize 13 common formats; fall back to `dateutil`.
6. **Cast types** → numeric coercion that strips `$`, quotes, commas.
7. **Detect outliers** → IQR-based flag, not drop (humans decide).
8. **Deduplicate** → full-row first, then by business key (`order_id`).
9. **Validate** → a `pandera` schema enforces ranges, email regex, allowed values.

## Quick start

```bash
pip install -r requirements.txt
python -m src.pipeline
pytest -q tests
python notebooks/01_exploration.py
```

The pipeline writes three artifacts to `outputs/`:
- `before_after_summary.md` — row counts and per-column missing counts.

## Tech stack

| Layer | Tool | Why |
|---|---|---|
| DataFrame | **pandas** | Industry standard for analyst-size data |
| Validation | **pandera** | Expressive schema-as-code with column-level rules |
| Visualization | **matplotlib** | Lightweight missing-value matrices |
| Testing | **pytest** | Standard Python testing framework |
| Versioning | **git + GitHub** | (Run `git init && gh repo create ...` to publish) |

## Project structure

```
retail-cleaning-pipeline/
|-- README.md                    <- you are here
|-- LICENSE
|-- requirements.txt
|-- .gitignore
|
|-- data/
|   |-- raw/retail_sales_raw.csv      <- the messy input
|   +-- processed/retail_sales_clean.csv <- the cleaned output (gitignored)
|
|-- src/
|   |-- utils.py                  <- reusable cleaning helpers
|   |-- validators.py             <- pandera schema
|   |-- profiling.py              <- quick per-column profile
|   +-- pipeline.py               <- 9-stage orchestrator (run me)
|
|-- tests/
|   +-- test_pipeline.py          <- 9 unit tests covering utils + stages
|
|-- notebooks/
|   +-- 01_exploration.py         <- what an analyst runs first
|
|-- outputs/
|   |-- before_after_summary.md   <- markdown summary of changes
|   |-- missing_before.png        <- missing-value matrix (before)
|   +-- missing_after.png         <- missing-value matrix (after)
|
+-- docs/
    |-- cleaning_decisions.md     <- the *why* behind every stage
    |-- data_dictionary.md        <- column-level documentation
    +-- interview_walkthrough.md  <- 3-minute talk-track for interviews
```

## What I learned

Building this taught me three things:

1. **Order matters.** Cleaning missing tokens *before* parsing dates
   prevents the date parser from seeing `?` and crashing.
2. **Flag, don't drop.** Outliers are business decisions. A flagged row
   goes back to the stakeholder with a note - a dropped row vanishes
   silently and breaks trust.
3. **Validate at the boundary.** Pandera catches drift in the schema
   itself (a future analyst adding `quantity: str` would have failed
   here, not 3 reports down).

## How to talk through this in an interview

Open [`docs/interview_walkthrough.md`](docs/interview_walkthrough.md) for
a 3-minute script and common follow-up questions.

## License

MIT - see [`LICENSE`](LICENSE).
- `missing_before.png` and `missing_after.png` — visual proofs.

## Before / After

| Metric | Raw | Cleaned | Change |
|---|---|---|---|
| Rows | 26 | 24 | -2 |
| Columns | 14 | 15 | +1 (`price_outlier_flag`) |
| Missing-cell % | 7.14% | 6.39% | -0.75pp |
| Duplicate rows | 2 | 0 | -2 |
| Outlier rows (flagged) | - | 1 | - |

