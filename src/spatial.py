from __future__ import annotations
from pathlib import Path

import geopandas as gpd
import pandas as pd
from src.models import QueryParams, SpatialContext

DATA_DIR = Path("data")

# Concordance uses "Australian Capital Territory"; boundary file uses "ACT"
_PHN_BOUNDARY_ALIASES: dict[str, str] = {
    "Australian Capital Territory": "ACT",
}


def load_sa2_access() -> pd.DataFrame:
    """Filipcikova SA2 access table joined to PHN concordance.

    Returns DataFrame with columns:
      SA2_CODE21, STE_NAME21, PHN_CODE, PHN_NAME, Person,
      gp_min, gp_bulk_billing_min, hospital_public_min, hospital_private_min,
      emergency_min, pharmacy_min,
      plus all raw _duration / _distance columns from the source file.
    """
    access = pd.read_csv(DATA_DIR / "health_access_sa2.csv", dtype={"SA2_CODE21": str})
    concordance = pd.read_csv(
        DATA_DIR / "phn_sa2_concordance.csv", dtype={"SA2_CODE21": str}
    )
    df = access.merge(concordance, on="SA2_CODE21", how="inner")

    # Convert seconds → minutes for headline metrics
    for col in (
        "gp", "gp_bulk_billing",
        "hospital_public", "hospital_private",
        "emergency", "pharmacy",
    ):
        src = f"{col}_duration"
        if src in df.columns:
            df[f"{col}_min"] = df[src] / 60.0
    return df


def load_sa2_geometries() -> gpd.GeoDataFrame:
    """National SA2 polygons (ABS ASGS 2021)."""
    sa2 = gpd.read_file(DATA_DIR / "sa2_2021_aust.geojson")
    if sa2.crs is None or sa2.crs.to_epsg() != 4326:
        sa2 = sa2.to_crs(epsg=4326)
    sa2["SA2_CODE21"] = sa2["SA2_CODE21"].astype(str)
    return sa2


def load_facility_layers() -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame, gpd.GeoDataFrame]:
    """Load GP locations, DPA polygons, and PHN boundaries (national)."""
    gp = gpd.read_file(DATA_DIR / "gp_locations.geojson")
    dpa = gpd.read_file(DATA_DIR / "dpa.shp")
    phn = gpd.read_file(DATA_DIR / "phn_boundaries.geojson")
    for g in (gp, dpa, phn):
        if g.crs is None or g.crs.to_epsg() != 4326:
            g.to_crs(epsg=4326, inplace=True)
    if "nhsd_service_type" in gp.columns:
        gp = gp[gp["nhsd_service_type"] == "General practice service"].reset_index(drop=True)
    return gp, dpa, phn


def _clip_by_geometry(
    gdf: gpd.GeoDataFrame,
    clip_geom,
) -> gpd.GeoDataFrame:
    """Clip a GeoDataFrame to clip_geom using sindex+intersection.

    gpd.clip is broken in this env (shapely 2.0.4 + GEOS 3.11). This replicates
    the same semantics: rows whose geometries intersect the clip area, with
    geometries truncated to the clip boundary.
    """
    idx = gdf.sindex.query(clip_geom, predicate="intersects")
    result = gdf.iloc[idx].copy()
    result["geometry"] = result.geometry.intersection(clip_geom)
    result = result[~result.geometry.is_empty].reset_index(drop=True)
    return result


