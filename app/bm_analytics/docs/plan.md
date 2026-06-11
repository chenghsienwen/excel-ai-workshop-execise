# BM Analytics — Implementation Plan

## Overview

Read `input/raw_report.csv` (produced by `app/bm_report`) and generate two
analytics layers:

- **Layer 1** — period aggregations per cohort
- **Layer 2** — derived cross-type metrics (gap, hit rate, YoY, breakeven)

A third module (`trend.py`) provides functions for time-series trend views;
full spec deferred until layers 1 & 2 are validated.

---

## Directory Layout (target)

```
app/bm_analytics/
├── docs/
│   └── plan.md               ← this file
├── input/
│   └── raw_report.csv        ← source produced by bm_report
├── output/
│   ├── layer1_report.csv     ← period aggregations
│   └── layer2_report.csv     ← derived metrics
├── src/
│   ├── __init__.py
│   ├── config.py             ← paths, constants, timed() utility
│   ├── loader.py             ← load & validate input CSV
│   ├── periods.py            ← month→period mapping, dynamic YTD
│   ├── layer1.py             ← aggregated view generator
│   ├── layer2.py             ← derived metrics generator
│   └── trend.py              ← trend functions (stub)
├── main.py                   ← CLI entry point
├── requirements.txt
└── .venv/                    ← virtual environment (git-ignored)
```

---

## Environment Setup

```bash
cd app/bm_analytics
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

`requirements.txt`:

```
pandas>=2.2.0
```

---

## Input Schema

`input/raw_report.csv` — 15,120 rows, produced by `app/bm_report`.

| Column              | Type | Example values                   |
|---------------------|------|----------------------------------|
| `product`           | str  | `CDE`, `PJ`                      |
| `year`              | str  | `2024`, `2025`                   |
| `region`            | str  | `AZ`, `BD+`, `ID`, …             |
| `rev_op_type`       | str  | `Gross`, `Net`, `Op`             |
| `sales_budget_type` | str  | `Actual`, `Budget`, `Forecast`   |
| `month`             | str  | `Jan`–`Dec`                      |
| `amount`            | int  | e.g. `81035550`                  |

---

## Layer 1 — Period Aggregation

**Output**: `output/layer1_report.csv`

**Cohort key**: `region, product, year, rev_op_type, sales_budget_type`

For each cohort, sum `amount` across months according to period windows:

| Column  | Months summed          |
|---------|------------------------|
| `total` | Jan – Dec              |
| `h1`    | Jan – Jun              |
| `h2`    | Jul – Dec              |
| `q1`    | Jan – Mar              |
| `q2`    | Apr – Jun              |
| `q3`    | Jul – Sep              |
| `q4`    | Oct – Dec              |
| `ytd`   | Jan → current month (dynamic at runtime via `datetime.date.today()`) |

**Output schema** (1,224 rows expected):

```
region, product, year, rev_op_type, sales_budget_type,
total, h1, h2, q1, q2, q3, q4, ytd
```

---

## Layer 2 — Derived Metrics

**Output**: `output/layer2_report.csv`

**Cohort key**: `region, product, year, rev_op_type, sales_budget_type`

Derived by joining Layer 1 output with itself across `sales_budget_type`.

| Column           | Definition |
|------------------|------------|
| `ytd_gap`        | `ytd(this_type) − ytd(Budget)` per `(region, product, year, rev_op_type)` |
| `budget_hit_rate`| `ytd(this_type) / ytd(Budget) × 100` (integer %) |
| `yoy_total`      | `total(current_year) / total(prev_year)` within same `(region, product, rev_op_type, sales_budget_type)`; `0` when no prior year |
| `yoy_h1`–`yoy_h2`| same ratio for H1 / H2 |
| `yoy_q1`–`yoy_q4`| same ratio per quarter |
| `breakeven_month`| First month index (1–12) where `cumsum(Actual) >= cumsum(Budget)` for `(region, product, year, rev_op_type)`; `null` if Actual never crosses Budget within the year |

> `breakeven_month` is populated only on rows where `sales_budget_type = Actual`;
> set to `null` for Budget and Forecast rows.

**Output schema** (816 rows expected):

```
region, product, year, rev_op_type, sales_budget_type,
ytd_gap, budget_hit_rate,
yoy_total, yoy_h1, yoy_h2, yoy_q1, yoy_q2, yoy_q3, yoy_q4,
breakeven_month
```

---

## Module Responsibilities

### `src/config.py`

Centralise all constants — no other module hard-codes paths or strings.

- `INPUT_FILE`: `pathlib.Path` to `input/raw_report.csv`
- `OUTPUT_DIR`: `pathlib.Path` to `output/`
- `MONTH_COLS`: ordered list `["Jan", "Feb", …, "Dec"]`
- `COHORT_KEY`: `["region", "product", "year", "rev_op_type", "sales_budget_type"]`
- `timed(label)`: `contextlib.contextmanager` that logs wall-clock time
  (same pattern as `bm_report/src/config.py`)

### `src/loader.py`

```python
def load(path: pathlib.Path) -> pd.DataFrame:
    """Load and validate raw_report.csv."""
