# BM Analytics

Reads `input/raw_report.csv` (produced by `app/bm_report`) and generates two
analytics layers:

- **Layer 1** — period aggregations (total, H1/H2, Q1–Q4, dynamic YTD) per cohort
- **Layer 2** — derived cross-type metrics: YTD gap, budget hit rate, YoY ratios,
  and breakeven month

---

## Directory layout

```
app/bm_analytics/
├── docs/
│   └── plan.md               ← design notes and metric definitions
├── input/
│   └── raw_report.csv        ← source produced by app/bm_report
├── output/
│   ├── layer1_report.csv     ← period aggregations
│   └── layer2_report.csv     ← derived metrics
├── src/
│   ├── config.py             ← paths, constants, timed() utility
│   ├── loader.py             ← load and validate input CSV
│   ├── periods.py            ← month→period mapping, dynamic YTD
│   ├── layer1.py             ← period aggregation builder
│   ├── layer2.py             ← derived metrics builder
│   └── trend.py              ← trend functions (stub)
├── tests/
│   ├── fixtures/
│   │   └── raw_report_fixture.csv
│   ├── test_loader.py
│   ├── test_periods.py
│   ├── test_layer1.py
│   └── test_layer2.py
├── main.py                   ← CLI entry point
├── requirements.txt
└── .venv/                    ← virtual environment (git-ignored)
```

---

## Output schemas

### Layer 1 — `output/layer1_report.csv`

One row per cohort `(region, product, year, rev_op_type, sales_budget_type)`.

| Column              | Type  | Description                                    |
|---------------------|-------|------------------------------------------------|
| `region`            | str   | e.g. `AZ`, `ID`, `TTL VSI`                    |
| `product`           | str   | `CDE` or `PJ`                                  |
| `year`              | str   | `2024`, `2025`                                 |
| `rev_op_type`       | str   | `Gross`, `Net`, `Op`                           |
| `sales_budget_type` | str   | `Actual`, `Budget`, `Forecast`                 |
| `total`             | int   | Sum of all 12 months                           |
| `h1`                | int   | Sum Jan–Jun                                    |
| `h2`                | int   | Sum Jul–Dec                                    |
| `q1`                | int   | Sum Jan–Mar                                    |
| `q2`                | int   | Sum Apr–Jun                                    |
| `q3`                | int   | Sum Jul–Sep                                    |
| `q4`                | int   | Sum Oct–Dec                                    |
| `ytd`               | int   | Sum Jan → current month (dynamic at runtime)   |

### Layer 2 — `output/layer2_report.csv`

Same cohort key as Layer 1, with derived cross-type metrics.

| Column              | Type   | Description                                                         |
|---------------------|--------|---------------------------------------------------------------------|
| `ytd_gap`           | int    | `ytd(this_type) − ytd(Budget)`                                      |
| `budget_hit_rate`   | int    | `ytd(this_type) / ytd(Budget) × 100` (%)                           |
| `yoy_total`         | float  | `total(current_year) / total(prev_year)`; `0` if no prior year     |
| `yoy_h1` / `yoy_h2`| float  | Same ratio for H1 / H2                                              |
| `yoy_q1`–`yoy_q4`  | float  | Same ratio per quarter                                              |
| `breakeven_month`   | int    | First month (1–12) where `cumsum(Actual) ≥ cumsum(Budget)`; blank for non-Actual rows or when Actual never crosses Budget |

---

## Local run

### 1. Set up the environment

```bash
cd app/bm_analytics
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Place the input file

Copy or symlink `raw_report.csv` from `app/bm_report/output/` into `input/`:

```bash
cp ../bm_report/output/raw_report.csv input/
```

### 3. Run

```bash
# default paths (input/raw_report.csv → output/)
python main.py

# custom paths
python main.py --input-file /path/to/raw_report.csv --output-dir /path/to/out

# verbose: print per-stage timing
python main.py --verbose
```

Expected output:

```
Done: 15120 rows in → layer1: 1224 rows, layer2: 1224 rows  (0.07 s)
```

---

## Verbose / timing output

Pass `--verbose` to enable `DEBUG`-level logging with per-stage wall-clock times:

```
INFO Loaded 15120 rows from input/raw_report.csv
INFO [timing] load                           0.009 s
INFO [timing] layer1                         0.017 s
INFO Wrote 1224 rows → output/layer1_report.csv
INFO [timing] write_layer1                   0.006 s
INFO [timing] layer2                         0.033 s
INFO Wrote 1224 rows → output/layer2_report.csv
INFO [timing] write_layer2                   0.006 s
```

---

## Tests

```bash
source .venv/bin/activate
pip install pytest
python -m pytest tests/ -v
```

31 tests covering loader validation, period arithmetic invariants (H1+H2=total,
Q1+Q2+Q3+Q4=total), YTD boundary cases, YTD gap, budget hit rate, YoY ratios,
and breakeven month logic.

---

## Module reference

| Module            | Public API                                           | Responsibility                                              |
|-------------------|------------------------------------------------------|-------------------------------------------------------------|
| `src/config.py`   | constants, `timed(label)`                            | Paths, column lists, timing context manager                 |
| `src/loader.py`   | `load(path) → DataFrame`                             | Read CSV, validate schema, cast dtypes                      |
| `src/periods.py`  | `PERIOD_MONTHS`, `ytd_months(today)`, `aggregate_periods(df, today)` | Month→period mapping and pivot aggregation |
| `src/layer1.py`   | `build(df, today) → DataFrame`                       | Produce Layer 1 period aggregation report                   |
| `src/layer2.py`   | `build(layer1, raw) → DataFrame`                     | Produce Layer 2 derived metrics report                      |
| `src/trend.py`    | `ytd_trend`, `yoy_delta_by_month`, `period_momentum` | Trend functions (stub — deferred)                           |
| `main.py`         | CLI (`--input-file`, `--output-dir`, `--verbose`)    | Orchestrate load → layer1 → layer2 → write                  |

---

## Extending the pipeline

- **New period** — add an entry to `PERIOD_MONTHS` in `src/periods.py`; `aggregate_periods` picks it up automatically.
- **New derived metric** — add a helper in `src/layer2.py` and call it from `build()`.
- **Trend functions** — implement the stubs in `src/trend.py`; signatures are already defined.
- **New input source** — update `src/loader.py` to accept different formats while returning the same 7-column DataFrame.
