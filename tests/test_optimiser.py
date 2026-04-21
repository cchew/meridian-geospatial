import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import Point

from src.models import CoverageMatrix
from src.optimiser import solve_mclp, compute_coverage


@pytest.fixture
def small_context():
    """3 demand points, 4 candidates, 1 existing facility."""
    demand = gpd.GeoDataFrame(
        {"demand_id": ["d0", "d1", "d2"], "population": [5000, 3000, 2000]},
        geometry=[Point(0, 0), Point(1, 0), Point(2, 0)],
        crs="EPSG:4326",
    )
    candidates = gpd.GeoDataFrame(
        {"candidate_id": ["c0", "c1", "c2", "c3"], "facility_id": ["c0", "c1", "c2", "c3"]},
        geometry=[Point(0.1, 0), Point(1.1, 0), Point(1.9, 0), Point(3.0, 0)],
        crs="EPSG:4326",
    )
    existing = gpd.GeoDataFrame(
        {"facility_id": ["f0"]},
        geometry=[Point(5.0, 0)],  # far away — covers nothing within threshold
        crs="EPSG:4326",
    )
    # travel time matrix: demand x (existing + candidates)
    all_facility_ids = ["f0", "c0", "c1", "c2", "c3"]
    matrix_data = {
        "f0": [999, 999, 999],
        "c0": [5, 60, 90],   # c0 covers d0 within 45 min
        "c1": [50, 5, 50],   # c1 covers d1 within 45 min
        "c2": [90, 50, 5],   # c2 covers d2 within 45 min
        "c3": [999, 999, 999],
    }
    matrix = pd.DataFrame(matrix_data, index=["d0", "d1", "d2"])
    cm = CoverageMatrix(matrix=matrix, demand_ids=["d0", "d1", "d2"], facility_ids=all_facility_ids)
    return demand, candidates, existing, cm


def test_mclp_selects_best_k_sites(small_context):
    demand, candidates, existing, cm = small_context
    result = solve_mclp(
        demand=demand,
        candidates=candidates,
        existing_facilities=existing,
        coverage_matrix=cm,
        k=2,
        threshold_min=45,
    )
    # With k=2, optimal is c0 (covers d0: pop 5000) + c1 (covers d1: pop 3000)
    # Total covered: 8000 out of 10000
    assert len(result.selected_sites) == 2
    assert result.covered_after >= 8000


def test_mclp_before_coverage_uses_existing_only(small_context):
    demand, candidates, existing, cm = small_context
    result = solve_mclp(
        demand=demand,
        candidates=candidates,
        existing_facilities=existing,
        coverage_matrix=cm,
        k=1,
        threshold_min=45,
    )
    # Existing facility f0 covers nothing (travel time 999 for all)
    assert result.covered_before == 0
    assert result.coverage_pct_before == 0.0


def test_mclp_coverage_pct_correct(small_context):
    demand, candidates, existing, cm = small_context
    result = solve_mclp(
        demand=demand,
        candidates=candidates,
        existing_facilities=existing,
        coverage_matrix=cm,
        k=3,
        threshold_min=45,
    )
    # k=3 should cover all 3 demand points (c0+c1+c2)
    assert result.covered_after == 10000
    assert abs(result.coverage_pct_after - 100.0) < 0.01
