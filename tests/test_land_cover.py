from __future__ import annotations

import pandas as pd
import geopandas as gpd
from shapely.geometry import Point

from src.land_cover import load_land_cover_labels, format_land_cover_caveat


def test_load_land_cover_labels_missing_file_returns_empty(tmp_path):
    missing = tmp_path / "does_not_exist.parquet"
    assert load_land_cover_labels(path=missing) == {}


def test_load_land_cover_labels_reads_parquet(tmp_path):
    cache_path = tmp_path / "labels.parquet"
    pd.DataFrame({
        "SA2_CODE21": ["101021007", "101021008"],
        "cluster_id": [0, 1],
        "land_cover_label": ["built-up", "non-built-up"],
    }).to_parquet(cache_path)

    labels = load_land_cover_labels(path=cache_path)

    assert labels == {"101021007": "built-up", "101021008": "non-built-up"}


def _sites(codes: list[str], names: list[str]) -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(
        {"SA2_CODE21": codes, "locality_name": names},
        geometry=[Point(0, 0)] * len(codes),
        crs="EPSG:4326",
    )


def test_caveat_empty_when_no_selected_sites():
    sites = _sites([], [])
    assert format_land_cover_caveat(sites, {"101021007": "built-up"}) == ""


def test_caveat_region_not_covered():
    sites = _sites(["999999999"], ["Nowhereville"])
    text = format_land_cover_caveat(sites, {"101021007": "built-up"})
    assert "not yet available" in text


def test_caveat_empty_when_all_built_up():
    sites = _sites(["101021007", "101021008"], ["Town A", "Town B"])
    labels = {"101021007": "built-up", "101021008": "built-up"}
    assert format_land_cover_caveat(sites, labels) == ""


def test_caveat_names_flagged_sites_only():
    sites = _sites(["101021007", "101021008"], ["Town A", "Rural Block"])
    labels = {"101021007": "built-up", "101021008": "non-built-up"}
    text = format_land_cover_caveat(sites, labels)
    assert "Rural Block" in text
    assert "field verification" in text
    assert "Town A" not in text


def test_caveat_partial_coverage_flags_and_notes_uncovered():
    sites = _sites(
        ["101021008", "999999999"], ["Rural Block", "Nowhereville"]
    )
    labels = {"101021008": "non-built-up"}
    text = format_land_cover_caveat(sites, labels)
    assert "Rural Block" in text
    assert "field verification" in text
    assert "1" in text
    assert "not yet available" in text
