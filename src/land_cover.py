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


def format_land_cover_caveat(selected_sites: gpd.GeoDataFrame, labels: dict[str, str]) -> str:
    """Deterministic caveat text, computed independently of and appended
    AFTER generate_narrative()'s LLM call -- never passed through it. A fact
    given to that free-form prompt is not guaranteed to survive verbatim
    into its output, which is unacceptable for a safety-relevant caveat.

    Three states:
      - selected_sites is empty -> "" (nothing was proposed, nothing to say)
      - none of selected_sites' SA2 codes are keys in `labels`
        -> region not yet covered by the precompute step; returns a short
           note, so silence is never misread as "checked, all clear"
      - codes present in `labels`, none "non-built-up" -> "" (checked, clear)
      - one or more "non-built-up" -> the field-verification caveat
    """
    if len(selected_sites) == 0:
        return ""

    codes = selected_sites["SA2_CODE21"].astype(str).tolist()
    covered_codes = [c for c in codes if c in labels]

    if not covered_codes:
        return (
            "Note: land-cover verification is not yet available for this "
            "region (satellite embedding not yet computed here)."
        )

    flagged_names = [
        row["locality_name"]
        for _, row in selected_sites.iterrows()
        if str(row["SA2_CODE21"]) in labels
        and labels[str(row["SA2_CODE21"])] == "non-built-up"
    ]

    if not flagged_names:
        return ""

    return (
        f"Note: {len(flagged_names)} of the proposed sites "
        f"({', '.join(flagged_names)}) have a satellite land-cover profile "
        f"more consistent with rural/vegetated area than township; "
        f"recommend field verification before commissioning."
    )
