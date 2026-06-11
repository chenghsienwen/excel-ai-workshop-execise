"""Tests for src/loader.py."""
import pathlib

import pandas as pd
import pytest

from src import config, loader

_FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "raw_report_fixture.csv"


def _write_csv(tmp_path, df):
    p = tmp_path / "input.csv"
    df.to_csv(p, index=False)
    return p


class TestLoadHappyPath:
    def test_returns_dataframe(self):
        assert isinstance(loader.load(_FIXTURE), pd.DataFrame)

    def test_all_required_columns_present(self):
        df = loader.load(_FIXTURE)
        assert set(config.INPUT_COLUMNS).issubset(df.columns)

    def test_row_count(self):
        assert len(loader.load(_FIXTURE)) == 288

    def test_amount_dtype_is_int64(self):
        assert loader.load(_FIXTURE)["amount"].dtype.name == "int64"

    def test_year_dtype_is_object(self):
        assert loader.load(_FIXTURE)["year"].dtype == object


class TestLoadValidation:
    def test_missing_column_raises_value_error(self, tmp_path):
        df = pd.read_csv(_FIXTURE).drop(columns=["amount"])
        with pytest.raises(ValueError):
            loader.load(_write_csv(tmp_path, df))

    def test_error_message_names_missing_column(self, tmp_path):
        df = pd.read_csv(_FIXTURE).drop(columns=["region"])
        with pytest.raises(ValueError, match="region"):
            loader.load(_write_csv(tmp_path, df))

    def test_multiple_missing_columns_raises(self, tmp_path):
        df = pd.read_csv(_FIXTURE).drop(columns=["amount", "month"])
        with pytest.raises(ValueError):
            loader.load(_write_csv(tmp_path, df))

    def test_file_not_found_raises(self):
        with pytest.raises(FileNotFoundError):
            loader.load(pathlib.Path("/nonexistent/path/file.csv"))


class TestLoadTransformations:
    def test_nan_amount_filled_with_zero(self, tmp_path):
        df = pd.read_csv(_FIXTURE)
        df.loc[0, "amount"] = float("nan")
        result = loader.load(_write_csv(tmp_path, df))
        assert result["amount"].iloc[0] == 0

    def test_all_nan_amounts_filled_with_zero(self, tmp_path):
        df = pd.read_csv(_FIXTURE)
        df["amount"] = float("nan")
        result = loader.load(_write_csv(tmp_path, df))
        assert (result["amount"] == 0).all()

    def test_integer_year_cast_to_string(self, tmp_path):
        df = pd.read_csv(_FIXTURE)
        df["year"] = df["year"].astype(int)
        result = loader.load(_write_csv(tmp_path, df))
        assert result["year"].dtype == object
        assert result["year"].iloc[0] == "2024"

    def test_no_rows_lost_during_load(self):
        raw = pd.read_csv(_FIXTURE)
        result = loader.load(_FIXTURE)
        assert len(result) == len(raw)
