# Architecture Walkthrough — How to Talk Through This Project

Use this as a 3-minute script when an interviewer asks
*"Walk me through a project on your resume."*

---

## 30 sec — Hook

> "I built a reproducible data-cleaning pipeline for a simulated
> retail sales dataset. The raw data had the kind of mess you'd
> see in real business CSVs — five different date formats, missing
> values written seven different ways, two duplicate orders, an
> outlier that was actually a fat-fingered price entry, and a
> customer email with a non-ASCII character. The pipeline takes
> the raw CSV all the way to a validated, schema-checked output
> in one command."

## 90 sec — Walk through the pipeline

Open `src/pipeline.py`. The pipeline is nine stages, each its own
function:

1. **Load** the CSV (`stage_load`).
2. **Rename** columns to `snake_case` — the simplest way to avoid
   `KeyError`s later.
3. **Normalize missing tokens** — pandas treats strings, so
   `"N/A"`, `"?"`, `"-"` etc. all need to become real `NaN`s
   before `isna().sum()` is honest.
4. **Clean strings** — trim whitespace, title-case names and
   cities, upper-case countries, lower-case categories.
5. **Parse dates** — try a list of common formats, fall back to
   `dateutil` with `dayfirst=True`. Two of our 26 rows had
   unparseable dates; we kept them as `NaT` and let the schema
   validate `nullable=True`.
6. **Cast types** — `quantity` and `discount` come in as text
   with quotes and commas. Use a regex stripper, not a naive
   `pd.to_numeric`, because of those quote characters.
7. **Detect outliers** — IQR on `unit_price` flagged one row
   with `$12,999,999`. We **flagged** it, didn't drop it — that's
   a human decision, not a pipeline decision.
8. **Deduplicate** — first full-row duplicates (2 rows), then
   business-key duplicates by `order_id`.
9. **Validate** — a pandera schema enforces column ranges, email
   regexes, and allowed values for `payment_method`.

## 30 sec — Show the result

> "We went from 26 raw rows to 24 clean rows — the two were
> duplicates. The pipeline writes a `before_after_summary.md`
> with the row counts, per-column missing counts, and two PNG
> charts of the missing-value matrix. So even a non-technical
> stakeholder can see what changed."

## 30 sec — What you'd improve next

> "Three things. First, customer names get title-cased, which
> breaks `McDonald` and `O'Connor`; I'd swap in the
> `probablepeople` library. Second, I'd parameterize the date
> format list so different source systems can plug in. Third, I'd
> integrate `great_expectations` for richer data-doc output."
> This shows humility and a roadmap — interviewers love it.

---

## Common follow-up questions and good answers

**Q: Why flag instead of drop outliers?**
> "Because the pipeline runs unattended and a $12.99M row could
> be a fat finger OR a real bulk discount for a corporate buyer.
> Humans make that call. Flagging preserves the audit trail."

**Q: Why both row-level and business-key dedup?**
> "A near-duplicate by order_id might differ in whitespace or
> casing, so full-row dedup misses it. Two passes catch both
> kinds."

**Q: How would you scale this to 50M rows?**
> "Switch from pandas to Polars or PySpark. The stage functions
> translate one-to-one — `clean_column_names` becomes
> `df.columns = ...` in either framework. For 50M rows I'd also
> move validation out of pandera and into Great Expectations with
> a sampling strategy."

**Q: Why pandera instead of just dtype checks?**
> "Pandera lets you express business constraints — 'discount must
> be 0 to 1', 'country must be one of these'. Plain dtype checks
> only catch type confusion, not semantic bugs."

