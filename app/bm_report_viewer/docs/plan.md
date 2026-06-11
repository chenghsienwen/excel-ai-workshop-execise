# BM Report Viewer — Plan

## Goal

Create a Streamlit dashboard (`app/bm_report_viewer`) that reads analytics outputs
from `app/bm_analytics` and visualises all four report layers interactively.
Runs locally on Ubuntu and macOS with no external services.

## Stack

| Library | Role |
|---|---|
| **Streamlit** | Web app framework — browser UI, multipage, sidebar |
| **Plotly** | Interactive charts (zoom, hover, filter) |
| **Pandas** | Data loading, filtering, pivoting |

## Project Layout

```
app/bm_report_viewer/
├── .venv/                      # virtual environment (not committed)
├── input/                      # synced from bm_analytics (not committed)
│   ├── raw_report.csv
│   ├── layer1_report.csv
│   ├── layer2_report.csv
│   ├── layer3_segmentation.csv
│   └── layer3_timeseries.csv
├── src/
│   ├── __init__.py
│   ├── loader.py               # load & cache all 5 CSVs with @st.cache_data
│   └── charts/
│       ├── __init__.py
│       ├── layer1.py           # period bar chart: Actual vs Budget by H/Q
│       ├── layer2.py           # YTD gap, budget hit rate heatmap, YoY, breakeven
│       ├── layer3_seg.py       # ranked bar + treemap (share_pct)
│       └── layer3_ts.py        # MoM growth line, seasonal index heatmap
├── pages/
│   ├── 1_Period_Summary.py     # layer1
│   ├── 2_KPI_Metrics.py        # layer2
│   ├── 3_Segmentation.py       # layer3_segmentation
│   └── 4_Timeseries.py         # layer3_timeseries
├── docs/
│   └── plan.md                 # this file
├── app.py                      # home page + global sidebar filters
├── sync_input.py               # copies files from ../bm_analytics/
├── requirements.txt
└── README.md
```

## Input Sync

`sync_input.py` — one-command script that copies source files into `input/`:

| Source | Destination |
|---|---|
| `../bm_analytics/input/raw_report.csv` | `input/raw_report.csv` |
| `../bm_analytics/output/layer1_report.csv` | `input/layer1_report.csv` |
| `../bm_analytics/output/layer2_report.csv` | `input/layer2_report.csv` |
| `../bm_analytics/output/layer3_segmentation.csv` | `input/layer3_segmentation.csv` |
| `../bm_analytics/output/layer3_timeseries.csv` | `input/layer3_timeseries.csv` |

- Prints which files were updated (skips unchanged by mtime comparison).
- Also exposed as a **Sync** button in the Streamlit sidebar.

## Sidebar Filters (Global, All Pages)

- **Year** — multi-select
- **Region** — multi-select
- **Product** — multi-select
- **rev_op_type** — dropdown
- **sales_budget_type** — dropdown

Filters are applied in `loader.py` and shared across all pages via `st.session_state`.

## Pages & Charts

### 1 — Period Summary (`layer1_report.csv`)
- Grouped bar chart: Actual vs Budget for total / H1 / H2 / Q1 / Q2 / Q3 / Q4
- Pivot table (region × period) as a styled DataFrame

### 2 — KPI Metrics (`layer2_report.csv`)
- YTD gap bar chart (positive = over budget, negative = under)
- Budget hit rate heatmap (region × product)
- YoY comparison bar (yoy_total, yoy_h1, yoy_h2)
- Breakeven month scatter (month index per cohort)

### 3 — Segmentation (`layer3_segmentation.csv`)
- Ranked bar by region — sort by rank_total or rank_ytd_gap
- Treemap: share_pct by region / product

### 4 — Timeseries (`layer3_timeseries.csv`)
- MoM growth line chart (month × amount, colour by region)
- vs_budget area chart
- Seasonal index heatmap (month × product)

## Run Commands

```bash
# Setup (first time)
cd app/bm_report_viewer
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Pull latest analytics data
python sync_input.py

# Launch dashboard
streamlit run app.py
```

## Input Data Schemas (reference)

| File | Key columns |
|---|---|
| `raw_report.csv` | region, product, year, rev_op_type, sales_budget_type, month, amount |
| `layer1_report.csv` | region, product, year, rev_op_type, sales_budget_type, total, h1, h2, q1, q2, q3, q4, ytd |
| `layer2_report.csv` | …same cohort key…, ytd_gap, budget_hit_rate, yoy_total, yoy_h1..q4, breakeven_month |
| `layer3_segmentation.csv` | …same cohort key…, total, ytd, ytd_gap, rank_total, rank_ytd_gap, share_pct |
| `layer3_timeseries.csv` | …same cohort key…, month, amount, mom_growth, vs_budget, seasonal_index |

## Decisions

- **Sidebar filters: global shared state** — filter values persist in `st.session_state` across all pages; each page imports and calls `render_sidebar()` to re-render with the same state.
- **Chart theme: dark mode** — all Plotly charts use `template="plotly_dark"`; Streamlit app uses `[theme] base = "dark"` in `.streamlit/config.toml`.
- **sync_input.py: copy only** — does not re-run `bm_analytics/main.py`; manual copy to `input/` is the primary workflow; `sync_input.py` is a convenience helper.
