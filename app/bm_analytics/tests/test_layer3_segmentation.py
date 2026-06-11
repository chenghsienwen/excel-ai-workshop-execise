"""Tests for src/layer3_segmentation.py."""
import datetime
import pathlib

import pandas as pd
import pytest

from src import layer1, layer3_segmentation, loader

_FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "raw_report_fixture.csv"
_TODAY = datetime.date(2025, 6, 15)
_SEGMENT_KEY = ["product", "year", "rev_op_type", "sales_budget_type"]


@pytest.fixture(scope="module")
def result():
    raw = loader.load(_FIXTURE)
    l1 = layer1.build(raw, today=_TODAY)
    return layer3_segmentation.build(l1)


def _segment(result, product, year, rev_op, sbt):
    return result[
        (result["product"] == product) & (result["year"] == str(year))
        & (result["rev_op_type"] == rev_op) & (result["sales_budget_type"] == sbt)
    ].set_index("region")


class TestLayer3SegSchema:
    def test_output_columns(self, result):
        assert list(result.columns) == layer3_segmentation.LAYER3_SEG_COLUMNS

    def test_row_count(self, result):
        # same as layer1: 24 cohorts
        assert len(result) == 24

    def test_rank_total_no_nulls(self, result):
        assert result["rank_total"].notna().all()

    def test_rank_ytd_gap_no_nulls(self, result):
        assert result["rank_ytd_gap"].notna().all()


class TestRankTotal:
    def test_minimum_rank_is_one(self, result):
        assert result["rank_total"].min() == 1

    def test_r1_beats_r2_for_gross_actual_2024(self, result):
        # R1 total=2400, R2 total=120 → R1 rank 1
        seg = _segment(result, "CDE", "2024", "Gross", "Actual")
        assert seg.loc["R1", "rank_total"] < seg.loc["R2", "rank_total"]

    def test_single_region_segment_rank_is_one(self):
        l1 = pd.DataFrame([
            {"region": "RX", "product": "P", "year": "2024", "rev_op_type": "Gross",
             "sales_budget_type": "Actual",
             "total": 500, "h1": 250, "h2": 250,
             "q1": 125, "q2": 125, "q3": 125, "q4": 125, "ytd": 250},
            {"region": "RX", "product": "P", "year": "2024", "rev_op_type": "Gross",
             "sales_budget_type": "Budget",
             "total": 600, "h1": 300, "h2": 300,
             "q1": 150, "q2": 150, "q3": 150, "q4": 150, "ytd": 300},
        ])
        out = layer3_segmentation.build(l1)
        assert out[out["sales_budget_type"] == "Actual"].iloc[0]["rank_total"] == 1


class TestRankYtdGap:
    def test_r2_worse_gap_has_lower_rank_number(self, result):
        # R2 ytd_gap=-5940 (far below budget) → rank 1 (ascending)
        seg = _segment(result, "CDE", "2024", "Gross", "Actual")
        assert seg.loc["R2", "rank_ytd_gap"] < seg.loc["R1", "rank_ytd_gap"]

    def test_ytd_gap_positive_when_actual_above_budget(self, result):
        row = result[
            (result["region"] == "R1") & (result["product"] == "CDE")
            & (result["year"] == "2024") & (result["rev_op_type"] == "Gross")
            & (result["sales_budget_type"] == "Actual")
        ].iloc[0]
        assert row["ytd_gap"] > 0

    def test_ytd_gap_negative_when_actual_below_budget(self, result):
        row = result[
            (result["region"] == "R2") & (result["product"] == "CDE")
            & (result["year"] == "2024") & (result["rev_op_type"] == "Gross")
            & (result["sales_budget_type"] == "Actual")
        ].iloc[0]
        assert row["ytd_gap"] < 0


class TestSharePct:
    def test_sums_to_100_per_segment(self, result):
        sums = result.groupby(_SEGMENT_KEY)["share_pct"].sum().round(1)
        assert (sums == 100.0).all()

    def test_r1_higher_share_than_r2_gross_actual_2024(self, result):
        seg = _segment(result, "CDE", "2024", "Gross", "Actual")
        assert seg.loc["R1", "share_pct"] > seg.loc["R2", "share_pct"]

    def test_positive_total_gives_positive_share(self, result):
        nonzero = result[result["total"] > 0]
        assert (nonzero["share_pct"] > 0).all()

    def test_zero_segment_total_share_pct_is_nan(self):
        l1 = pd.DataFrame([
            {"region": "RA", "product": "P", "year": "2024", "rev_op_type": "Gross",
             "sales_budget_type": "Actual",
             "total": 0, "h1": 0, "h2": 0, "q1": 0, "q2": 0, "q3": 0, "q4": 0, "ytd": 0},
            {"region": "RA", "product": "P", "year": "2024", "rev_op_type": "Gross",
             "sales_budget_type": "Budget",
             "total": 0, "h1": 0, "h2": 0, "q1": 0, "q2": 0, "q3": 0, "q4": 0, "ytd": 0},
        ])
        out = layer3_segmentation.build(l1)
        assert pd.isna(out[out["sales_budget_type"] == "Actual"].iloc[0]["share_pct"])
