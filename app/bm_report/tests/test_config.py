"""Unit tests for src/config.py."""
import logging
import time

from src import config


class TestConstants:
    def test_amount_scale(self):
        assert config.AMOUNT_SCALE == 10_000

    def test_month_cols_count(self):
        assert len(config.MONTH_COLS) == 12

    def test_month_cols_first_and_last(self):
        assert config.MONTH_COLS[0] == "Jan"
        assert config.MONTH_COLS[11] == "Dec"

    def test_output_columns_order(self):
        assert config.OUTPUT_COLUMNS == [
            "product", "year", "region", "rev_op_type",
            "sales_budget_type", "month", "amount",
        ]

    def test_valid_rev_op_types_matches_header_values(self):
        assert config.VALID_REV_OP_TYPES == frozenset(config.REV_OP_TYPE_HEADERS.values())

    def test_valid_rev_op_types_non_empty(self):
        assert len(config.VALID_REV_OP_TYPES) > 0

    def test_valid_sales_budget_types_derived_from_section_config(self):
        expected = frozenset(sbt for sbt, _, _ in config.SECTION_CONFIG)
        assert config.VALID_SALES_BUDGET_TYPES == expected

    def test_section_config_month_start_follows_region_col(self):
        for _, reg_col, month_start in config.SECTION_CONFIG:
            assert month_start == reg_col + 1

    def test_section_config_region_cols_unique(self):
        reg_cols = [reg_col for _, reg_col, _ in config.SECTION_CONFIG]
        assert len(reg_cols) == len(set(reg_cols))

    def test_section_type_labels_lowercase(self):
        for label in config.SECTION_TYPE_LABELS:
            assert label == label.lower()


class TestTimed:
    def test_yields_without_error(self):
        with config.timed("test"):
            pass

    def test_logs_label(self, caplog):
        with caplog.at_level(logging.INFO):
            with config.timed("my-stage"):
                pass
        assert "my-stage" in caplog.text

    def test_logs_timing_marker(self, caplog):
        with caplog.at_level(logging.INFO):
            with config.timed("x"):
                pass
        assert "[timing]" in caplog.text

    def test_elapsed_is_positive(self):
        start = time.perf_counter()
        with config.timed("measure"):
            time.sleep(0.01)
        elapsed = time.perf_counter() - start
        assert elapsed > 0

    def test_nested_timed_blocks(self):
        with config.timed("outer"):
            with config.timed("inner"):
                pass
