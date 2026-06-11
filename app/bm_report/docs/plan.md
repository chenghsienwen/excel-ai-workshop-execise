# BM Report Transformer — Implementation Plan

## Overview

Transform raw Excel business-status files (`raw_data/`) into a consolidated,
analytics-ready CSV (`output/`) using Python with Google-style conventions.

---

## Directory Layout (target)

```
app/bm_report/
├── docs/
│   └── plan.md               ← this file
├── raw_data/
│   ├── CDE biz status_2024_v1.xlsx
│   ├── CDE biz status_2025_v1.xlsx
│   ├── PJ biz status_2024_v1.xlsx
│   └── PJ biz status_2025_v2.xlsx
├── output/
│   └── raw_report.csv        ← final output
├── src/
│   ├── __init__.py
│   ├── config.py             ← paths, column maps, constants
│   ├── loader.py             ← Excel → raw DataFrame
│   ├── transformer.py        ← normalize, reshape, validate
│   └── writer.py             ← write CSV output
├── main.py                   ← CLI entry point
├── requirements.txt
└── .venv/                    ← virtual environment (git-ignored)
```

---

## Output Schema

The output CSV (`output/raw_report.csv`) must contain exactly these columns
in this order:

| Column             | Type   | Example values              |
|--------------------|--------|-----------------------------|
| `product`          | str    | `CDE`, `PJ`                 |
| `year`             | int    | `2024`, `2025`              |
| `region`           | str    | `AZ`, `BD+`, `ID`, …        |
| `rev_op_type`      | str    | `Gross`, `Net`, `Op`        |
| `sales_budget_type`| str    | `Actual`, `Budget`, `Forecast` |
| `month`            | str    | `Jan`–`Dec`                 |
| `amount`           | int    | raw integer (no rounding)   |

---

## Implementation Steps

### Step 1 — Environment Setup

1. Create and activate a virtual environment:
   ```bash
   cd app/bm_report
   python3 -m venv .venv
   source .venv/bin/activate
   ```

2. Write `requirements.txt`:
   ```
   pandas>=2.2.0
   openpyxl>=3.1.0
   ```

3. Install:
   ```bash
   pip install -r requirements.txt
   ```

### Step 2 — `src/config.py`

Centralise all magic values so no other module hard-codes paths or strings.

- `RAW_DATA_DIR`: `pathlib.Path` pointing to `raw_data/`
- `OUTPUT_DIR`: `pathlib.Path` pointing to `output/`
- `OUTPUT_FILE`: `output/raw_report.csv`
- `PRODUCT_MAP`: filename prefix → product label (`{"CDE": "CDE", "PJ": "PJ"}`)
- `MONTH_COLS`: ordered list `["Jan", "Feb", …, "Dec"]`
- `OUTPUT_COLUMNS`: the 7 final column names in order

### Step 3 — `src/loader.py`

Responsibility: read one Excel file, return a raw `pandas.DataFrame`.

```
load_excel(path: pathlib.Path) -> pd.DataFrame
```

- Uses `openpyxl` engine.
- Reads every sheet; merges with a `sheet_name` column if multiple sheets carry
  different `rev_op_type` or `sales_budget_type` values.
- Infers `product` from the filename prefix and `year` from the filename stem
  (e.g. `_2024_`).
- Raises `ValueError` for unrecognised filename patterns.

### Step 4 — `src/transformer.py`

Responsibility: take one raw DataFrame from the loader and return a normalised
long-format DataFrame matching the output schema.

```
transform(df: pd.DataFrame, product: str, year: int) -> pd.DataFrame
```

Key operations:
1. **Identify dimension columns** — detect `region`, `rev_op_type`,
   `sales_budget_type` by position or header name.
2. **Melt month columns** — `pd.melt` the 12 month columns (`Jan`–`Dec`) into
   `month` / `amount` rows.
3. **Normalise** — strip whitespace, title-case where needed, cast `amount` to
   `int` (fill NaN with 0).
4. **Validate** — assert `rev_op_type` ∈ `{Gross, Net, Op}` and
   `sales_budget_type` ∈ `{Actual, Budget, Forecast}`; log a warning and drop
   unknown rows rather than crashing.
5. **Return** only the 7 output columns in canonical order.

