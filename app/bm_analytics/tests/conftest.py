"""Shared pytest fixtures for bm_analytics tests."""
import datetime
import pathlib

import pandas as pd
import pytest

from src import config, layer1, loader

_FIXTURE_PATH = pathlib.Path(__file__).parent / "fixtures" / "raw_report_fixture.csv"
_TODAY = datetime.date(2025, 6, 15)


def make_monthly_rows(product, year, region, rev_op_type, sales_budget_type, amounts):
    """Build 12 rows (one per month) with given monthly amounts list."""
    assert len(amounts) == 12
    return [
        {
            "product": product,
            "year": str(year),
            "region": region,
            "rev_op_type": rev_op_type,
            "sales_budget_type": sales_budget_type,
            "month": month,
            "amount": amount,
        }
        for month, amount in zip(config.MONTH_COLS, amounts)
    ]


@pytest.fixture(scope="session")
def raw_df():
    return loader.load(_FIXTURE_PATH)


@pytest.fixture(scope="session")
def layer1_df(raw_df):
    return layer1.build(raw_df, today=_TODAY)