```

- Reads CSV, asserts all expected columns are present.
- Casts `amount` to `int`, `year` to `str`.
- Raises `ValueError` on schema mismatch.

### `src/periods.py`

Pure functions — no I/O or side effects.

```python
PERIOD_MONTHS: dict[str, list[str]]   # period name → month list
def ytd_months(today: datetime.date) -> list[str]
def aggregate_periods(df: pd.DataFrame) -> pd.DataFrame
```

- `PERIOD_MONTHS` maps `total/h1/h2/q1/q2/q3/q4` to their month lists.
- `ytd_months` returns months Jan → `today.month` for dynamic YTD.
- `aggregate_periods` groups by cohort key and applies all period sums
  via `map` over `PERIOD_MONTHS` items — functional style, no explicit loops.

### `src/layer1.py`

```python
def build(df: pd.DataFrame) -> pd.DataFrame:
    """Return Layer 1 period aggregations."""
```

Calls `periods.aggregate_periods`; returns the Layer 1 schema.

### `src/layer2.py`

```python
def build(layer1: pd.DataFrame) -> pd.DataFrame:
    """Return Layer 2 derived metrics."""
```

Steps (all functional — map/merge/assign, no for-loops):

1. Self-join `layer1` on `(region, product, year, rev_op_type)` to align
   Budget rows alongside each type row → compute `ytd_gap`, `budget_hit_rate`.
2. Self-join on `(region, product, rev_op_type, sales_budget_type)` across
   years → compute `yoy_*` columns.
3. Compute `breakeven_month` via `itertools.accumulate` over
   sorted months for each `(region, product, year, rev_op_type)` Actual/Budget
   pair; set `null` for non-Actual rows.

### `src/trend.py`

Stub — exports typed function signatures only; bodies return empty DataFrames.
Full implementation deferred until layers 1 & 2 are validated.

```python
def ytd_trend(df: pd.DataFrame, cohort: dict) -> pd.DataFrame: ...
def yoy_delta_by_month(df: pd.DataFrame, cohort: dict) -> pd.DataFrame: ...
def period_momentum(df: pd.DataFrame, cohort: dict) -> pd.DataFrame: ...
```

### `main.py` — CLI entry point

```
python main.py [--input-dir PATH] [--output-dir PATH] [--verbose]
```

Orchestration:

1. Parse CLI flags (`argparse`).
2. `loader.load` → raw DataFrame.
3. `layer1.build` → Layer 1 DataFrame; write `output/layer1_report.csv`.
4. `layer2.build(layer1)` → Layer 2 DataFrame; write `output/layer2_report.csv`.
5. Print timing summary to stdout.
6. Exit 0 on success, 1 on any error.

---

## Google Python Style Conventions

| Concern       | Rule                                                                  |
|---------------|-----------------------------------------------------------------------|
| Indentation   | 4 spaces, no tabs                                                     |
| Line length   | ≤ 80 characters                                                       |
| Imports       | stdlib → third-party → local, one per line, no wildcards             |
| Naming        | `snake_case` functions/vars, `ALL_CAPS` module constants              |
| Docstrings    | One-line summary + blank line + Args/Returns (Google format)          |
| Type hints    | All public functions annotated                                        |
| Logging       | `logging` module only — no bare `print` in library code              |
| Style         | Functional — `map`, `filter`, `functools.reduce`, `itertools`; avoid explicit `for`-loops in transform logic |

---

## Timing

Every stage wrapped in `config.timed(label)` (same pattern as `bm_report`):

| Stage label    | What is measured                        |
|----------------|-----------------------------------------|
| `load`         | `loader.load()` CSV read + validation   |
| `layer1`       | `layer1.build()` aggregation            |
| `layer2`       | `layer2.build()` derived metrics        |
| `write_layer1` | CSV write for layer 1                   |
| `write_layer2` | CSV write for layer 2                   |
| `total`        | Full pipeline wall-clock                |

Summary line to stdout (regardless of log level):

```
Done: 15120 rows in → layer1: 1224 rows, layer2: 816 rows  (1.23 s)
```

---

## Execution

```bash
cd app/bm_analytics
source .venv/bin/activate
python main.py --verbose
```

---

## Unit Tests

### Structure

```
app/bm_analytics/
└── tests/
    ├── __init__.py
    ├── fixtures/
    │   └── raw_report_fixture.csv   ← minimal 3-region, 2-year sample
    ├── test_loader.py
    ├── test_periods.py
    ├── test_layer1.py
    └── test_layer2.py
