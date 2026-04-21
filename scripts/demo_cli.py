#!/usr/bin/env python3
"""
CLI demo — verifies all three queries work end-to-end before the UI is built.
Usage: python scripts/demo_cli.py
"""
from dotenv import load_dotenv
load_dotenv()

from src.models import QueryParams
from src.spatial import load_all_data, build_spatial_context
from src.routing import get_travel_time_matrix
from src.optimiser import solve_mclp, compute_coverage

def run_diagnostic():
    print("\n=== Query 1: Diagnostic ===")
    params = QueryParams(mode="diagnostic", region="Western NSW",
                         facility_type="gp", threshold_min=45, pop_min=500)
    phn, localities, gp_locations, dpa = load_all_data()
    ctx = build_spatial_context(params, phn, localities, gp_locations, dpa)
    cm = get_travel_time_matrix(ctx.demand_points, ctx.existing_facilities, params.threshold_min)
    facility_ids = ctx.existing_facilities["facility_id"].tolist()
    covered, pct = compute_coverage(ctx.demand_points, facility_ids, cm.matrix, params.threshold_min)
    total = int(ctx.demand_points["population"].sum())
    print(f"  Population >={params.pop_min}: {total:,}")
    print(f"  Covered within 45 min: {covered:,} ({pct}%)")
    uncovered = ctx.demand_points[ctx.demand_points.apply(
        lambda row: cm.matrix.loc[row["demand_id"], facility_ids].min() > 45
        if row["demand_id"] in cm.matrix.index else True, axis=1
    )]["UCL_NAME_2021"].tolist()
    print(f"  Uncovered towns: {uncovered[:10]}")

def run_prescriptive_k6():
    print("\n=== Query 2: Prescriptive k=6 (validate Ochre) ===")
    params = QueryParams(mode="prescriptive", region="Western NSW",
                         facility_type="gp", threshold_min=45, k=6, pop_min=500)
    phn, localities, gp_locations, dpa = load_all_data()
    ctx = build_spatial_context(params, phn, localities, gp_locations, dpa)
    import geopandas as gpd, pandas as pd
    all_facilities = gpd.GeoDataFrame(
        pd.concat([ctx.existing_facilities, ctx.candidates], ignore_index=True),
        crs=ctx.existing_facilities.crs,
    )
    cm = get_travel_time_matrix(ctx.demand_points, all_facilities, params.threshold_min)
    result = solve_mclp(ctx.demand_points, ctx.candidates, ctx.existing_facilities, cm, k=6, threshold_min=45)
    print(f"  Proposed sites: {result.selected_sites['UCL_NAME_2021'].tolist()}")
    print(f"  Coverage before: {result.coverage_pct_before}%")
    print(f"  Coverage after:  {result.coverage_pct_after}%")

def run_prescriptive_k2():
    print("\n=== Query 3: Prescriptive k=2 (next 2 after Ochre) ===")
    # Ochre clinics are already included in gp_locations.gpkg (NHSD Nov 2025 snapshot)
    params = QueryParams(mode="prescriptive", region="Western NSW",
                         facility_type="gp", threshold_min=45, k=2, pop_min=500)
    phn, localities, gp_locations, dpa = load_all_data()
    ctx = build_spatial_context(params, phn, localities, gp_locations, dpa)
    import geopandas as gpd, pandas as pd
    all_facilities = gpd.GeoDataFrame(
        pd.concat([ctx.existing_facilities, ctx.candidates], ignore_index=True),
        crs=ctx.existing_facilities.crs,
    )
    cm = get_travel_time_matrix(ctx.demand_points, all_facilities, params.threshold_min)
    result = solve_mclp(ctx.demand_points, ctx.candidates, ctx.existing_facilities, cm, k=2, threshold_min=45)
    print(f"  Proposed next 2: {result.selected_sites['UCL_NAME_2021'].tolist()}")
    print(f"  Coverage before: {result.coverage_pct_before}%")
    print(f"  Coverage after:  {result.coverage_pct_after}%")

if __name__ == "__main__":
    run_diagnostic()
    run_prescriptive_k6()
    run_prescriptive_k2()
    print("\n=== Weekend 1 complete. All queries working. ===")
