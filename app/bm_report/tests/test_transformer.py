"""Unit tests for src/transformer.py."""
import logging

import numpy as np
import pandas as pd
import pytest

from src import config
from src.transformer import (
    _apply_validations,
    _strip_str_cols,
    _validate_column,
    transform,
)


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_df(**overrides):
    """Return a minimal valid raw DataFrame, with optional column overrides."""
    base = {
        "product": ["CDE"],
        "year": [2024],
        "region": ["APAC"],
        "rev_op_type": ["Gross"],
        "sales_budget_type": ["Actual"],
        "month": ["Jan"],
        "amount": [1.5],
    }
    base.update(overrides)
    return pd.DataFrame(base)


# ── _validate_column ──────────────────────────────────────────────────────────

class TestValidateColumn:
    def test_all_valid_keeps_all_rows(self):
        df = pd.DataFrame({"rev_op_type": list(config.VALID_REV_OP_TYPES)})
        result = _validate_column(df, "rev_op_type", config.VALID_REV_OP_TYPES)
        assert len(result) == len(df)

    def test_invalid_row_dropped(self):
        df = pd.DataFrame({"rev_op_type": ["Gross", "BadValue", "Net"]})
        result = _validate_column(df, "rev_op_type", config.VALID_REV_OP_TYPES)
        assert len(result) == 2
        assert "BadValue" not in result["rev_op_type"].values

    def test_all_invalid_returns_empty(self):
        df = pd.DataFrame({"rev_op_type": ["X", "Y", "Z"]})
        assert _validate_column(df, "rev_op_type", config.VALID_REV_OP_TYPES).empty

    def test_invalid_value_logged_as_warning(self, caplog):
        df = pd.DataFrame({"rev_op_type": ["BadValue"]})
        with caplog.at_level(logging.WARNING, logger="src.transformer"):
            _validate_column(df, "rev_op_type", config.VALID_REV_OP_TYPES)
        assert "BadValue" in caplog.text

    def test_no_warning_when_all_valid(self, caplog):
        df = pd.DataFrame({"rev_op_type": ["Gross"]})
        with caplog.at_level(logging.WARNING, logger="src.transformer"):
            _validate_column(df, "rev_op_type", config.VALID_REV_OP_TYPES)
        assert "WARNING" not in caplog.text

    def test_returns_copy_not_view(self):
        df = pd.DataFrame({"rev_op_type": ["Gross"]})
        result = _validate_column(df, "rev_op_type", config.VALID_REV_OP_TYPES)
        result["rev_op_type"] = "Modified"
        assert df["rev_op_type"].iloc[0] == "Gross"

    def test_sales_budget_type_validation(self):
        df = pd.DataFrame({"sales_budget_type": ["Actual", "Unknown", "Budget"]})
        result = _validate_column(df, "sales_budget_type", config.VALID_SALES_BUDGET_TYPES)
        assert set(result["sales_budget_type"]) == {"Actual", "Budget"}


# ── _strip_str_cols ───────────────────────────────────────────────────────────

class TestStripStrCols:
    def test_strips_leading_trailing_spaces(self):
        df = _make_df(region=["  APAC  "], rev_op_type=["  Gross  "],
                      sales_budget_type=["  Actual  "], month=["  Jan  "], product=["  CDE  "])
        result = _strip_str_cols(df)
        assert result["region"].iloc[0] == "APAC"
        assert result["rev_op_type"].iloc[0] == "Gross"
        assert result["sales_budget_type"].iloc[0] == "Actual"
        assert result["month"].iloc[0] == "Jan"
        assert result["product"].iloc[0] == "CDE"

    def test_strips_tabs_and_newlines(self):
        df = _make_df(region=["\tAPAC\n"])
        result = _strip_str_cols(df)
        assert result["region"].iloc[0] == "APAC"

    def test_does_not_mutate_input(self):
        df = _make_df(region=["  APAC  "])
        _strip_str_cols(df)
        assert df["region"].iloc[0] == "  APAC  "

    def test_non_string_columns_unchanged(self):
        df = _make_df(year=[2024], amount=[999.0])
        result = _strip_str_cols(df)
        assert result["year"].iloc[0] == 2024
        assert result["amount"].iloc[0] == 999.0

    def test_already_clean_strings_unchanged(self):
        df = _make_df(region=["APAC"])
        result = _strip_str_cols(df)
        assert result["region"].iloc[0] == "APAC"


# ── _apply_validations ────────────────────────────────────────────────────────

