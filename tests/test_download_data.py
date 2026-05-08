import os
import pytest
from pathlib import Path
from scripts.download_data import download_filipcikova_sa2


def test_download_filipcikova_sa2_writes_expected_file(tmp_path):
    out = tmp_path / "health_access_sa2.csv"
    download_filipcikova_sa2(out)
    assert out.exists()
    assert out.stat().st_size > 500_000  # ~600KB expected
    # Verify expected columns
    import pandas as pd
    df = pd.read_csv(out, nrows=1)
    expected = {"SA2_CODE21", "gp_duration", "gp_bulk_billing_duration", "Person", "STE_NAME21"}
    assert expected.issubset(df.columns)
