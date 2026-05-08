from src.spatial import load_sa2_access


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
