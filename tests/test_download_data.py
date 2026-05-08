from pathlib import Path
from scripts.download_data import download_filipcikova_sa2, download_sa2_boundaries, download_phn_sa2_concordance


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


def test_download_phn_concordance(tmp_path):
    out = tmp_path / "phn_sa2_concordance.csv"
    download_phn_sa2_concordance(out)
    assert out.exists()
    import pandas as pd
    df = pd.read_csv(out, dtype=str)
    assert {"SA2_CODE21", "PHN_CODE", "PHN_NAME"}.issubset(df.columns)
    assert df["PHN_NAME"].nunique() == 31
    assert (df["PHN_NAME"] == "Western NSW").any()
    # No SA2s without PHN assignment (DHDA includes special categories with NaN PHN)
    assert df["PHN_CODE"].notna().all()
    assert df["PHN_NAME"].notna().all()


def test_download_sa2_boundaries_national(tmp_path):
    out = tmp_path / "sa2_2021_aust.geojson"
    download_sa2_boundaries(out)
    assert out.exists()
    import geopandas as gpd
    gdf = gpd.read_file(out)
    # ABS reports 2,473 SA2s in ASGS 2021 Edition 3
    assert 2400 <= len(gdf) <= 2500, f"expected ~2473 SA2s, got {len(gdf)}"
    assert "SA2_CODE21" in gdf.columns
    assert "SA2_NAME21" in gdf.columns