class TestApplyValidations:
    def test_valid_row_kept(self):
        df = _make_df()
        result = _apply_validations(df)
        assert len(result) == 1

    def test_invalid_rev_op_type_dropped(self):
        df = _make_df(rev_op_type=["InvalidType"])
        assert _apply_validations(df).empty

    def test_invalid_sales_budget_type_dropped(self):
        df = _make_df(sales_budget_type=["InvalidSBT"])
        assert _apply_validations(df).empty

    def test_both_invalid_dropped(self):
        df = _make_df(rev_op_type=["Bad"], sales_budget_type=["Bad"])
        assert _apply_validations(df).empty

    def test_partial_validity_keeps_valid_rows(self):
        df = pd.DataFrame([
            {**_make_df().iloc[0].to_dict(), "rev_op_type": "Gross"},
            {**_make_df().iloc[0].to_dict(), "rev_op_type": "INVALID"},
        ])
        result = _apply_validations(df)
        assert len(result) == 1
        assert result["rev_op_type"].iloc[0] == "Gross"

    def test_all_valid_rev_op_types_accepted(self):
        for valid in config.VALID_REV_OP_TYPES:
            df = _make_df(rev_op_type=[valid])
            assert not _apply_validations(df).empty, f"{valid!r} should be valid"

    def test_all_valid_sales_budget_types_accepted(self):
        for valid in config.VALID_SALES_BUDGET_TYPES:
            df = _make_df(sales_budget_type=[valid])
            assert not _apply_validations(df).empty, f"{valid!r} should be valid"


# ── transform ─────────────────────────────────────────────────────────────────

class TestTransform:
    def test_output_columns_match_config(self):
        result = transform(_make_df(), "CDE", 2024)
        assert list(result.columns) == config.OUTPUT_COLUMNS

    def test_amount_scaled_by_amount_scale(self):
        result = transform(_make_df(amount=[1.5]), "CDE", 2024)
        assert result["amount"].iloc[0] == int(round(1.5 * config.AMOUNT_SCALE))

    def test_amount_is_integer_dtype(self):
        result = transform(_make_df(amount=[2.0]), "CDE", 2024)
        assert pd.api.types.is_integer_dtype(result["amount"])

    def test_nan_amount_becomes_zero(self):
        result = transform(_make_df(amount=[np.nan]), "CDE", 2024)
        assert result["amount"].iloc[0] == 0

    def test_zero_amount_stays_zero(self):
        result = transform(_make_df(amount=[0.0]), "CDE", 2024)
        assert result["amount"].iloc[0] == 0

    def test_whitespace_stripped_from_string_cols(self):
        df = _make_df(region=["  APAC  "], rev_op_type=["  Gross  "])
        result = transform(df, "CDE", 2024)
        assert result["region"].iloc[0] == "APAC"
        assert result["rev_op_type"].iloc[0] == "Gross"

    def test_invalid_rev_op_type_dropped(self):
        df = _make_df(rev_op_type=["INVALID"])
        result = transform(df, "CDE", 2024)
        assert result.empty

    def test_invalid_sales_budget_type_dropped(self):
        df = _make_df(sales_budget_type=["INVALID"])
        result = transform(df, "CDE", 2024)
        assert result.empty

    def test_index_is_reset(self):
        df = pd.concat([_make_df(), _make_df()]).iloc[1:]  # index starts at 1
        result = transform(df, "CDE", 2024)
        assert list(result.index) == list(range(len(result)))

    def test_empty_dataframe_returns_empty(self):
        df = pd.DataFrame(columns=config.OUTPUT_COLUMNS)
        result = transform(df, "CDE", 2024)
        assert result.empty

    def test_multiple_rows_all_transformed(self):
        df = pd.DataFrame([
            {"product": "CDE", "year": 2024, "region": "APAC",
             "rev_op_type": "Gross", "sales_budget_type": "Actual",
             "month": "Jan", "amount": 1.0},
            {"product": "CDE", "year": 2024, "region": "EMEA",
             "rev_op_type": "Net", "sales_budget_type": "Budget",
             "month": "Feb", "amount": 2.0},
        ])
        result = transform(df, "CDE", 2024)
        assert len(result) == 2
        assert result["amount"].tolist() == [
            int(round(1.0 * config.AMOUNT_SCALE)),
            int(round(2.0 * config.AMOUNT_SCALE)),
        ]

    def test_amount_rounding(self):
        # 1.00005 * 10000 = 10000.5 → rounds to 10001 (banker's rounding or standard)
        df = _make_df(amount=[0.00015])
        result = transform(df, "CDE", 2024)
        expected = int(round(0.00015 * config.AMOUNT_SCALE))
        assert result["amount"].iloc[0] == expected
