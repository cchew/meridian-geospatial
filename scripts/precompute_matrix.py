#!/usr/bin/env python3
"""Pre-compute Mode 2 candidate × demand travel matrices for all 31 PHNs."""
from pathlib import Path
import argparse
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

import pandas as pd
import geopandas as gpd

from src.models import QueryParams
from src.spatial import (
    load_sa2_access, load_sa2_geometries, load_facility_layers,
    build_spatial_context_sa2_prescriptive, list_phns,
)
from src.routing import get_travel_time_matrix


# Mode 2 canonical demo queries — one per PHN
def queries_for(phn: str) -> list[QueryParams]:
    return [
        QueryParams(mode="prescriptive", region=phn, facility_type="gp",
                    threshold_min=45, k=6, pop_min=500),
        QueryParams(mode="prescriptive", region=phn, facility_type="gp",
                    threshold_min=45, k=2, pop_min=500),
    ]


def main(only_phn: str | None = None) -> None:
    print("Loading spatial data...")
    access = load_sa2_access()
    sa2 = load_sa2_geometries()
    gp, dpa, phn_layer = load_facility_layers()
    phns = list_phns(access)

    target_phns = [only_phn] if only_phn else phns

    if only_phn and only_phn not in phns:
        print(f"ERROR: PHN '{only_phn}' not found. Available PHNs:")
        for p in phns:
            print(f"  {p}")
        sys.exit(1)

    print(f"Target: {len(target_phns)} PHN(s)\n")

    for i, phn in enumerate(target_phns, 1):
        print(f"[{i}/{len(target_phns)}] {phn}")
        for params in queries_for(phn):
            try:
                ctx = build_spatial_context_sa2_prescriptive(
                    params, access, sa2, gp, dpa, phn_layer
                )
                all_facilities = gpd.GeoDataFrame(
                    pd.concat([ctx.existing_facilities, ctx.candidates], ignore_index=True),
                    crs=ctx.existing_facilities.crs,
                )
                cm = get_travel_time_matrix(
                    ctx.demand_points, all_facilities, params.threshold_min
                )
                print(f"  k={params.k}: matrix {cm.matrix.shape} cached")
            except Exception as e:
                print(f"  k={params.k}: SKIPPED ({e})")

    print("\nDone.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Pre-compute Mode 2 travel matrices for PHNs."
    )
    parser.add_argument("--phn", default=None, help="Run only this PHN (smoke test)")
    args = parser.parse_args()
    main(args.phn)
