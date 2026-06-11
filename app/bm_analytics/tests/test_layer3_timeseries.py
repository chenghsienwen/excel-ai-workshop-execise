"""Tests for src/layer3_timeseries.py."""
import pathlib

import pandas as pd
import pytest

from src import config, layer3_timeseries, loader

_FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "raw_report_fixture.csv"


@pytest.fixture(scope="module")
def raw_df():
    return loader.load(_FIXTURE)


@pytest.fixture(scope="module")
def result(raw_df):
    return layer3_timeseries.build(raw_df)


def _cohort(result, region, product, year, rev_op, sbt):
    return result[
        (result["region"] == region) & (result["product"] == product)
        & (result["year"] == str(year)) & (result["rev_op_type"] == rev_op)
        & (result["sales_budget_type"] == sbt)
    ]


class TestLayer3TsSchema:
    def test_output_columns(self, result):
        assert list(result.columns) == layer3_timeseries.LAYER3_TS_COLUMNS

    def test_row_count(self, result):
        assert len(result) == 288

    def test_amount_numeric(self, result):
        assert pd.api.types.is_numeric_dtype(result["amount"])


class TestMonthOrdering:
    def test_months_in_calendar_order_per_cohort(self, result):
        month_order = {m: i for i, m in enumerate(config.MONTH_COLS)}
        cohort = _cohort(result, "R1", "CDE", "2024", "Gross", "Actual")
        indices = cohort["month"].map(month_order).tolist()
        assert indices == sorted(indices)

    def test_all_12_months_present_per_cohort(self, result):
        cohort = _cohort(result, "R1", "CDE", "2024", "Gross", "Actual")
        assert set(cohort["month"]) == set(config.MONTH_COLS)


class TestMomGrowth:
    def test_mom_growth_null_for_every_january(self, result):
        jan_rows = result[result["month"] == "Jan"]
        assert jan_rows["mom_growth"].isna().all()

    def test_mom_growth_one_for_uniform_cohort(self, result):
        # 200/mo throughout → Feb onward = 200/200 = 1.0
        non_jan = _cohort(result, "R1", "CDE", "2024", "Gross", "Actual")
        assert (non_jan[non_jan["month"] != "Jan"]["mom_growth"] == 1.0).all()

    def test_mom_growth_spike_in_march(self, result):
        # Net Actual 2024: Jan=50, Feb=50, Mar=300 → Mar ratio = 300/50 = 6.0
        cohort = _cohort(result, "R1", "CDE", "2024", "Net", "Actual")
        march = cohort[cohort["month"] == "Mar"].iloc[0]
        assert abs(float(march["mom_growth"]) - 6.0) < 0.001

    def test_mom_growth_null_at_cohort_boundary(self, result):
        # First month of each distinct cohort is NaN regardless of row order
        r2_jan = _cohort(result, "R2", "CDE", "2024", "Gross", "Actual")
        assert pd.isna(r2_jan[r2_jan["month"] == "Jan"].iloc[0]["mom_growth"])


class TestSeasonalIndex:
    def test_sums_to_one_per_cohort(self, result):
        cohort_key = layer3_timeseries.LAYER3_TS_COLUMNS[:5]
        sums = result.groupby(cohort_key)["seasonal_index"].sum().round(3)
        assert (sums == 1.0).all()

    def test_uniform_cohort_index_is_one_twelfth(self, result):
        # 200/mo, total=2400 → each month = round(1/12, 4) = 0.0833
        expected = round(1 / 12, 4)
        cohort = _cohort(result, "R1", "CDE", "2024", "Gross", "Actual")
        assert (cohort["seasonal_index"] == expected).all()

    def test_seasonal_index_proportional_to_spike(self, result):
        # Net Actual 2024: total=400, Mar=300 → seasonal_index(Mar)=0.75
        cohort = _cohort(result, "R1", "CDE", "2024", "Net", "Actual")
        march = cohort[cohort["month"] == "Mar"].iloc[0]
        assert abs(float(march["seasonal_index"]) - 0.75) < 0.001

    def test_seasonal_index_between_zero_and_one(self, result):
        idx = result["seasonal_index"].fillna(0)
        assert (idx >= 0).all() and (idx <= 1).all()


class TestVsBudget:
    def test_vs_budget_zero_for_budget_rows(self, result):
        budget_rows = result[result["sales_budget_type"] == "Budget"]
        assert (budget_rows["vs_budget"] == 0).all()

    def test_vs_budget_positive_when_actual_exceeds_budget(self, result):
        # R1 Gross Actual 2024: 200/mo, Budget 100/mo → vs_budget=100
        cohort = _cohort(result, "R1", "CDE", "2024", "Gross", "Actual")
        assert (cohort["vs_budget"] == 100).all()

    def test_vs_budget_negative_when_actual_below_budget(self, result):
        # R2 Gross Actual 2024: 10/mo, Budget 1000/mo → vs_budget=-990
        cohort = _cohort(result, "R2", "CDE", "2024", "Gross", "Actual")
        assert (cohort["vs_budget"] == -990).all()

    def test_vs_budget_value_for_net_actual_march(self, result):
        # Net Actual 2024: Mar=300, Budget=100 → vs_budget=200
        cohort = _cohort(result, "R1", "CDE", "2024", "Net", "Actual")
        march = cohort[cohort["month"] == "Mar"].iloc[0]
        assert march["vs_budget"] == 200
