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

    Evaluated per selected site, independently of any other site's coverage
    -- partial cache coverage is never silently treated as full coverage:
      - selected_sites is empty -> "" (nothing was proposed, nothing to say)
      - a site's SA2 code is not a key in `labels` -> counted as uncovered;
        if any sites are uncovered, a short note says so, so silence is
        never misread as "checked, all clear" (this also covers the case
        where none of the codes are in `labels` -- the whole region)
      - a site's SA2 code is a key in `labels` and labelled "non-built-up"
        -> counted as flagged; if any sites are flagged, the
        field-verification caveat names them
      - both notes can appear together; if neither applies -> "" (checked,
        clear)
    """
    if len(selected_sites) == 0:
        return ""

    flagged_names = [
        row["locality_name"]
        for _, row in selected_sites.iterrows()
        if str(row["SA2_CODE21"]) in labels
        and labels[str(row["SA2_CODE21"])] == "non-built-up"
    ]
    uncovered_count = sum(
        1 for c in selected_sites["SA2_CODE21"].astype(str) if c not in labels
    )

    if not flagged_names and not uncovered_count:
        return ""

    parts = []
    if flagged_names:
        verb = "has" if len(flagged_names) == 1 else "have"
        parts.append(
            f"Note: {len(flagged_names)} of the proposed sites "
            f"({', '.join(flagged_names)}) {verb} a satellite land-cover profile "
            f"more consistent with rural/vegetated area than township; "
            f"recommend field verification before commissioning."
        )
    if uncovered_count:
        parts.append(
            f"Note: land-cover verification is not yet available for "
            f"{uncovered_count} of the proposed sites (satellite embedding "
            f"not yet computed for their area)."
        )
    return " ".join(parts)
