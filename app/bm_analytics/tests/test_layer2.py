"""Tests for src/layer2.py — integration + unit tests for private helpers."""
import datetime
import pathlib

import pandas as pd
import pytest

from src import config, layer1, layer2, loader
from src.layer2 import _attach_yoy, _attach_ytd_metrics, _compute_breakeven

_FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "raw_report_fixture.csv"
_TODAY = datetime.date(2025, 6, 15)


@pytest.fixture(scope="module")
def raw_df():
    return loader.load(_FIXTURE)


@pytest.fixture(scope="module")
def l1_df(raw_df):
    return layer1.build(raw_df, today=_TODAY)


@pytest.fixture(scope="module")
def result(l1_df, raw_df):
    return layer2.build(l1_df, raw_df)


def _row(result, region, product, year, rev_op, sbt):
    return result[
        (result["region"] == region) & (result["product"] == product)
        & (result["year"] == str(year)) & (result["rev_op_type"] == rev_op)
        & (result["sales_budget_type"] == sbt)
    ].iloc[0]


def _make_layer1(pairs):
    """Build a layer1-shaped DataFrame from (sbt, ytd_val) pairs."""
    rows = [
        {
            "region": "R1", "product": "P", "year": "2024",
            "rev_op_type": "Gross", "sales_budget_type": sbt,
            "total": v * 12, "h1": v * 6, "h2": v * 6,
            "q1": v * 3, "q2": v * 3, "q3": v * 3, "q4": v * 3,
            "ytd": v,
        }
        for sbt, v in pairs
    ]
    return pd.DataFrame(rows)


def _make_raw_monthly(sbt_amounts):
    """Build a raw monthly DataFrame from {sbt: amount/mo} dict."""
    rows = [
        {"region": "R", "product": "P", "year": "2024", "rev_op_type": "G",
         "sales_budget_type": sbt, "month": m, "amount": amt}
        for sbt, amt in sbt_amounts.items()
        for m in config.MONTH_COLS
    ]
    return pd.DataFrame(rows)


class TestLayer2Schema:
    def test_output_columns(self, result):
        assert list(result.columns) == layer2.LAYER2_COLUMNS

    def test_row_count_matches_layer1(self, result, l1_df):
        assert len(result) == len(l1_df)


class TestYtdMetrics:
    def test_ytd_gap_actual_exceeds_budget(self, result):
        # Actual ytd=1200, Budget ytd=600 → gap=600
        assert _row(result, "R1", "CDE", "2024", "Gross", "Actual")["ytd_gap"] == 600

    def test_ytd_gap_actual_below_budget(self, result):
        # Net Actual ytd=400, Budget ytd=600 → gap=-200
        assert _row(result, "R1", "CDE", "2024", "Net", "Actual")["ytd_gap"] == -200

    def test_budget_hit_rate_200_when_double(self, result):
        # 1200/600 × 100 = 200
        assert _row(result, "R1", "CDE", "2024", "Gross", "Actual")["budget_hit_rate"] == 200

    def test_budget_hit_rate_100_when_equal(self, result):
        # R1, Net 2025: Actual == Budget == 100/mo
        assert _row(result, "R1", "CDE", "2025", "Net", "Actual")["budget_hit_rate"] == 100

    def test_budget_hit_rate_120_when_partial_over(self, result):
        # R1, Gross 2025: Actual ytd=1800, Budget ytd=1500 → 120
        assert _row(result, "R1", "CDE", "2025", "Gross", "Actual")["budget_hit_rate"] == 120

    def test_attach_ytd_metrics_unit(self):
        l1 = _make_layer1([("Actual", 200), ("Budget", 100)])
        out = _attach_ytd_metrics(l1)
        actual = out[out["sales_budget_type"] == "Actual"].iloc[0]
        assert actual["ytd_gap"] == 100
        assert actual["budget_hit_rate"] == 200

    def test_budget_hit_rate_null_when_budget_ytd_zero(self):
        l1 = _make_layer1([("Actual", 50), ("Budget", 0)])
        out = _attach_ytd_metrics(l1)
        actual = out[out["sales_budget_type"] == "Actual"].iloc[0]
        assert pd.isna(actual["budget_hit_rate"])


