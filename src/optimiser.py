from __future__ import annotations

import geopandas as gpd
import pandas as pd
from pulp import LpProblem, LpVariable, LpMaximize, lpSum, value, PULP_CBC_CMD

from src.models import CoverageMatrix, OptimisationResult


def compute_coverage(
    demand: gpd.GeoDataFrame,
    facility_ids: list[str],
    matrix: pd.DataFrame,
    threshold_min: int,
) -> tuple[int, float]:
    """Compute covered population given a set of active facility IDs."""
    total_pop = demand["population"].sum()
    if total_pop == 0:
        return 0, 0.0

    covered_pop = 0
    for _, row in demand.iterrows():
        did = row["demand_id"]
        if did not in matrix.index:
            continue
        times = [matrix.loc[did, fid] for fid in facility_ids if fid in matrix.columns]
        if times and min(times) <= threshold_min:
            covered_pop += row["population"]

    return int(covered_pop), round(covered_pop / total_pop * 100, 2)


def solve_mclp(
    demand: gpd.GeoDataFrame,
    candidates: gpd.GeoDataFrame,
    existing_facilities: gpd.GeoDataFrame,
    coverage_matrix: CoverageMatrix,
    k: int,
    threshold_min: int,
) -> OptimisationResult:
    """
    Maximal Coverage Location Problem via PuLP.

    Selects k candidate sites to maximise covered population.
    Coverage is determined by travel time <= threshold_min minutes.
    """
    matrix = coverage_matrix.matrix
    demand_ids = [row["demand_id"] for _, row in demand.iterrows() if "demand_id" in demand.columns]
    existing_ids = [row["facility_id"] for _, row in existing_facilities.iterrows() if "facility_id" in existing_facilities.columns]
    candidate_ids = [row["facility_id"] for _, row in candidates.iterrows() if "facility_id" in candidates.columns]

    # Compute before coverage (existing facilities only)
    covered_before, pct_before = compute_coverage(demand, existing_ids, matrix, threshold_min)

    if len(candidate_ids) == 0:
        return OptimisationResult(
            selected_sites=gpd.GeoDataFrame(geometry=[], crs="EPSG:4326"),
            covered_before=covered_before,
            covered_after=covered_before,
            coverage_pct_before=pct_before,
            coverage_pct_after=pct_before,
        )

    n_demand = len(demand_ids)
    n_candidates = len(candidate_ids)

    # Build coverage sets: which candidates cover each demand point?
    covered_by: dict[str, list[int]] = {}
    for did in demand_ids:
        covered_by[did] = []
        if did not in matrix.index:
            continue
        # Also check if already covered by existing
        existing_times = [matrix.loc[did, fid] for fid in existing_ids if fid in matrix.columns]
        already_covered = existing_times and min(existing_times) <= threshold_min
        if not already_covered:
            for j, cid in enumerate(candidate_ids):
                if cid in matrix.columns and matrix.loc[did, cid] <= threshold_min:
                    covered_by[did].append(j)

    prob = LpProblem("MCLP", LpMaximize)
    x = [LpVariable(f"x_{j}", cat="Binary") for j in range(n_candidates)]
    y = [LpVariable(f"y_{i}", cat="Binary") for i in range(n_demand)]

    pops = [int(demand.loc[demand["demand_id"] == did, "population"].iloc[0]) for did in demand_ids]

    prob += lpSum(pops[i] * y[i] for i in range(n_demand))
    prob += lpSum(x) <= k

    for i, did in enumerate(demand_ids):
        existing_times = [matrix.loc[did, fid] for fid in existing_ids if fid in matrix.columns and did in matrix.index]
        if existing_times and min(existing_times) <= threshold_min:
            prob += y[i] == 1
        elif covered_by[did]:
            prob += y[i] <= lpSum(x[j] for j in covered_by[did])
        else:
            prob += y[i] == 0

    prob.solve(PULP_CBC_CMD(msg=0))

    selected_indices = [j for j in range(n_candidates) if value(x[j]) is not None and value(x[j]) > 0.5]
    selected_ids = [candidate_ids[j] for j in selected_indices]
    selected_sites = candidates[candidates["facility_id"].isin(selected_ids)].copy()

    active_ids = existing_ids + selected_ids
    covered_after, pct_after = compute_coverage(demand, active_ids, matrix, threshold_min)

    return OptimisationResult(
        selected_sites=selected_sites,
        covered_before=covered_before,
        covered_after=covered_after,
        coverage_pct_before=pct_before,
        coverage_pct_after=pct_after,
    )
