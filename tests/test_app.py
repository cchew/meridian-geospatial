from __future__ import annotations

import geopandas as gpd
import pandas as pd
import plotly.graph_objects as go
import pytest
from shapely.geometry import Point, Polygon
from unittest.mock import patch, MagicMock
from streamlit.testing.v1 import AppTest

from src.models import (
    QueryParams,
    SpatialContext,
    CoverageMatrix,
    NarrativeContext,
)

# Synthetic SA2 population for mock: 3 SA2s totalling 10000
_SA2_TOTAL_POP = 10000

APP_PATH = "app.py"
TIMEOUT = 30


# ── Synthetic data helpers ────────────────────────────────────────────────────

def _phn() -> gpd.GeoDataFrame:
    poly = Polygon([(146, -31), (148, -31), (148, -33), (146, -33), (146, -31)])
    return gpd.GeoDataFrame({"PHN_NAME": ["Western NSW"]}, geometry=[poly], crs="EPSG:4326")


def _localities() -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(
        {"UCL_NAME_2021": ["Cobar", "Bourke", "Walgett"], "population": [5000, 3000, 2000]},
        geometry=[Point(145.8, -31.5), Point(145.9, -30.1), Point(148.1, -30.0)],
        crs="EPSG:4326",
    )


def _gp_locations() -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(
        {"practice_name": ["Cobar Medical"], "nhsd_service_type": ["General practice service"]},
        geometry=[Point(145.8, -31.5)],
        crs="EPSG:4326",
    )


def _dpa() -> gpd.GeoDataFrame:
    poly = Polygon([(145, -29), (149, -29), (149, -33), (145, -33), (145, -29)])
    return gpd.GeoDataFrame({"DPA": [1]}, geometry=[poly], crs="EPSG:4326")


def _spatial_context() -> SpatialContext:
    demand = gpd.GeoDataFrame(
        {
            "locality_name": ["Cobar", "Bourke", "Walgett"],
            "UCL_NAME_2021": ["Cobar", "Bourke", "Walgett"],
            "population": [5000, 3000, 2000],
            "demand_id": ["0", "1", "2"],
        },
        geometry=[Point(145.8, -31.5), Point(145.9, -30.1), Point(148.1, -30.0)],
        crs="EPSG:4326",
    )
    facilities = gpd.GeoDataFrame(
        {"practice_name": ["Cobar Medical"], "facility_id": ["0"]},
        geometry=[Point(145.8, -31.5)],
        crs="EPSG:4326",
    )
    candidates = gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")
    return SpatialContext(demand_points=demand, existing_facilities=facilities, candidates=candidates)


def _coverage_matrix() -> CoverageMatrix:
    # Cobar (0) covered at 10 min, Bourke (1) and Walgett (2) uncovered at 999 min
    matrix = pd.DataFrame(
        {"0": [10.0, 999.0, 999.0]},
        index=["0", "1", "2"],
    )
    return CoverageMatrix(matrix=matrix, demand_ids=["0", "1", "2"], facility_ids=["0"])


# ── Fixtures ─────────────────────────────────────────────────────────────────

def _sa2_summary():
    return {
        "total_population": _SA2_TOTAL_POP,
        "covered_population": 5000,
        "coverage_pct": 50.0,
        "uncovered_sa2_count": 2,
        "median_travel_min": 30.0,
    }


def _sa2_demand_with_coverage() -> gpd.GeoDataFrame:
    demand = _spatial_context().demand_points.copy()
    demand["covered"] = [True, False, False]
    demand["gp_min"] = [10.0, 60.0, 90.0]
    demand["gp_bulk_billing_min"] = [10.0, 60.0, 90.0]
    return demand


