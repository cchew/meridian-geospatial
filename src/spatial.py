from __future__ import annotations
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

from src.models import QueryParams, SpatialContext

DATA_DIR = Path("data")

# UCL layer name in the ABS GeoPackage
_UCL_LAYER = "UCL_2021_AUST_GDA2020"


def _load_localities_with_population() -> gpd.GeoDataFrame:
    """Load UCL boundaries and join 2021 Census population (Tot_P_P from G01 table)."""
    localities = gpd.read_file(DATA_DIR / "localities.gpkg", layer=_UCL_LAYER)
    pop_path = DATA_DIR / "ucl_population_nsw.csv"
    if not pop_path.exists():
        raise RuntimeError(
            "ucl_population_nsw.csv not found. Run scripts/download_data.py first."
        )
    pop = pd.read_csv(pop_path, usecols=["UCL_CODE_2021", "Tot_P_P"], dtype=str)
    # Census CSV prefixes codes with "UCL" (e.g. "UCL101001"); GeoPackage uses bare codes
    pop["UCL_CODE_2021"] = pop["UCL_CODE_2021"].str.removeprefix("UCL")
    pop["Tot_P_P"] = pd.to_numeric(pop["Tot_P_P"], errors="coerce").fillna(0).astype(int)
    pop = pop.rename(columns={"Tot_P_P": "population"})
    localities = localities.merge(pop, on="UCL_CODE_2021", how="left")
    localities["population"] = localities["population"].fillna(0).astype(int)
    return localities


def load_all_data() -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame, gpd.GeoDataFrame, gpd.GeoDataFrame]:
    """Load all spatial datasets. Call once at startup and cache with @st.cache_resource."""
    from src.security import verify_checksums, ChecksumError
    try:
        verify_checksums(DATA_DIR, DATA_DIR / "checksums.sha256")
    except ChecksumError as e:
        raise RuntimeError(f"Data integrity check failed: {e}") from e

    phn = gpd.read_file(DATA_DIR / "phn_boundaries.geojson")
    localities = _load_localities_with_population()
    gp_locations = gpd.read_file(DATA_DIR / "gp_locations.geojson")
    dpa = gpd.read_file(DATA_DIR / "dpa.shp")

    # Standardise CRS to WGS84
    for gdf in [phn, localities, gp_locations, dpa]:
        if gdf.crs.to_epsg() != 4326:
            gdf.to_crs(epsg=4326, inplace=True)

    return phn, localities, gp_locations, dpa


def build_spatial_context(
    params: QueryParams,
    phn: gpd.GeoDataFrame,
    localities: gpd.GeoDataFrame,
    gp_locations: gpd.GeoDataFrame,
    dpa: gpd.GeoDataFrame,
) -> SpatialContext:
    """Filter data to PHN region and derive candidate sites."""
    phn_boundary = phn[phn["PHN_NAME"] == params.region]

    # Clip localities to PHN — exclude ABS residual "Remainder" locality
    demand = gpd.clip(localities, phn_boundary)
    demand = demand[~demand["UCL_NAME_2021"].str.startswith("Remainder of")]
    if params.pop_min is not None:
        demand = demand[demand["population"] >= params.pop_min].copy()
    demand = demand.reset_index(drop=True)
    # Alias UCL_NAME_2021 → locality_name for consistent downstream access
    if "locality_name" not in demand.columns and "UCL_NAME_2021" in demand.columns:
        demand = demand.copy()
        demand["locality_name"] = demand["UCL_NAME_2021"]
    demand["demand_id"] = demand.index.astype(str)
    # Routing expects point geometries — use centroids for polygon locality boundaries
    if demand.geometry.geom_type.isin(["Polygon", "MultiPolygon"]).any():
        demand = demand.copy()
        demand["geometry"] = demand.geometry.to_crs(epsg=7855).centroid.to_crs(epsg=4326)

    # Clip GP locations to PHN — filter to GP services only
    facilities = gpd.clip(gp_locations, phn_boundary).reset_index(drop=True)
    if "nhsd_service_type" in facilities.columns:
        facilities = facilities[
            facilities["nhsd_service_type"] == "General practice service"
        ].reset_index(drop=True)
    facilities["facility_id"] = facilities.index.astype(str)

    # Derive candidates for Mode 2
    candidates = gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")
    if params.mode == "prescriptive":
        candidates = _derive_candidates(params, demand, facilities, dpa)

    return SpatialContext(
        demand_points=demand,
        existing_facilities=facilities,
        candidates=candidates,
    )


def _derive_candidates(
    params: QueryParams,
    demand: gpd.GeoDataFrame,
    facilities: gpd.GeoDataFrame,
    dpa: gpd.GeoDataFrame,
) -> gpd.GeoDataFrame:
    """
    Candidate sites = demand points with no existing GP within straight-line
    distance proxy (2x travel threshold, assuming ~60 km/h avg -> threshold_min km).
    """
    # Use projected CRS for distance calculations (GDA2020 / MGA zone 55)
    demand_proj = demand.to_crs(epsg=7855)
    facilities_proj = facilities.to_crs(epsg=7855)
    dpa_proj = dpa.to_crs(epsg=7855)

    # Approximate: 1 minute driving ~= 1 km at 60 km/h in rural NSW
    proxy_distance_m = params.threshold_min * 1000  # threshold in metres

    # Keep demand points that have no facility within proxy distance
    if len(facilities_proj) > 0:
        near_facility = demand_proj.geometry.apply(
            lambda geom: facilities_proj.distance(geom).min() <= proxy_distance_m
        )
        candidates_proj = demand_proj[~near_facility].copy()
    else:
        candidates_proj = demand_proj.copy()

    candidates_proj = candidates_proj.reset_index(drop=True)

    # Add DPA priority flag
    candidates_proj["dpa_priority"] = candidates_proj.geometry.apply(
        lambda geom: dpa_proj.intersects(geom).any()
    )

    # Sort: DPA first, then by population descending
    candidates_proj = candidates_proj.sort_values(
        ["dpa_priority", "population"], ascending=[False, False]
    ).reset_index(drop=True)

    candidates_proj["candidate_id"] = candidates_proj.index.astype(str)
    # facility_id mirrors candidate_id so existing + candidates can be merged uniformly
    candidates_proj["facility_id"] = "c_" + candidates_proj["candidate_id"]
    # Alias UCL_NAME_2021 → locality_name
    if "locality_name" not in candidates_proj.columns and "UCL_NAME_2021" in candidates_proj.columns:
        candidates_proj["locality_name"] = candidates_proj["UCL_NAME_2021"]
    return candidates_proj.to_crs(epsg=4326)


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


def list_phns(access: pd.DataFrame) -> list[str]:
    """Sorted PHN names from the access/concordance table."""
    return sorted(access["PHN_NAME"].dropna().unique().tolist())
