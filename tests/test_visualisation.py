import geopandas as gpd
import plotly.graph_objects as go
import pytest
from shapely.geometry import Point

from src.visualisation import build_diagnostic_map, build_prescriptive_map


@pytest.fixture
def demand_with_coverage(localities):
    localities = localities.copy()
    localities["demand_id"] = ["d0", "d1", "d2"]
    localities["covered"] = [True, False, True]
    return localities


def test_diagnostic_map_returns_plotly_figure(demand_with_coverage, gp_locations):
    fig = build_diagnostic_map(demand_with_coverage, gp_locations, threshold_min=45)
    assert isinstance(fig, go.Figure)


def test_prescriptive_map_returns_plotly_figure(demand_with_coverage, gp_locations):
    proposed = gpd.GeoDataFrame(
        {"locality_name": ["Town X"]},
        geometry=[Point(147.4, -31.8)],
        crs="EPSG:4326",
    )
    fig = build_prescriptive_map(demand_with_coverage, gp_locations, proposed, threshold_min=45)
    assert isinstance(fig, go.Figure)


def test_diagnostic_map_has_covered_and_uncovered_traces(demand_with_coverage, gp_locations):
    fig = build_diagnostic_map(demand_with_coverage, gp_locations, threshold_min=45)
    trace_names = [t.name for t in fig.data]
    assert "Covered" in trace_names
    assert "Uncovered" in trace_names


def test_prescriptive_map_has_proposed_clinic_trace(demand_with_coverage, gp_locations):
    proposed = gpd.GeoDataFrame(
        {"locality_name": ["Town X"]},
        geometry=[Point(147.4, -31.8)],
        crs="EPSG:4326",
    )
    fig = build_prescriptive_map(demand_with_coverage, gp_locations, proposed, threshold_min=45)
    trace_names = [t.name for t in fig.data]
    assert "Proposed clinic" in trace_names
