"""Unit tests for src/writer.py."""
import pandas as pd
import pytest

from src import config
from src.writer import write_report


def _sample_df():
    return pd.DataFrame([{
        "product": "CDE",
        "year": 2024,
        "region": "APAC",
        "rev_op_type": "Gross",
        "sales_budget_type": "Actual",
        "month": "Jan",
        "amount": 10000,
    }])


class TestWriteReport:
    def test_creates_file(self, tmp_path):
        out = tmp_path / "report.csv"
        write_report(_sample_df(), out)
        assert out.exists()

    def test_creates_parent_directories(self, tmp_path):
        out = tmp_path / "deeply" / "nested" / "output.csv"
        write_report(_sample_df(), out)
        assert out.exists()

    def test_csv_content_matches_dataframe(self, tmp_path):
        df = _sample_df()
        out = tmp_path / "report.csv"
        write_report(df, out)
        loaded = pd.read_csv(out)
        assert loaded["product"].iloc[0] == "CDE"
        assert loaded["amount"].iloc[0] == 10000

    def test_csv_columns_preserved(self, tmp_path):
        df = _sample_df()
        out = tmp_path / "report.csv"
        write_report(df, out)
        loaded = pd.read_csv(out)
        assert list(loaded.columns) == list(df.columns)

    def test_csv_row_count_preserved(self, tmp_path):
        df = pd.concat([_sample_df()] * 5, ignore_index=True)
        out = tmp_path / "report.csv"
        write_report(df, out)
        loaded = pd.read_csv(out)
        assert len(loaded) == 5

    def test_utf8_encoding(self, tmp_path):
        df = pd.DataFrame([{"region": "日本", "amount": 0}])
        out = tmp_path / "test.csv"
        write_report(df, out)
        content = out.read_text(encoding="utf-8")
        assert "日本" in content

    def test_no_index_column_written(self, tmp_path):
        out = tmp_path / "report.csv"
        write_report(_sample_df(), out)
        content = out.read_text()
        # Index column would appear as an unnamed first column
        assert content.startswith("product")

    def test_empty_dataframe_writes_headers_only(self, tmp_path):
        df = pd.DataFrame(columns=config.OUTPUT_COLUMNS)
        out = tmp_path / "empty.csv"
        write_report(df, out)
        loaded = pd.read_csv(out)
        assert loaded.empty
        assert list(loaded.columns) == config.OUTPUT_COLUMNS

    def test_overwrites_existing_file(self, tmp_path):
        out = tmp_path / "report.csv"
        write_report(pd.DataFrame([{"x": 1}]), out)
        write_report(pd.DataFrame([{"x": 99}]), out)
        loaded = pd.read_csv(out)
        assert loaded["x"].iloc[0] == 99
