"""AlphaEarth land-cover caveat: reads the precomputed cluster cache and
formats a deterministic caveat string for Meridian's Mode 2 output.

See docs/superpowers/specs/2026-09-20-meridian-alphaearth-land-cover-design.md.
The precompute step that writes the cache this reads is
scripts/precompute_land_cover_clusters.py.
"""
from __future__ import annotations
from pathlib import Path

import geopandas as gpd
import pandas as pd

DATA_DIR = Path("data")
LABELS_PATH = DATA_DIR / "land_cover_clusters_western_nsw.parquet"


def load_land_cover_labels(path: Path = LABELS_PATH) -> dict[str, str]:
    """SA2_CODE21 -> 'built-up' | 'non-built-up', from the precomputed cache.
    Empty dict if the cache file doesn't exist -- never raises."""
    if not path.exists():
        return {}
    df = pd.read_parquet(path)
    return dict(zip(df["SA2_CODE21"].astype(str), df["land_cover_label"]))
