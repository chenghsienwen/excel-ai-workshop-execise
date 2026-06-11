"""Tests for src/periods.py."""
import datetime
import pathlib

import pandas as pd
import pytest

from src import config, loader, periods

_FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "raw_report_fixture.csv"
_TODAY = datetime.date(2025, 6, 15)


class TestPeriodMonthsConstants:
    def test_quarters_partition_all_months(self):
        all_q = set(
            periods.PERIOD_MONTHS["q1"]
            + periods.PERIOD_MONTHS["q2"]
            + periods.PERIOD_MONTHS["q3"]
            + periods.PERIOD_MONTHS["q4"]
        )
        assert all_q == set(periods.PERIOD_MONTHS["total"])

    def test_halves_partition_all_months(self):
        all_h = set(periods.PERIOD_MONTHS["h1"] + periods.PERIOD_MONTHS["h2"])
        assert all_h == set(periods.PERIOD_MONTHS["total"])

    def test_h1_equals_q1_plus_q2(self):
        assert set(periods.PERIOD_MONTHS["h1"]) == set(
            periods.PERIOD_MONTHS["q1"] + periods.PERIOD_MONTHS["q2"]
        )

    def test_h2_equals_q3_plus_q4(self):
        assert set(periods.PERIOD_MONTHS["h2"]) == set(
            periods.PERIOD_MONTHS["q3"] + periods.PERIOD_MONTHS["q4"]
        )

    def test_total_has_12_months(self):
        assert len(periods.PERIOD_MONTHS["total"]) == 12

    @pytest.mark.parametrize("period", ["h1", "h2", "q1", "q2", "q3", "q4"])
    def test_no_duplicate_months_in_period(self, period):
        months = periods.PERIOD_MONTHS[period]
        assert len(months) == len(set(months))


class TestYtdMonths:
    @pytest.mark.parametrize("month_num, expected_count", [
        (1, 1), (3, 3), (6, 6), (9, 9), (12, 12),
    ])
    def test_length_equals_month_number(self, month_num, expected_count):
        result = periods.ytd_months(datetime.date(2025, month_num, 15))
        assert len(result) == expected_count

    def test_june_returns_jan_through_jun(self):
        assert periods.ytd_months(datetime.date(2025, 6, 15)) == [
            "Jan", "Feb", "Mar", "Apr", "May", "Jun"
        ]

    def test_january_returns_only_jan(self):
        assert periods.ytd_months(datetime.date(2025, 1, 1)) == ["Jan"]

    def test_december_returns_all_months(self):
        assert periods.ytd_months(datetime.date(2025, 12, 31)) == config.MONTH_COLS

    def test_mid_month_date_uses_current_month(self):
        assert periods.ytd_months(datetime.date(2025, 3, 15)) == ["Jan", "Feb", "Mar"]


class TestAggregatePeriods:
    @pytest.fixture(scope="class")
    def result(self):
        raw = loader.load(_FIXTURE)
        return periods.aggregate_periods(raw, today=_TODAY)

    def test_output_contains_all_period_columns(self, result):
        for col in ["total", "h1", "h2", "q1", "q2", "q3", "q4", "ytd"]:
            assert col in result.columns

    def test_cohort_key_preserved(self, result):
        for field in config.COHORT_KEY:
            assert field in result.columns

    def test_h1_plus_h2_equals_total(self, result):
        assert ((result["h1"] + result["h2"]) == result["total"]).all()

    def test_quarter_partition_matches_total(self, result):
        q_sum = result["q1"] + result["q2"] + result["q3"] + result["q4"]
        assert (q_sum == result["total"]).all()

    def test_ytd_is_h1_for_june(self, result):
        # today=Jun → ytd = Jan-Jun = h1
        assert (result["ytd"] == result["h1"]).all()

    def test_ytd_lte_total(self, result):
        assert (result["ytd"] <= result["total"]).all()

    def test_ytd_equals_total_for_december(self):
        raw = loader.load(_FIXTURE)
        result = periods.aggregate_periods(raw, today=datetime.date(2025, 12, 31))
        assert (result["ytd"] == result["total"]).all()

    def test_specific_total_r1_gross_actual_2024(self, result):
        # 200/mo × 12 = 2400
        row = result[
            (result["region"] == "R1") & (result["product"] == "CDE")
            & (result["year"] == "2024") & (result["rev_op_type"] == "Gross")
            & (result["sales_budget_type"] == "Actual")
        ].iloc[0]
        assert row["total"] == 2400

    def test_today_none_does_not_raise(self):
        raw = loader.load(_FIXTURE)
        result = periods.aggregate_periods(raw, today=None)
        assert len(result) > 0

    def test_sparse_months_fill_with_zero(self):
        # Only Jan present; remaining months should default to 0
        rows = [{
            "product": "P", "year": "2024", "region": "R",
            "rev_op_type": "Gross", "sales_budget_type": "Actual",
            "month": "Jan", "amount": 100,
        }]
        result = periods.aggregate_periods(
            pd.DataFrame(rows), today=datetime.date(2024, 12, 31)
        )
        assert result.iloc[0]["total"] == 100
        assert result.iloc[0]["h2"] == 0
        assert result.iloc[0]["q2"] == 0