def build_spatial_context_sa2_prescriptive(
    params: "QueryParams",
    access: pd.DataFrame,
    sa2: gpd.GeoDataFrame,
    gp_locations: gpd.GeoDataFrame,
    dpa: gpd.GeoDataFrame,
    phn: gpd.GeoDataFrame,
) -> SpatialContext:
    """Mode 2 (prescriptive) context. Demand = SA2s in PHN; candidates = SA2 centroids
    in PHN with no facility within proxy distance, ranked by DPA flag and population."""
    phn_access = access[access["PHN_NAME"] == params.region].copy()
    if params.pop_min is not None:
        phn_access = phn_access[phn_access["Person"] >= params.pop_min]
    demand = sa2.merge(phn_access, on="SA2_CODE21", how="inner")
    demand["demand_id"] = demand["SA2_CODE21"]
    demand["population"] = demand["Person"].fillna(0).astype(int)
    demand["locality_name"] = demand["SA2_NAME21"]
    demand = demand.copy()
    demand["geometry"] = demand.geometry.to_crs(epsg=7855).centroid.to_crs(epsg=4326)

    boundary_name = _PHN_BOUNDARY_ALIASES.get(params.region, params.region)
    phn_boundary = phn[phn["PHN_NAME"] == boundary_name]
    if phn_boundary.empty:
        raise ValueError(f"No PHN boundary for {params.region}")

    # Existing facilities for coverage check: PHN buffered by 30 km (cross-boundary).
    # gpd.clip, union_all(), and shapely.ops.unary_union all fail with
    # shapely 2.0.4 + GEOS 3.11 (create_collection ufunc not supported).
    # PHN boundaries are one row per PHN; extract the Shapely geometry directly via .iloc[0].
    phn_geom = phn_boundary.geometry.iloc[0]
    phn_gs = gpd.GeoSeries([phn_geom], crs="EPSG:4326")
    facility_search_geom = phn_gs.to_crs(epsg=7855).buffer(30_000).to_crs(epsg=4326).iloc[0]
    existing = _clip_by_geometry(gp_locations, facility_search_geom)
    existing["facility_id"] = existing.index.astype(str)

    candidates = _derive_candidates_sa2(params, demand, existing, dpa)
    return SpatialContext(
        demand_points=demand,
        existing_facilities=existing,
        candidates=candidates,
    )


def _derive_candidates_sa2(
    params: "QueryParams",
    demand: gpd.GeoDataFrame,
    facilities: gpd.GeoDataFrame,
    dpa: gpd.GeoDataFrame,
) -> gpd.GeoDataFrame:
    """SA2 centroids with no facility within proxy distance,
    ranked by DPA priority then population descending."""
    demand_proj = demand.to_crs(epsg=7855)
    facilities_proj = facilities.to_crs(epsg=7855)
    dpa_proj = dpa.to_crs(epsg=7855)
    proxy_m = params.threshold_min * 1000  # 1 km/min approximation

    if len(facilities_proj) > 0:
        near = demand_proj.geometry.apply(
            lambda g: facilities_proj.distance(g).min() <= proxy_m
        )
        cands = demand_proj[~near].copy()
    else:
        cands = demand_proj.copy()

    cands = cands.reset_index(drop=True)
    cands["dpa_priority"] = cands.geometry.apply(lambda g: dpa_proj.intersects(g).any())
    cands = cands.sort_values(
        ["dpa_priority", "population"], ascending=[False, False]
    ).reset_index(drop=True)
    cands["candidate_id"] = cands.index.astype(str)
    cands["facility_id"] = "c_" + cands["candidate_id"]
    return cands.to_crs(epsg=4326)


def list_phns(access: pd.DataFrame) -> list[str]:
    """Sorted PHN names from the access/concordance table."""
    return sorted(access["PHN_NAME"].dropna().unique().tolist())


def build_spatial_context_sa2(
    params: QueryParams,
    access: pd.DataFrame,
    sa2: gpd.GeoDataFrame,
) -> SpatialContext:
    """SA2-based context for Mode 1 (diagnostic).

    Mode 2 builder lives in `build_spatial_context_sa2_prescriptive` (Task 9).
    """
    phn_access = access[access["PHN_NAME"] == params.region].copy()
    if phn_access.empty:
        raise ValueError(f"No SA2s found for PHN: {params.region}")

    demand = sa2.merge(phn_access, on="SA2_CODE21", how="inner")
    demand["demand_id"] = demand["SA2_CODE21"]
    demand["population"] = demand["Person"].fillna(0).astype(int)
    demand["locality_name"] = demand["SA2_NAME21"]

    # Centroid for any downstream routing (Mode 1 reads gp_min directly; centroid is harmless)
    demand_centroids = demand.copy()
    demand_centroids["geometry"] = (
        demand.geometry.to_crs(epsg=7855).centroid.to_crs(epsg=4326)
    )

    empty_facilities = gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")
    empty_candidates = gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")
    return SpatialContext(
        demand_points=demand_centroids,
        existing_facilities=empty_facilities,
        candidates=empty_candidates,
    )
