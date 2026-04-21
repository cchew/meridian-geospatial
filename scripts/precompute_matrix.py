#!/usr/bin/env python3
"""
Pre-compute and cache ArcGIS travel time matrices for all three demo queries.
Run once before any demo: python scripts/precompute_matrix.py

Requires: .env with ARCGIS_CLIENT_ID and ARCGIS_CLIENT_SECRET
          data/ directory populated (run download_data.py first)
"""
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from src.models import QueryParams
from src.spatial import load_all_data, build_spatial_context
from src.routing import get_travel_time_matrix

DEMO_QUERIES = [
    QueryParams(mode="diagnostic", region="Western NSW", facility_type="gp",
                threshold_min=45, pop_min=500),
    QueryParams(mode="prescriptive", region="Western NSW", facility_type="gp",
                threshold_min=45, k=6, pop_min=500),
    QueryParams(mode="prescriptive", region="Western NSW", facility_type="gp",
                threshold_min=45, k=2, pop_min=500),
]

def main() -> None:
    print("Loading spatial data...")
    phn, localities, gp_locations, dpa = load_all_data()

    for i, params in enumerate(DEMO_QUERIES, 1):
        print(f"\nQuery {i}: {params.mode} k={params.k} threshold={params.threshold_min}min")
        ctx = build_spatial_context(params, phn, localities, gp_locations, dpa)

        facilities = ctx.existing_facilities
        if params.mode == "prescriptive":
            import pandas as pd
            import geopandas as gpd
            all_facilities = gpd.GeoDataFrame(
                pd.concat([ctx.existing_facilities, ctx.candidates], ignore_index=True),
                crs=ctx.existing_facilities.crs,
            )
            facilities = all_facilities

        print(f"  Demand points: {len(ctx.demand_points)}, Facilities: {len(facilities)}")
        print("  Computing travel time matrix (may take 1-2 min)...")
        cm = get_travel_time_matrix(ctx.demand_points, facilities, params.threshold_min)
        print(f"  Matrix shape: {cm.matrix.shape} — cached.")

    print("\nAll matrices pre-computed. Demo is ready.")

if __name__ == "__main__":
    main()
