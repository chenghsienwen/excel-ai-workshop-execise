# BM Report Transformer

Transforms raw Excel business-status files (`raw_data/`) into a consolidated,
analytics-ready CSV (`output/raw_report.csv`).

Each source file covers one product (`CDE` or `PJ`) and one year. The
pipeline reads every worksheet, parses the multi-block layout (Actual /
Forecast / Budget × Gross / Net / Op), melts the 12 month columns into rows,
scales amounts, and writes a single sorted CSV.

---

## Directory layout

```
app/bm_report/
├── docs/
│   └── plan.md               ← design notes
├── raw_data/                 ← input .xlsx files (not committed)
├── output/
│   └── raw_report.csv        ← generated output
├── src/
│   ├── config.py             ← paths, column maps, constants
│   ├── loader.py             ← Excel → raw DataFrame
│   ├── transformer.py        ← normalise, validate, reshape
│   └── writer.py             ← write CSV
├── main.py                   ← CLI entry point
├── requirements.txt
└── .venv/                    ← virtual environment (git-ignored)
```

---

## Output schema

`output/raw_report.csv` contains exactly these columns:

| Column              | Type | Example values                   |
|---------------------|------|----------------------------------|
| `product`           | str  | `CDE`, `PJ`                      |
| `year`              | int  | `2024`, `2025`                   |
| `region`            | str  | `AZ`, `BD+`, `ID`, …             |
| `rev_op_type`       | str  | `Gross`, `Net`, `Op`             |
| `sales_budget_type` | str  | `Actual`, `Budget`, `Forecast`   |
| `month`             | str  | `Jan` – `Dec`                    |
| `amount`            | int  | Excel value × 10 000 (no rounding) |

Rows are sorted by `product → year → region → rev_op_type → sales_budget_type → month`.

---

## Local run

### 1. Set up the environment

```bash
cd app/bm_report
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Add source files

Place `.xlsx` files in `raw_data/`. Filenames must match the pattern:

```
<PRODUCT> biz status_<YEAR>_*.xlsx
# e.g.
CDE biz status_2025_v1.xlsx
PJ  biz status_2024_v1.xlsx
```

### 3. Run

```bash
# default paths (raw_data/ → output/raw_report.csv)
python main.py

# custom paths
python main.py --raw-data-dir /path/to/xlsx --output-dir /path/to/out

# verbose: print per-stage timing to stderr
python main.py --verbose
```

Expected output:

```
Done: 4 files processed, 15120 rows written in 1.98 s
```

---

## Verbose / timing output

Pass `--verbose` to enable `DEBUG`-level logging including per-stage wall-clock times:

```
INFO [timing] load:CDE biz status_2024_v1.xlsx       0.412 s
INFO [timing] transform:CDE biz status_2024_v1.xlsx  0.083 s
INFO [timing] load:PJ biz status_2025_v2.xlsx        0.395 s
INFO [timing] transform:PJ biz status_2025_v2.xlsx   0.074 s
INFO [timing] concat_and_sort                        0.031 s
INFO [timing] write_report                           0.044 s
```

---

## Module reference

| Module               | Public API                                         | Responsibility                                              |
|----------------------|----------------------------------------------------|-------------------------------------------------------------|
| `src/config.py`      | constants, `timed(label)`                          | Paths, column maps, scale factor, timing context manager    |
| `src/loader.py`      | `load_excel(path) → DataFrame`                     | Read one `.xlsx`, parse multi-block layout, return raw rows |
| `src/transformer.py` | `transform(df, product, year) → DataFrame`         | Strip, validate, scale `amount`, return canonical columns   |
| `src/writer.py`      | `write_report(df, path) → None`                    | Write UTF-8 CSV, create parent dirs if missing              |
| `main.py`            | CLI (`--raw-data-dir`, `--output-dir`, `--verbose`) | Orchestrate loader → transformer → writer pipeline         |

---

## Excel file structure

Each workbook may contain multiple sheets. Within each sheet the cells are
laid out in three side-by-side blocks:

| Block     | Region col | Month cols  |
|-----------|-----------|-------------|
| Actual    | col B (1) | cols C–N (2–13) |
| Forecast  | col Q (16) | cols R–AC (17–28) |
| Budget    | col AF (31) | cols AG–AR (32–43) |

Header rows in column B identify the `rev_op_type`:

| Cell value        | Mapped to |
|-------------------|-----------|
| `Gross Sales ($K)` | `Gross`  |
| `Net Sales ($K)`   | `Net`    |
| `OP Sales ($K)`    | `Op`     |

The loader carries the current `rev_op_type` forward across rows using
`itertools.accumulate`, so no mutable state is required.

---

## Extending the pipeline

- **New product prefix** — add the prefix to `PRODUCT_PREFIXES` in `src/config.py` and update `_FILENAME_RE` in `src/loader.py`.
- **New rev_op_type** — add a mapping to `REV_OP_TYPE_HEADERS` in `src/config.py`.
- **Different block layout** — update `SECTION_CONFIG` in `src/config.py` (each entry is `(sales_budget_type, region_col_index, month_start_col_index)`).
- **Different amount scale** — change `AMOUNT_SCALE` in `src/config.py`.
