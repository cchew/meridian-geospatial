import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import Point, Polygon


@pytest.fixture
def phn_boundary() -> gpd.GeoDataFrame:
    """Minimal synthetic PHN boundary for Western NSW."""
    poly = Polygon([(146, -31), (148, -31), (148, -33), (146, -33), (146, -31)])
    return gpd.GeoDataFrame(
        {"PHN_NAME": ["Western NSW"]},
        geometry=[poly],
        crs="EPSG:4326",
    )


@pytest.fixture
def localities(phn_boundary) -> gpd.GeoDataFrame:
    """Synthetic locality demand points inside the PHN boundary."""
    points = [
        Point(147.0, -32.0),  # town A — pop 5000
        Point(147.3, -32.2),  # town B — pop 1500 (below 2000 threshold)
        Point(147.6, -31.5),  # town C — pop 3000
    ]
    return gpd.GeoDataFrame(
        {
            "locality_name": ["Town A", "Town B", "Town C"],
            "UCL_NAME_2021": ["Town A", "Town B", "Town C"],
            "population": [5000, 1500, 3000],
        },
        geometry=points,
        crs="EPSG:4326",
    )


@pytest.fixture
def gp_locations() -> gpd.GeoDataFrame:
    """Synthetic GP practice locations."""
    points = [
        Point(147.05, -32.05),  # near Town A
    ]
    return gpd.GeoDataFrame(
        {"practice_name": ["Test Clinic"]},
        geometry=points,
        crs="EPSG:4326",
    )


@pytest.fixture
def dpa() -> gpd.GeoDataFrame:
    """Synthetic DPA areas."""
    poly = Polygon([(147.5, -31.3), (147.8, -31.3), (147.8, -31.7), (147.5, -31.7), (147.5, -31.3)])
    return gpd.GeoDataFrame(
        {"DPA": [1]},
        geometry=[poly],
        crs="EPSG:4326",
    )
