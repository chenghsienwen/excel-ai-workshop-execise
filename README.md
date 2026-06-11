# Excel AI Workshop — Exercise Repo

This repository is a hands-on exercise for practising **AI harness engineering** with Claude Code.  
The goal is to build, extend, and test a real data pipeline — guided by AI — so participants learn how to:

- prompt an AI coding assistant to scaffold modules and tests
- iterate on requirements using plan docs as source-of-truth
- verify AI-generated code against typed fixtures and pytest suites
- chain multiple apps together into a reproducible analytics pipeline

---

## What's inside

The repo contains three independent apps that form an end-to-end pipeline:

```
app/
├── bm_report/          ← Step 1 · Excel → CSV transformer
├── bm_analytics/       ← Step 2 · CSV → KPI reports (layers 1 & 2)
└── bm_report_viewer/   ← Step 3 · Streamlit dashboard (planned)
```

### `bm_report` — Excel transformer

Reads raw `.xlsx` business-status files and produces a single analytics-ready
`raw_report.csv`.  Each workbook covers one product (`CDE` or `PJ`) and one
year; the pipeline parses a multi-block sheet layout and melts 12 month columns
into rows.

### `bm_analytics` — KPI analytics

Reads `raw_report.csv` and produces two report layers:

| Layer | Output file | What it contains |
|-------|-------------|------------------|
| 1 | `layer1_report.csv` | Period aggregations — total, H1/H2, Q1–Q4, YTD |
| 2 | `layer2_report.csv` | Derived metrics — YTD gap, budget hit rate, YoY ratios, breakeven month |

### `bm_report_viewer` — Streamlit dashboard _(planned)_

Interactive dashboard (Streamlit + Plotly) that visualises all report layers.
Design doc: [`app/bm_report_viewer/docs/plan.md`](app/bm_report_viewer/docs/plan.md).

---

## Prerequisites

- Python 3.10+
- `pip` / `venv`

Each app has its own virtual environment and `requirements.txt`.

---

## Running the pipeline

### Step 1 — bm_report

```bash
cd app/bm_report
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Place .xlsx files in raw_data/ then run:
python main.py

# Optional flags
python main.py --raw-data-dir /path/to/xlsx --output-dir /path/to/out
python main.py --verbose          # per-stage timing to stderr
```

Expected output:

```
Done: 4 files processed, 15120 rows written in 1.98 s
```

Output: `app/bm_report/output/raw_report.csv`

---

### Step 2 — bm_analytics

```bash
cd app/bm_analytics
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Copy output from step 1
cp ../bm_report/output/raw_report.csv input/

python main.py

# Optional flags
python main.py --input-file /path/to/raw_report.csv --output-dir /path/to/out
python main.py --verbose
```

Expected output:

```
Done: 15120 rows in → layer1: 1224 rows, layer2: 1224 rows  (0.07 s)
```

Outputs: `app/bm_analytics/output/layer1_report.csv`, `layer2_report.csv`

---

## Running tests

Each app has its own pytest suite.

### bm_report tests

```bash
cd app/bm_report
source .venv/bin/activate
pip install pytest
python -m pytest tests/ -v
```

### bm_analytics tests

```bash
cd app/bm_analytics
source .venv/bin/activate
pip install pytest
python -m pytest tests/ -v
```

31 tests covering loader validation, period arithmetic invariants (H1+H2=total,
Q1+Q2+Q3+Q4=total), YTD boundary cases, YTD gap, budget hit rate, YoY ratios,
and breakeven month logic.

---

## App-level READMEs

Each app has its own detailed README:

- [`app/bm_report/README.md`](app/bm_report/README.md) — output schema, module reference, Excel layout, extension guide
- [`app/bm_analytics/README.md`](app/bm_analytics/README.md) — output schemas, metric definitions, module reference, extension guide

---

## Workshop exercises

Typical AI harness tasks this repo is designed for:

1. **Scaffold a new module** — ask the AI to add a new metric to `layer2.py` with tests
2. **Extend the loader** — support a new Excel block layout via `config.py`
3. **Fix a failing test** — introduce a bug and use AI to diagnose and fix it
4. **Add a new layer** — implement `layer3` (segmentation or time-series) following the pattern in `layer1.py` / `layer2.py`
5. **Build the viewer** — implement `bm_report_viewer` from the plan doc using AI-assisted scaffolding