```

Tests mirror `src/` one-to-one. Each file uses only `unittest` (stdlib) and
`pandas` — no additional test framework required. Run with:

```bash
cd app/bm_analytics
source .venv/bin/activate
python -m pytest tests/          # or: python -m unittest discover tests/
```

---

### Fixture

`tests/fixtures/raw_report_fixture.csv` — hand-authored minimal dataset:

- 2 regions (`AZ`, `CE`), 2 products (`CDE`, `PJ`), 2 years (`2024`, `2025`)
- All 3 `rev_op_type` values, all 3 `sales_budget_type` values
- All 12 months with deterministic integer amounts
- Enough rows that aggregation results can be verified by mental arithmetic

---

### `tests/test_loader.py`

| Test | Assertion |
|---|---|
| `test_happy_path` | Valid CSV loads without error; returns correct column set and row count |
| `test_missing_column` | Raises `ValueError` when a required column is absent |
| `test_amount_cast` | `amount` column dtype is `int64` after load |
| `test_year_cast` | `year` column dtype is `str` (not int) after load |

---

### `tests/test_periods.py`

| Test | Assertion |
|---|---|
| `test_period_months_complete` | Every month `Jan`–`Dec` appears in exactly one of `q1/q2/q3/q4`; `h1 = q1+q2`, `h2 = q3+q4`, `total = h1+h2` |
| `test_ytd_months_june` | `ytd_months(date(2025, 6, 15))` returns `["Jan","Feb","Mar","Apr","May","Jun"]` |
| `test_ytd_months_january` | `ytd_months(date(2025, 1, 1))` returns `["Jan"]` |
| `test_aggregate_periods_totals` | For a single-cohort fixture, `total == h1 + h2` and `h1 == q1 + q2` |
| `test_aggregate_periods_ytd` | `ytd` matches manual sum of months up to the injected `today` date |

---

### `tests/test_layer1.py`

| Test | Assertion |
|---|---|
| `test_output_columns` | Output contains exactly the Layer 1 schema columns in order |
| `test_row_count` | One row per unique `(region, product, year, rev_op_type, sales_budget_type)` cohort |
| `test_total_equals_sum` | `total` == sum of all 12 monthly `amount` values for a known cohort |
| `test_h1_h2_partition` | `h1 + h2 == total` for every row |
| `test_quarter_partition` | `q1 + q2 + q3 + q4 == total` for every row |
| `test_ytd_subset_of_total` | `ytd <= total` for all rows when `today` is within the year |

---

### `tests/test_layer2.py`

| Test | Assertion |
|---|---|
| `test_output_columns` | Output contains exactly the Layer 2 schema columns in order |
| `test_ytd_gap_actual_minus_budget` | For a known cohort, `ytd_gap == ytd(Actual) - ytd(Budget)` |
| `test_budget_hit_rate_100_when_equal` | When Actual YTD == Budget YTD, `budget_hit_rate == 100` |
| `test_yoy_zero_when_no_prior_year` | `yoy_total == 0` for all 2024 rows (no 2023 data) |
| `test_yoy_ratio` | For a 2025 cohort, `yoy_total == layer1_total_2025 / layer1_total_2024` |
| `test_breakeven_month_actual_only` | `breakeven_month` is non-null only on rows where `sales_budget_type == "Actual"` |
| `test_breakeven_correct_month` | For a fixture where cumulative Actual crosses Budget in March, `breakeven_month == 3` |
| `test_breakeven_null_when_never_crosses` | `breakeven_month` is null when Actual never reaches Budget within the year |

---

## Future Extensions (out of scope for v1)

- Full `trend.py` implementation with charting-ready output.
- Incremental mode: skip regeneration when input mtime < output mtime.
- Layer 3: cross-product / cross-region ranking views.

---

## Data Analysis Concept Mapping

Assessment of standard BI/analytics frameworks against `raw_report.csv`.

### Fully applicable — can generate from current data

| Concept | How it maps |
|---|---|
| **Segmentation** | Slice revenue by region, product (CDE/PJ), rev_op_type (Gross/Net/Op), or any combination. Layer 1 already provides per-cohort aggregations; a ranking/cross-tab view adds the segmentation layer. |
| **Time-Series Analysis** | Month-by-month Actual vs Budget vs Forecast trends, MoM growth rates, seasonal patterns (which quarters are strongest), anomaly months where Actual deviates sharply from Budget. |

### Partially applicable — requires adaptation

| Concept | Constraint | Adapted form |
|---|---|---|
| **Retention Rate** | Designed for user/subscription data, not revenue. | **Budget achievement rate over time** — does a region consistently hit its monthly budget across the year? Produces a retention-curve-shaped output per cohort. |
| **LTV (Customer Lifetime Value)** | No customer-level or acquisition cost data. | **Cumulative revenue per cohort** — total Gross revenue per (region × product) over the two years as a proxy for segment value. |

### Not applicable — data does not support

| Concept | Reason |
|---|---|
| **Funnel Analysis** | No sequential step data; our data is periodic revenue, not a user journey. |
| **CAC / Attribution Modeling** | No marketing spend or channel data. |
| **Churn Rate** | No user-level subscription tracking. |

---

## Layer 3 — Planned Modules (from concept mapping)

Two new report modules to build on top of `raw_report.csv`:

### `layer3_segmentation.py`

Cross-tab ranking report: which regions/products are performing best or worst.

**Output**: `output/layer3_segmentation.csv`

| Column | Description |
|---|---|
| `product`, `year`, `rev_op_type`, `sales_budget_type` | Segment dimensions |
| `region` | Ranked entity |
| `total`, `ytd` | Absolute revenue |
| `ytd_gap` | Actual vs Budget gap |
| `rank_total` | Region rank by total revenue within segment |
| `rank_ytd_gap` | Region rank by YTD gap (worst to best) |
| `share_pct` | Region's share of segment total (%) |

### `layer3_timeseries.py`

Month-by-month trend series per cohort.

**Output**: `output/layer3_timeseries.csv`

| Column | Description |
|---|---|
| `region`, `product`, `year`, `rev_op_type`, `sales_budget_type` | Cohort key |
| `month` | Month abbreviation (Jan–Dec) |
| `amount` | Raw monthly amount |
| `mom_growth` | Month-over-month growth rate vs prior month (ratio; null for Jan) |
| `vs_budget` | `amount(Actual) - amount(Budget)` for same month |
| `seasonal_index` | Month's share of annual total (amount / total); indicates peak/trough months |
