"""Tests for src/layer1.py."""
import datetime
import pathlib

import pytest

from src import layer1, loader

_FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "raw_report_fixture.csv"
_TODAY = datetime.date(2025, 6, 15)

_EXPECTED_COLUMNS = [
    "region", "product", "year", "rev_op_type", "sales_budget_type",
    "total", "h1", "h2", "q1", "q2", "q3", "q4", "ytd",
]


@pytest.fixture(scope="module")
def result():
    raw = loader.load(_FIXTURE)
    return layer1.build(raw, today=_TODAY)


def _row(result, region, product, year, rev_op, sbt):
    return result[
        (result["region"] == region) & (result["product"] == product)
        & (result["year"] == str(year)) & (result["rev_op_type"] == rev_op)
        & (result["sales_budget_type"] == sbt)
    ].iloc[0]


class TestLayer1Schema:
    def test_column_order(self, result):
        assert list(result.columns) == _EXPECTED_COLUMNS

    def test_row_count(self, result):
        # 2 regions × 1 product × 2 years × 2 rev_op × 3 sbt = 24 cohorts
        assert len(result) == 24

    def test_no_null_values(self, result):
        assert not result.isnull().any().any()


class TestLayer1Arithmetic:
    def test_h1_plus_h2_equals_total(self, result):
        assert ((result["h1"] + result["h2"]) == result["total"]).all()

    def test_quarter_partition(self, result):
        q_sum = result["q1"] + result["q2"] + result["q3"] + result["q4"]
        assert (q_sum == result["total"]).all()

    def test_ytd_lte_total(self, result):
        assert (result["ytd"] <= result["total"]).all()

    def test_ytd_equals_h1_for_june_reference(self, result):
        assert (result["ytd"] == result["h1"]).all()

    def test_gross_actual_2024_total(self, result):
        # 200/mo × 12 = 2400
        assert _row(result, "R1", "CDE", "2024", "Gross", "Actual")["total"] == 2400

    def test_net_actual_2024_total(self, result):
        # 50+50+300+0×9 = 400
        assert _row(result, "R1", "CDE", "2024", "Net", "Actual")["total"] == 400

    def test_net_actual_2024_h1(self, result):
        # Jan=50, Feb=50, Mar=300, Apr-Jun=0 → h1 = 400
        assert _row(result, "R1", "CDE", "2024", "Net", "Actual")["h1"] == 400

    def test_net_actual_2024_h2_is_zero(self, result):
        assert _row(result, "R1", "CDE", "2024", "Net", "Actual")["h2"] == 0

    @pytest.mark.parametrize("rev_op, sbt, expected_total", [
        ("Gross", "Actual",   2400),
        ("Gross", "Budget",   1200),
        ("Gross", "Forecast", 1800),
        ("Net",   "Actual",    400),
        ("Net",   "Budget",   1200),
        ("Net",   "Forecast", 1200),
    ])
    def test_r1_cde_2024_totals(self, result, rev_op, sbt, expected_total):
        assert _row(result, "R1", "CDE", "2024", rev_op, sbt)["total"] == expected_total

    def test_r2_gross_actual_2025_total(self, result):
        # 20/mo × 12 = 240
        assert _row(result, "R2", "CDE", "2025", "Gross", "Actual")["total"] == 240
