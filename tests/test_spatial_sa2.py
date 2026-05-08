from src.spatial import load_sa2_access


def test_load_sa2_access_columns():
    df = load_sa2_access()
    expected = {
        "SA2_CODE21", "STE_NAME21", "PHN_CODE", "PHN_NAME", "Person",
        "gp_min", "gp_bulk_billing_min", "hospital_public_min", "emergency_min",
    }
    assert expected.issubset(df.columns)
    assert (df["gp_min"] >= 0).all()
    assert df["SA2_CODE21"].dtype == object


def test_load_sa2_access_row_count():
    df = load_sa2_access()
    assert 2400 <= len(df) <= 2500


def test_western_nsw_38_sa2s_over_45min_bulk_billing():
    """Regression on the 2026-05-08 spot-check."""
    df = load_sa2_access()
    wn = df[df["PHN_NAME"] == "Western NSW"]
    over = wn["gp_bulk_billing_min"] > 45
    assert over.sum() == 38, f"expected 38 SA2s, got {over.sum()}"
