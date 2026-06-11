"""Tests for src/config.py."""
import logging

import pytest

from src import config


class TestMonthCols:
    def test_count(self):
        assert len(config.MONTH_COLS) == 12

    def test_starts_with_jan(self):
        assert config.MONTH_COLS[0] == "Jan"

    def test_ends_with_dec(self):
        assert config.MONTH_COLS[-1] == "Dec"

    def test_no_duplicates(self):
        assert len(set(config.MONTH_COLS)) == 12


class TestCohortKey:
    def test_contains_all_required_fields(self):
        expected = {"region", "product", "year", "rev_op_type", "sales_budget_type"}
        assert set(config.COHORT_KEY) == expected

    def test_length(self):
        assert len(config.COHORT_KEY) == 5


class TestInputColumns:
    def test_contains_amount(self):
        assert "amount" in config.INPUT_COLUMNS

    def test_contains_month(self):
        assert "month" in config.INPUT_COLUMNS

    def test_contains_all_cohort_key_fields(self):
        for field in config.COHORT_KEY:
            assert field in config.INPUT_COLUMNS


class TestValidTypes:
    @pytest.mark.parametrize("t", ["Gross", "Net", "Op"])
    def test_valid_rev_op_types(self, t):
        assert t in config.VALID_REV_OP_TYPES

    @pytest.mark.parametrize("t", ["Actual", "Budget", "Forecast"])
    def test_valid_sales_budget_types(self, t):
        assert t in config.VALID_SALES_BUDGET_TYPES

    def test_rev_op_types_is_frozenset(self):
        assert isinstance(config.VALID_REV_OP_TYPES, frozenset)

    def test_sales_budget_types_is_frozenset(self):
        assert isinstance(config.VALID_SALES_BUDGET_TYPES, frozenset)


class TestTimed:
    def test_yields_without_error(self):
        with config.timed("stage"):
            pass

    def test_logs_label(self, caplog):
        with caplog.at_level(logging.INFO):
            with config.timed("my_stage"):
                pass
        assert "my_stage" in caplog.text

    def test_logs_timing_marker(self, caplog):
        with caplog.at_level(logging.INFO):
            with config.timed("any"):
                pass
        assert "[timing]" in caplog.text

    def test_exception_propagates(self):
        with pytest.raises(ValueError, match="sentinel"):
            with config.timed("stage"):
                raise ValueError("sentinel")

    def test_nested_blocks_do_not_raise(self):
        with config.timed("outer"):
            with config.timed("inner"):
                pass