### Step 5 — `src/writer.py`

Responsibility: write the final merged DataFrame to CSV.

```
write_report(df: pd.DataFrame, path: pathlib.Path) -> None
```

- Creates parent directories if missing.
- Writes UTF-8 CSV with no index.
- Logs row count and output path.

### Step 6 — `main.py` (CLI entry point)

```
python main.py [--raw-data-dir PATH] [--output-dir PATH] [--verbose]
```

Orchestration:
1. Parse CLI flags (use `argparse`).
2. Glob all `*.xlsx` in `raw_data/`.
3. `loader.load_excel` → `transformer.transform` for each file.
4. `pd.concat` all results, sort by `[product, year, region, rev_op_type,
   sales_budget_type, month]`.
5. `writer.write_report` to `output/raw_report.csv`.
6. Exit 0 on success, 1 on any error (print traceback with `--verbose`).

---

## Google Python Style Conventions Applied

| Concern              | Rule                                                          |
|----------------------|---------------------------------------------------------------|
| Indentation          | 4 spaces, no tabs                                            |
| Line length          | ≤ 80 characters                                              |
| Imports              | stdlib → third-party → local, one per line, no wildcards     |
| Naming               | `snake_case` for functions/variables, `PascalCase` for classes, `ALL_CAPS` for module-level constants |
| Docstrings           | One-line summary + blank line + args/returns (Google format) |
| Type hints           | All public functions annotated                               |
| Logging              | `logging` module only — no bare `print` in library code      |
| Error handling       | Raise specific exceptions; document them in docstrings       |
| Testing              | `unittest` in `tests/` mirroring `src/`; run with `python -m pytest` |

---

## Execution

```bash
cd app/bm_report
source .venv/bin/activate
python main.py
# output written to output/raw_report.csv
```

---

## Execution Time Consumption

Every stage is timed using `time.perf_counter()` and reported via `logging`.
No third-party library is required.

### Instrumentation Pattern

Wrap each logical stage in `main.py` with a context manager defined in
`src/config.py`:

```python
import contextlib
import logging
import time

@contextlib.contextmanager
def _timed(label: str):
    """Logs elapsed wall-clock time for a named stage."""
    start = time.perf_counter()
    yield
    elapsed = time.perf_counter() - start
    logging.info("[timing] %-30s %.3f s", label, elapsed)
```

### Timed Stages in `main.py`

| Stage label               | What is measured                                      |
|---------------------------|-------------------------------------------------------|
| `load:<filename>`         | `loader.load_excel()` per file                        |
| `transform:<filename>`    | `transformer.transform()` per file                    |
| `concat_and_sort`         | `pd.concat` + sort of all DataFrames                  |
| `write_report`            | `writer.write_report()` CSV write                     |
| `total`                   | Full pipeline wall-clock from first glob to last write|

### Sample Log Output (`--verbose`)

```
INFO [timing] load:CDE biz status_2024_v1.xlsx  0.412 s
INFO [timing] transform:CDE biz status_2024_v1.xlsx  0.083 s
INFO [timing] load:CDE biz status_2025_v1.xlsx  0.387 s
INFO [timing] transform:CDE biz status_2025_v1.xlsx  0.079 s
INFO [timing] load:PJ biz status_2024_v1.xlsx   0.401 s
INFO [timing] transform:PJ biz status_2024_v1.xlsx   0.076 s
INFO [timing] load:PJ biz status_2025_v2.xlsx   0.395 s
INFO [timing] transform:PJ biz status_2025_v2.xlsx   0.074 s
INFO [timing] concat_and_sort                  0.031 s
INFO [timing] write_report                     0.044 s
INFO [timing] total                            1.982 s
INFO Wrote 15120 rows → output/raw_report.csv
```

### Summary Line

After all stage timings, `main.py` prints a single human-readable summary to
`stdout` (not the log) so it is visible regardless of log level:

```
Done: 4 files processed, 15120 rows written in 1.98 s
```

---

## Future Extensions (out of scope for v1)

- Incremental mode: skip files whose mtime is older than output mtime.
- Excel sheet auto-discovery via header signature matching.
- HTML or Excel output format flag.
- Unit tests in `tests/` covering loader, transformer, and writer individually.