class TestYoy:
    def test_yoy_zero_for_all_2024_rows(self, result):
        # No 2023 data exists → prior year lookup returns nothing → fillna(0)
        rows_2024 = result[result["year"] == "2024"]
        assert (rows_2024["yoy_total"] == 0).all()

    def test_yoy_total_r1_gross_2025(self, result):
        # 3600 / 2400 = 1.5
        row = _row(result, "R1", "CDE", "2025", "Gross", "Actual")
        assert abs(float(row["yoy_total"]) - 1.5) < 0.001

    def test_yoy_total_r1_net_2025(self, result):
        # 1200 / 400 = 3.0
        row = _row(result, "R1", "CDE", "2025", "Net", "Actual")
        assert abs(float(row["yoy_total"]) - 3.0) < 0.001

    def test_yoy_total_r2_gross_2025(self, result):
        # 240 / 120 = 2.0
        row = _row(result, "R2", "CDE", "2025", "Gross", "Actual")
        assert abs(float(row["yoy_total"]) - 2.0) < 0.001

    @pytest.mark.parametrize("period", ["total", "h1", "h2", "q1", "q2", "q3", "q4"])
    def test_yoy_column_present(self, result, period):
        assert f"yoy_{period}" in result.columns

    def test_attach_yoy_prior_zero_gives_zero(self):
        l1 = pd.DataFrame([
            {"region": "R", "product": "P", "year": "2024", "rev_op_type": "G",
             "sales_budget_type": "Actual",
             "total": 0, "h1": 0, "h2": 0, "q1": 0, "q2": 0, "q3": 0, "q4": 0, "ytd": 0},
            {"region": "R", "product": "P", "year": "2025", "rev_op_type": "G",
             "sales_budget_type": "Actual",
             "total": 100, "h1": 50, "h2": 50, "q1": 25, "q2": 25, "q3": 25, "q4": 25, "ytd": 50},
        ])
        out = _attach_yoy(l1)
        assert out[out["year"] == "2025"].iloc[0]["yoy_total"] == 0


class TestBreakeven:
    def test_breakeven_null_for_non_actual(self, result):
        non_actual = result[result["sales_budget_type"] != "Actual"]
        assert non_actual["breakeven_month"].isna().all()

    def test_breakeven_january_when_immediately_above(self, result):
        # R1 Gross Actual 2024: 200/mo vs Budget 100/mo → crosses Jan
        assert _row(result, "R1", "CDE", "2024", "Gross", "Actual")["breakeven_month"] == 1

    def test_breakeven_march_for_net_actual_2024(self, result):
        # cumActual=[50,100,400,...] vs cumBudget=[100,200,300,...] → Mar
        assert _row(result, "R1", "CDE", "2024", "Net", "Actual")["breakeven_month"] == 3

    def test_breakeven_null_when_never_crosses(self, result):
        # R2 Gross Actual 2024: 10/mo vs Budget 1000/mo → never crosses
        assert pd.isna(_row(result, "R2", "CDE", "2024", "Gross", "Actual")["breakeven_month"])

    def test_breakeven_january_when_equal_from_start(self, result):
        # R1 Net Actual 2025: 100/mo == Budget 100/mo → breakeven Jan
        assert _row(result, "R1", "CDE", "2025", "Net", "Actual")["breakeven_month"] == 1

    def test_compute_breakeven_unit_immediate(self):
        raw = _make_raw_monthly({"Actual": 200, "Budget": 100})
        result = _compute_breakeven(raw)
        assert result.iloc[0]["breakeven_month"] == 1

    def test_compute_breakeven_unit_never(self):
        raw = _make_raw_monthly({"Actual": 10, "Budget": 1000})
        result = _compute_breakeven(raw)
        assert pd.isna(result.iloc[0]["breakeven_month"])

    def test_compute_breakeven_returns_cross_key_columns(self):
        raw = _make_raw_monthly({"Actual": 50, "Budget": 50})
        result = _compute_breakeven(raw)
        expected = ["region", "product", "year", "rev_op_type", "breakeven_month"]
        assert list(result.columns) == expected
