<div align="center">

# Retail Cleaning Pipeline

**Reproducible 9-stage Python data-cleaning pipeline for messy retail CSV data.**

*Turned a 26-row messy CSV into a 24-row schema-validated clean output - in one command.*

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python&logoColor=white)
![pandas](https://img.shields.io/badge/pandas-2.x-150458?style=for-the-badge&logo=pandas&logoColor=white)
![pandera](https://img.shields.io/badge/pandera-validated-purple?style=for-the-badge)
![Tests](https://img.shields.io/badge/tests-9%20passed-success?style=for-the-badge&logo=pytest&logoColor=white)
![License](https://img.shields.io/badge/license-MIT-green?style=for-the-badge)

[Report Bug](https://github.com/harsh68397-star/retail-cleaning-pipeline/issues) - [Request Feature](https://github.com/harsh68397-star/retail-cleaning-pipeline/issues)

</div>

---

## TL;DR

> Takes a realistic, messy retail CSV - 7 different missing-value tokens, 13 date formats, fat-finger prices, embedded duplicates, encoding edge cases - and produces a **schema-validated clean CSV** plus a **before/after metrics report**. One command, fully reproducible, fully tested.

```bash
git clone https://github.com/harsh68397-star/retail-cleaning-pipeline
cd retail-cleaning-pipeline
pip install -r requirements.txt
python -m src.pipeline
```

---

## The Problem

Real-world CSVs look nothing like textbook examples. The sample dataset in `data/raw/retail_sales_raw.csv` is a realistic mess:

| Issue | Example |
|---|---|
| Mixed date formats | `12/05/2024`, `2024-05-13`, `May 14, 2024`, `15-05-2024`, `2024.05.16` |
| 7 representations of "missing" | `N/A`, `?`, `-`, `NULL`, `na`, `""`, `nan` |
| Whitespace + casing chaos | `  Alice Johnson  `, `new york`, `USA`, `usa` |
| Numeric-as-text | `"1,299.99"` (quotes + comma) |
| Duplicates | Same `order_id` twice with slight whitespace drift |
| Fat-finger price | One row at **$12,999,999** (4 extra zeros) |
| Encoding edge cases | `München`, `Naïve` |

---

## Before / After

| Metric | Raw | Cleaned | Change |
|---|---:|---:|---:|
| Rows | 26 | 24 | **-2** |
| Columns | 14 | 15 | +1 (`price_outlier_flag`) |
| Missing-cell % | 7.14% | 6.39% | -0.75pp |
| Duplicate rows | 2 | 0 | **-2** |
| Outlier rows (flagged, not dropped) | - | 1 | - |
| Tests passing | - | **9 / 9** | - |

**Sample row transformation:**

| Field | Raw | Clean |
|---|---|---|
| `Order Date` | `15/03/2024` | `2024-03-15` |
| `Unit Price` | `$12.99M` | `12.99` |
| `Quantity` | `"-3"` | `-3` |
| `Customer Email` | ` JOHN@GMAIL.com  ` | `john@gmail.com` |
| `Discount` | `N/A` | *(null)* |

---

## Architecture

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

---

## The 9 Stages

| # | Stage | What it does |
|---|---|---|
| 1 | **Load** | Read CSV with `pandas`, profile it. |
| 2 | **Rename** | `Order ID` → `order_id`, strip whitespace + special chars. |
| 3 | **Normalize missing** | All variants of `N/A`, `?`, `-`, `null`, `nan` → real `NaN`. |
| 4 | **Clean strings** | Trim, collapse whitespace, normalize case (`Title`, `UPPER`, `lower`). |
| 5 | **Parse dates** | Recognize 13 common formats; fall back to `dateutil` parser. |
| 6 | **Cast types** | Numeric coercion that strips `$`, quotes, commas. |
| 7 | **Detect outliers** | IQR-based **flag** (not drop) - humans decide. |
| 8 | **Deduplicate** | Full-row first, then by business key (`order_id`). |
| 9 | **Validate** | `pandera` schema enforces ranges, email regex, allowed values. |

---

## Quick Start

**1. Clone & install**

```bash
git clone https://github.com/harsh68397-star/retail-cleaning-pipeline
cd retail-cleaning-pipeline
pip install -r requirements.txt
```

**2. Run the pipeline**

```bash
python -m src.pipeline
```

Produces:

- `data/processed/retail_sales_clean.csv` - the cleaned dataset
- `outputs/before_after_summary.md` - row + column metrics
- `outputs/missing_before.png` / `missing_after.png` - visual proof

**3. Run the tests**

```bash
pytest -q
```

Expected: `9 passed in ~0.5s`.

**4. Explore the data**

```bash
python notebooks/01_exploration.py
```

---

## Tests

9 unit tests covering utils + stages - all pass.

```
tests/test_pipeline.py::test_clean_column_names PASSED
tests/test_pipeline.py::test_normalize_missing_handles_null_like_tokens PASSED
tests/test_pipeline.py::test_to_numeric_clean_strips_currency_and_commas PASSED
tests/test_pipeline.py::test_parse_mixed_dates_handles_multiple_formats PASSED
tests/test_pipeline.py::test_outlier_flag_uses_iqr PASSED
tests/test_pipeline.py::test_normalize_country_and_category PASSED
tests/test_pipeline.py::test_stage_handle_missing_tokens PASSED
tests/test_pipeline.py::test_quality_report_shape_change PASSED
tests/test_pipeline.py::test_end_to_end_smoke PASSED

9 passed in 0.52s
```

---

## Tech Stack

| Layer | Tool | Why |
|---|---|---|
| DataFrame | **pandas** | Industry standard for analyst-size data |
| Validation | **pandera** | Expressive schema-as-code with column-level rules |
| Visualization | **matplotlib** | Lightweight missing-value matrices |
| Testing | **pytest** | Standard Python testing framework |
| Versioning | **git + GitHub** | Reproducible, branchable, reviewable |

---

## Project Structure

```
retail-cleaning-pipeline/
|-- README.md                    <- you are here
|-- LICENSE
|-- requirements.txt
|-- pyproject.toml
|-- pytest.ini
|-- .gitignore
|
|-- data/
|   |-- raw/retail_sales_raw.csv          <- the messy input
|   +-- processed/retail_sales_clean.csv   <- the cleaned output (gitignored)
|
|-- src/
|   |-- utils.py                  <- reusable cleaning helpers
|   |-- validators.py             <- pandera schema
|   |-- profiling.py              <- quick per-column profile
|   +-- pipeline.py               <- 9-stage orchestrator
|
|-- tests/
|   +-- test_pipeline.py          <- 9 unit tests
|
|-- notebooks/
|   +-- 01_exploration.py         <- analyst-first exploration script
|
|-- outputs/                       <- generated by the pipeline
|   |-- before_after_summary.md
|   |-- missing_before.png
|   +-- missing_after.png
|
+-- docs/
    |-- cleaning_decisions.md     <- the *why* behind every stage
    +-- data_dictionary.md        <- column-level documentation
```

---

## Design Decisions

Three principles guided this build:

1. **Order matters.** Cleaning missing tokens *before* parsing dates prevents the date parser from seeing `?` and crashing.
2. **Flag, don’t drop.** Outliers are business decisions. A flagged row goes back to the stakeholder with a note - a dropped row vanishes silently and breaks trust.
3. **Validate at the boundary.** Pandera catches drift in the schema itself (a future analyst changing `quantity` to `str` would fail here, not 3 reports down).

---

## Roadmap

- [ ] GitHub Actions CI (`pytest` on every push)
- [ ] Great Expectations checkpoint alongside pandera
- [ ] CLI flags for custom missing tokens
- [ ] PyPI package: `pip install retail-cleaning-pipeline`
- [ ] Sample notebook comparing this pipeline to Great Expectations
- [ ] Add a `make_dataset.py` script for regenerating the raw CSV

---

## Documentation

- [**Cleaning decisions**](docs/cleaning_decisions.md) - the *why* behind every stage.
- [**Data dictionary**](docs/data_dictionary.md) - column-level schema documentation.

---

## Author

**Harsh Raj Sharma** - [@harsh68397-star](https://github.com/harsh68397-star)

Built as a portfolio piece demonstrating production-quality data engineering with Python.

---

## License

MIT - see [`LICENSE`](LICENSE).

---

<div align="center">

If this helped you, consider giving it a ⭐ on GitHub.

</div>
