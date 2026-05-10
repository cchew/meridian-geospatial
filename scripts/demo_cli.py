#!/usr/bin/env python3
"""
CLI demo — verifies all three queries work end-to-end before the UI is used.
Usage: python scripts/demo_cli.py
"""
from dotenv import load_dotenv
load_dotenv()

import geopandas as gpd
import pandas as pd

from src.models import QueryParams
from src.spatial import (
    load_sa2_access, load_sa2_geometries, load_facility_layers,
    build_spatial_context_sa2, build_spatial_context_sa2_prescriptive,
)
from src.routing import get_travel_time_matrix
from src.optimiser import solve_mclp, diagnose_sa2_coverage


def run_diagnostic():
    print("\n=== Query 1: Diagnostic ===")
    params = QueryParams(mode="diagnostic", region="Western NSW",
                         facility_type="gp_bulk_billing", threshold_min=45, pop_min=500)
    access = load_sa2_access()
    sa2 = load_sa2_geometries()
    ctx = build_spatial_context_sa2(params, access, sa2)
    demand, summary = diagnose_sa2_coverage(ctx.demand_points, params.threshold_min, params.facility_type)
    print(f"  Population total: {summary['total_population']:,}")
    print(f"  Covered within 45 min: {summary['covered_population']:,} ({summary['coverage_pct']:.1f}%)")
    uncovered = demand[~demand["covered"]]["locality_name"].tolist()
    print(f"  Uncovered SA2s: {uncovered[:10]}")


def run_prescriptive_k6():
    print("\n=== Query 2: Prescriptive k=6 (validate Ochre) ===")
    params = QueryParams(mode="prescriptive", region="Western NSW",
                         facility_type="gp", threshold_min=45, k=6, pop_min=500)
    access = load_sa2_access()
    sa2 = load_sa2_geometries()
    gp, dpa, phn = load_facility_layers()
    ctx = build_spatial_context_sa2_prescriptive(params, access, sa2, gp, dpa, phn)
    all_facilities = gpd.GeoDataFrame(
        pd.concat([ctx.existing_facilities, ctx.candidates], ignore_index=True),
        crs=ctx.existing_facilities.crs,
    )
    cm = get_travel_time_matrix(ctx.demand_points, all_facilities, params.threshold_min)
    result = solve_mclp(ctx.demand_points, ctx.candidates, ctx.existing_facilities, cm, k=6, threshold_min=45)
    print(f"  Proposed sites: {result.selected_sites['locality_name'].tolist()}")
    print(f"  Coverage before: {result.coverage_pct_before:.1f}%")
    print(f"  Coverage after:  {result.coverage_pct_after:.1f}%")


def run_prescriptive_k2():
    print("\n=== Query 3: Prescriptive k=2 (next 2 after Ochre) ===")
    # Ochre clinics are already in gp_locations.geojson (NHSD Nov 2025 snapshot)
    params = QueryParams(mode="prescriptive", region="Western NSW",
                         facility_type="gp", threshold_min=45, k=2, pop_min=500)
    access = load_sa2_access()
    sa2 = load_sa2_geometries()
    gp, dpa, phn = load_facility_layers()
    ctx = build_spatial_context_sa2_prescriptive(params, access, sa2, gp, dpa, phn)
    all_facilities = gpd.GeoDataFrame(
        pd.concat([ctx.existing_facilities, ctx.candidates], ignore_index=True),
        crs=ctx.existing_facilities.crs,
    )
    cm = get_travel_time_matrix(ctx.demand_points, all_facilities, params.threshold_min)
    result = solve_mclp(ctx.demand_points, ctx.candidates, ctx.existing_facilities, cm, k=2, threshold_min=45)
    print(f"  Proposed next 2: {result.selected_sites['locality_name'].tolist()}")
    print(f"  Coverage before: {result.coverage_pct_before:.1f}%")
    print(f"  Coverage after:  {result.coverage_pct_after:.1f}%")


if __name__ == "__main__":
    run_diagnostic()
    run_prescriptive_k6()
    run_prescriptive_k2()
    print("\n=== All queries working. ===")
