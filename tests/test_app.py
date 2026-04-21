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

@pytest.fixture
def mocked_pipeline():
    """Patch all external dependencies so AppTest runs without real data or APIs."""
    with (
        patch("src.security.verify_checksums"),
        patch("src.spatial.load_all_data", return_value=(
            _phn(), _localities(), _gp_locations(), _dpa()
        )),
        patch("src.spatial.build_spatial_context", return_value=_spatial_context()),
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
    assert at.session_state["results"]["total_pop"] == 10000  # 5000+3000+2000


def test_switching_modes_clears_results(mocked_pipeline):
    at = AppTest.from_file(APP_PATH, default_timeout=TIMEOUT)
    at.run()
    at.text_area[0].set_value("Which towns lack GP coverage?").run()
    analyse_btn = next(b for b in at.button if b.label == "Analyse")
    analyse_btn.click().run()
    assert "results" in at.session_state
    at.radio[0].set_value("prescriptive").run()
    assert "results" not in at.session_state