@pytest.fixture
def mocked_pipeline():
    """Patch all external dependencies so AppTest runs without real data or APIs."""
    with (
        patch("src.security.verify_checksums"),
        patch("src.spatial.load_all_data", return_value=(
            _phn(), _localities(), _gp_locations(), _dpa()
        )),
        patch("src.spatial.load_sa2_access", return_value=pd.DataFrame()),
        patch("src.spatial.load_sa2_geometries", return_value=gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")),
        patch("src.spatial.load_facility_layers", return_value=(
            _gp_locations(), _dpa(), _phn()
        )),
        patch("src.spatial.build_spatial_context", return_value=_spatial_context()),
        patch("src.spatial.build_spatial_context_sa2", return_value=_spatial_context()),
        patch("src.spatial.build_spatial_context_sa2_prescriptive", return_value=_spatial_context()),
        patch("src.optimiser.diagnose_sa2_coverage", return_value=(
            _sa2_demand_with_coverage(), _sa2_summary()
        )),
        patch("src.routing.get_travel_time_matrix", return_value=_coverage_matrix()),
        patch("src.nlp.parse_query", return_value=QueryParams(
            mode="diagnostic", region="Western NSW", facility_type="gp",
            threshold_min=45, pop_min=500,
        )),
        patch("src.nlp.generate_narrative", return_value=(
            "Currently 50% of the population in Western NSW is within 45 minutes of a GP. "
            "Towns including Bourke and Walgett lack adequate coverage."
        )),
        patch("src.visualisation.build_diagnostic_map", return_value=go.Figure()),
        patch("src.visualisation.build_prescriptive_map", return_value=go.Figure()),
    ):
        yield


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_app_loads_without_error(mocked_pipeline):
    at = AppTest.from_file(APP_PATH, default_timeout=TIMEOUT)
    at.run()
    assert not at.exception


def test_mode1_shows_one_suggested_query(mocked_pipeline):
    at = AppTest.from_file(APP_PATH, default_timeout=TIMEOUT)
    at.run()
    # Default mode is diagnostic — should show exactly 1 suggested query button
    query_buttons = [b for b in at.button if "Western NSW" in b.label]
    assert len(query_buttons) == 1
    assert "500 people" in query_buttons[0].label


def test_mode2_shows_two_suggested_queries(mocked_pipeline):
    at = AppTest.from_file(APP_PATH, default_timeout=TIMEOUT)
    at.run()
    at.radio[0].set_value("prescriptive").run()
    query_buttons = [b for b in at.button if "Western NSW" in b.label]
    assert len(query_buttons) == 2


def test_clicking_suggested_query_populates_textarea(mocked_pipeline):
    at = AppTest.from_file(APP_PATH, default_timeout=TIMEOUT)
    at.run()
    query_buttons = [b for b in at.button if "Western NSW" in b.label]
    query_buttons[0].click().run()
    assert "500 people" in at.text_area[0].value


def test_empty_input_shows_warning(mocked_pipeline):
    at = AppTest.from_file(APP_PATH, default_timeout=TIMEOUT)
    at.run()
    analyse_btn = next(b for b in at.button if b.label == "Analyse")
    analyse_btn.click().run()
    assert len(at.warning) > 0


def test_diagnostic_analysis_renders_results(mocked_pipeline):
    at = AppTest.from_file(APP_PATH, default_timeout=TIMEOUT)
    at.run()
    at.text_area[0].set_value(
        "Which towns in Western NSW with more than 500 people are more than 45 minutes from the nearest bulk-billing GP?"
    ).run()
    analyse_btn = next(b for b in at.button if b.label == "Analyse")
    analyse_btn.click().run()
    assert "results" in at.session_state
    assert at.session_state["results"]["narrative"] != ""
    assert at.session_state["results"]["total_pop"] == _SA2_TOTAL_POP  # from mocked SA2 summary


def test_switching_modes_clears_results(mocked_pipeline):
    at = AppTest.from_file(APP_PATH, default_timeout=TIMEOUT)
    at.run()
    at.text_area[0].set_value("Which towns lack GP coverage?").run()
    analyse_btn = next(b for b in at.button if b.label == "Analyse")
    analyse_btn.click().run()
    assert "results" in at.session_state
    at.radio[0].set_value("prescriptive").run()
    assert "results" not in at.session_state


def test_mode1_western_nsw_no_routing_calls(monkeypatch):
    """Mode 1 must not invoke ArcGIS or ORS."""
    from unittest.mock import MagicMock
    import src.routing as routing
    spy = MagicMock(side_effect=AssertionError("Mode 1 should not call routing"))
    monkeypatch.setattr(routing, "get_travel_time_matrix", spy)

    from src.spatial import load_sa2_access, load_sa2_geometries, build_spatial_context_sa2
    from src.optimiser import diagnose_sa2_coverage
    from src.models import QueryParams

    params = QueryParams(mode="diagnostic", region="Western NSW",
                          facility_type="gp_bulk_billing", threshold_min=45)
    ctx = build_spatial_context_sa2(params, load_sa2_access(), load_sa2_geometries())
    demand_with_cov, summary = diagnose_sa2_coverage(
        ctx.demand_points, params.threshold_min, params.facility_type
    )
    assert summary["uncovered_sa2_count"] == 10  # Western NSW PHN regression anchor
    spy.assert_not_called()


def test_diagnose_sa2_coverage_rejects_unknown_facility_type():
    """Validate that unknown facility_type raises ValueError."""
    from src.optimiser import diagnose_sa2_coverage
    demand = gpd.GeoDataFrame(
        {"gp_min": [10.0], "gp_bulk_billing_min": [20.0], "population": [1000]},
        geometry=[Point(0, 0)],
        crs="EPSG:4326",
    )
    with pytest.raises(ValueError, match="unknown facility_type"):
        diagnose_sa2_coverage(demand, threshold_min=30, facility_type="bogus")


def test_mode2_western_nsw_k2_returns_two_sites(monkeypatch):
    """Mode 2 SA2 wiring: build_spatial_context_sa2_prescriptive + solve_mclp
    returns 2 selected sites. Routing is monkeypatched to avoid ArcGIS API cost."""
    from src.models import QueryParams, CoverageMatrix
    from src.spatial import (
        load_sa2_access,
        load_sa2_geometries,
        load_facility_layers,
        build_spatial_context_sa2_prescriptive,
    )
    from src.optimiser import solve_mclp
    import src.routing as routing

    access = load_sa2_access()
    sa2 = load_sa2_geometries()
    gp, dpa, phn = load_facility_layers()
    params = QueryParams(
        mode="prescriptive",
        region="Western NSW",
        facility_type="gp",
        threshold_min=45,
        k=2,
        pop_min=500,
    )
    ctx = build_spatial_context_sa2_prescriptive(params, access, sa2, gp, dpa, phn)

    all_facilities = gpd.GeoDataFrame(
        pd.concat([ctx.existing_facilities, ctx.candidates], ignore_index=True),
        crs=ctx.existing_facilities.crs,
    )

    demand_ids = ctx.demand_points["demand_id"].astype(str).tolist()
    # Preserve original facility_id values (existing: '0','1',...; candidates: 'c_0','c_1',...)
    facility_ids = all_facilities["facility_id"].tolist()

    # Build a synthetic travel-time matrix: first 2 candidates cover all demand
    # within threshold; all others are out of range. Existing facilities are all
    # out of range so before-coverage is zero and solve_mclp must select 2 sites.
    import numpy as np

    n_demand = len(demand_ids)
    n_facilities = len(facility_ids)
    matrix_data = np.full((n_demand, n_facilities), 999.0)

    candidate_ids = ctx.candidates["facility_id"].tolist() if "facility_id" in ctx.candidates.columns else []
    # Cover all demand via first 2 candidates
    for col_idx, fid in enumerate(facility_ids):
        if fid in candidate_ids[:2]:
            matrix_data[:, col_idx] = 10.0  # well within 45-min threshold

    synthetic_matrix = pd.DataFrame(matrix_data, index=demand_ids, columns=facility_ids)
    synthetic_cm = CoverageMatrix(
        matrix=synthetic_matrix,
        demand_ids=demand_ids,
        facility_ids=facility_ids,
    )

    monkeypatch.setattr(routing, "get_travel_time_matrix", lambda *a, **kw: synthetic_cm)

    cm = routing.get_travel_time_matrix(ctx.demand_points, all_facilities, params.threshold_min)
    result = solve_mclp(
        ctx.demand_points,
        ctx.candidates,
        ctx.existing_facilities,
        cm,
        k=2,
        threshold_min=45,
    )
    assert len(result.selected_sites) == 2
    assert result.coverage_pct_after >= result.coverage_pct_before
