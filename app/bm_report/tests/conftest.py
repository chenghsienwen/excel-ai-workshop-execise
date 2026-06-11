"""Shared pytest fixtures for bm_report tests."""
import pytest
import pandas as pd
from src import config


@pytest.fixture
def minimal_raw_df():
    """A minimal valid raw DataFrame matching the loader output schema."""
    return pd.DataFrame([{
        "product": "CDE",
        "year": 2024,
        "region": "APAC",
        "rev_op_type": "Gross",
        "sales_budget_type": "Actual",
        "month": "Jan",
        "amount": 1.5,
    }])


@pytest.fixture
def full_data_row():
    """Synthetic Excel row covering all three sections (Actual, Forecast, Budget).

    Layout mirrors config.SECTION_CONFIG:
      Actual   : region at col 1,  months at cols 2-13
      Forecast : region at col 16, months at cols 17-28
      Budget   : region at col 31, months at cols 32-43
    """
    row = [None] * 44
    row[1] = "APAC"
    row[16] = "EMEA"
    row[31] = "AMER"
    for i in range(12):
        row[2 + i] = float(i + 1)
        row[17 + i] = float(i + 1)
        row[32 + i] = float(i + 1)
    return tuple(row)
