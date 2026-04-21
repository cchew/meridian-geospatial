import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from src.models import CoverageMatrix, RoutingError
from src.routing import (
    compute_cache_key,
    get_travel_time_matrix,
    _parse_od_response,
)


@pytest.fixture
def sample_od_response():
    return {
        "odLines": {
            "features": [
                {"attributes": {"OriginOID": 0, "DestinationOID": 0, "Total_Time": 12.5}},
                {"attributes": {"OriginOID": 0, "DestinationOID": 1, "Total_Time": 55.0}},
                {"attributes": {"OriginOID": 1, "DestinationOID": 0, "Total_Time": 45.0}},
                {"attributes": {"OriginOID": 1, "DestinationOID": 1, "Total_Time": 8.0}},
            ]
        }
    }


def test_parse_od_response(sample_od_response):
    demand_ids = ["d0", "d1"]
    facility_ids = ["f0", "f1"]
    matrix = _parse_od_response(sample_od_response, demand_ids, facility_ids)
    assert isinstance(matrix, pd.DataFrame)
    assert matrix.loc["d0", "f0"] == 12.5
    assert matrix.loc["d1", "f1"] == 8.0


def test_cache_key_is_deterministic(localities, gp_locations):
    key1 = compute_cache_key(localities, gp_locations, threshold_min=45)
    key2 = compute_cache_key(localities, gp_locations, threshold_min=45)
    assert key1 == key2


def test_cache_key_differs_by_threshold(localities, gp_locations):
    key1 = compute_cache_key(localities, gp_locations, threshold_min=30)
    key2 = compute_cache_key(localities, gp_locations, threshold_min=45)
    assert key1 != key2


def test_returns_cached_matrix_without_api_call(localities, gp_locations):
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_dir = Path(tmpdir)

        # Pre-populate the cache
        cache_key = compute_cache_key(localities, gp_locations, threshold_min=45)
        cached_df = pd.DataFrame({"f0": [10.0]}, index=["d0"])
        cached_df.to_parquet(cache_dir / f"{cache_key}.parquet")

        with patch("src.routing._call_arcgis_od_matrix") as mock_api:
            result = get_travel_time_matrix(
                localities, gp_locations, threshold_min=45, cache_dir=cache_dir
            )
            mock_api.assert_not_called()

        assert result.matrix.loc["d0", "f0"] == 10.0


def test_raises_routing_error_on_api_failure(localities, gp_locations, monkeypatch):
    monkeypatch.setenv("ROUTING_PROVIDER", "arcgis")
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_dir = Path(tmpdir)
        with patch("src.routing._call_arcgis_od_matrix") as mock_api:
            mock_api.side_effect = RoutingError("ArcGIS timeout")
            with pytest.raises(RoutingError):
                get_travel_time_matrix(
                    localities, gp_locations, threshold_min=45, cache_dir=cache_dir
                )
