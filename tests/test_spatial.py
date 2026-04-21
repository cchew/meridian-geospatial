import pytest
from src.spatial import build_spatial_context
from src.models import QueryParams


def test_demand_points_filtered_by_population(localities, phn_boundary, gp_locations, dpa):
    params = QueryParams(
        mode="diagnostic",
        region="Western NSW",
        facility_type="gp",
        threshold_min=45,
        pop_min=2000,
    )
    ctx = build_spatial_context(params, phn_boundary, localities, gp_locations, dpa)
    # Town B has pop 1500, below 2000 threshold — should be excluded
    assert len(ctx.demand_points) == 2
    assert "Town B" not in ctx.demand_points["locality_name"].values


def test_existing_facilities_clipped_to_phn(localities, phn_boundary, gp_locations, dpa):
    params = QueryParams(
        mode="diagnostic",
        region="Western NSW",
        facility_type="gp",
        threshold_min=45,
        pop_min=None,
    )
    ctx = build_spatial_context(params, phn_boundary, localities, gp_locations, dpa)
    assert len(ctx.existing_facilities) == 1


def test_candidates_derived_for_prescriptive(localities, phn_boundary, gp_locations, dpa):
    params = QueryParams(
        mode="prescriptive",
        region="Western NSW",
        facility_type="gp",
        threshold_min=45,
        k=2,
        pop_min=1000,
    )
    ctx = build_spatial_context(params, phn_boundary, localities, gp_locations, dpa)
    # Candidates should exist and have dpa_priority column
    assert len(ctx.candidates) > 0
    assert "dpa_priority" in ctx.candidates.columns


def test_candidates_empty_for_diagnostic(localities, phn_boundary, gp_locations, dpa):
    params = QueryParams(
        mode="diagnostic",
        region="Western NSW",
        facility_type="gp",
        threshold_min=45,
        pop_min=None,
    )
    ctx = build_spatial_context(params, phn_boundary, localities, gp_locations, dpa)
    assert len(ctx.candidates) == 0
