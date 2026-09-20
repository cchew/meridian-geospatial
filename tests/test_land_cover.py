from __future__ import annotations

import pandas as pd

from src.land_cover import load_land_cover_labels


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
