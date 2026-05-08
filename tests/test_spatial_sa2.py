from src.spatial import load_sa2_access, load_sa2_geometries, list_phns


def test_load_sa2_access_columns():
    df = load_sa2_access()
    expected = {
        "SA2_CODE21", "STE_NAME21", "PHN_CODE", "PHN_NAME", "Person",
        "gp_min", "gp_bulk_billing_min", "hospital_public_min", "emergency_min",
    }
    assert expected.issubset(df.columns)
    # Some SA2s have null durations (special categories or no road access);
    # non-null values must be non-negative.
    assert (df["gp_min"].dropna() >= 0).all()
    assert df["SA2_CODE21"].dtype == object


def test_load_sa2_access_row_count():
    df = load_sa2_access()
    # Some SA2s span multiple PHNs in the concordance (~45 do), so the merged
    # row count can exceed the 2,462 SA2 total.
    assert 2400 <= len(df) <= 2600


def test_nsw_state_has_38_sa2s_over_45min_bulk_billing():
    """Regression on the 2026-05-08 cross-validation snapshot at NSW state level."""
    df = load_sa2_access()
    nsw = df[df["STE_NAME21"] == "New South Wales"].drop_duplicates(subset=["SA2_CODE21"])
    over = nsw["gp_bulk_billing_min"] > 45
    assert over.sum() == 38, f"expected 38 NSW SA2s, got {over.sum()}"


def test_western_nsw_phn_subset_consistent():
    """Western NSW PHN bulk-billing >45min count — pinned regression anchor."""
    df = load_sa2_access()
    wn = df[df["PHN_NAME"] == "Western NSW"]
    over_count = (wn["gp_bulk_billing_min"] > 45).sum()
    assert over_count == 10, f"expected 10 Western NSW SA2s, got {over_count}"


def test_load_sa2_geometries_national():
    sa2 = load_sa2_geometries()
    assert 2400 <= len(sa2) <= 2500
    assert sa2.crs.to_epsg() == 4326
    assert "SA2_CODE21" in sa2.columns


def test_list_phns_returns_31_sorted():
    df = load_sa2_access()
    phns = list_phns(df)
    assert len(phns) == 31
    assert phns == sorted(phns)
    assert "Western NSW" in phns


import pytest
from src.models import QueryParams
from src.spatial import build_spatial_context_sa2


@pytest.fixture(scope="module")
def access():
    return load_sa2_access()


@pytest.fixture(scope="module")
def sa2():
    return load_sa2_geometries()


def test_diagnostic_mode_western_nsw_returns_demand(access, sa2):
    params = QueryParams(mode="diagnostic", region="Western NSW",
                          facility_type="gp", threshold_min=45)
    ctx = build_spatial_context_sa2(params, access, sa2)
    # Western NSW PHN: ~50 SA2s
    assert 30 <= len(ctx.demand_points) <= 80
    assert "gp_min" in ctx.demand_points.columns
    assert "population" in ctx.demand_points.columns
    assert ctx.demand_points["population"].sum() > 100_000
