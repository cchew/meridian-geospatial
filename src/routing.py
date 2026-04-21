from __future__ import annotations
import hashlib
import json
import os
import time
from pathlib import Path

import geopandas as gpd
import pandas as pd
import requests

from src.models import CoverageMatrix, RoutingError

CACHE_DIR = Path("cache")
ARCGIS_TOKEN_URL = "https://www.arcgis.com/sharing/rest/oauth2/token"
ARCGIS_OD_URL = (
    "https://route.arcgis.com/arcgis/rest/services/World/"
    "OriginDestinationCostMatrix/NAServer/"
    "OriginDestinationCostMatrix_World/solveODCostMatrix"
)
ORS_MATRIX_URL = "https://api.openrouteservice.org/v2/matrix/driving-car"

_token_cache: dict = {}


def _get_token() -> str:
    """Fetch OAuth2 token, reuse if not expired."""
    now = time.time()
    if _token_cache.get("token") and _token_cache.get("expires_at", 0) > now + 60:
        return _token_cache["token"]

    client_id = os.environ["ARCGIS_CLIENT_ID"]
    client_secret = os.environ["ARCGIS_CLIENT_SECRET"]

    resp = requests.post(
        ARCGIS_TOKEN_URL,
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": "client_credentials",
            "f": "json",
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    if "error" in data:
        raise RoutingError(f"ArcGIS auth error: {data['error'].get('message', 'unknown')}")

    _token_cache["token"] = data["access_token"]
    _token_cache["expires_at"] = now + data.get("expires_in", 3600)
    return _token_cache["token"]


def _gdf_to_features(gdf: gpd.GeoDataFrame) -> list[dict]:
    """Convert GeoDataFrame points to ArcGIS FeatureSet features."""
    if gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(epsg=4326)
    features = []
    for i, row in enumerate(gdf.itertuples()):
        features.append({
            "geometry": {
                "x": row.geometry.x,
                "y": row.geometry.y,
                "spatialReference": {"wkid": 4326},
            },
            "attributes": {"ObjectID": i},
        })
    return features


def _parse_od_response(
    response: dict,
    demand_ids: list[str],
    facility_ids: list[str],
) -> pd.DataFrame:
    """Parse ArcGIS OD response into a demand x facility travel time DataFrame."""
    matrix = pd.DataFrame(
        index=demand_ids, columns=facility_ids, dtype=float
    )
    matrix[:] = float("inf")

    for feature in response.get("odLines", {}).get("features", []):
        attrs = feature["attributes"]
        origin_idx = attrs["OriginOID"]
        dest_idx = attrs["DestinationOID"]
        if origin_idx < len(demand_ids) and dest_idx < len(facility_ids):
            matrix.loc[demand_ids[origin_idx], facility_ids[dest_idx]] = attrs["Total_Time"]

    return matrix


def _call_arcgis_od_matrix(
    demand: gpd.GeoDataFrame,
    facilities: gpd.GeoDataFrame,
) -> dict:
    """Call ArcGIS OD Cost Matrix REST API. Returns raw response dict."""
    token = _get_token()
    origins = {"features": _gdf_to_features(demand)}
    destinations = {"features": _gdf_to_features(facilities)}

    resp = requests.post(
        ARCGIS_OD_URL,
        data={
            "origins": json.dumps(origins),
            "destinations": json.dumps(destinations),
            "token": token,
            "f": "json",
            "returnODLines": "true",
            "outputLines": "esriNAOutputLineNone",
            "defaultTargetDestinationCount": len(facilities),
        },
        timeout=120,
    )
    resp.raise_for_status()
    data = resp.json()
    if "error" in data:
        raise RoutingError(
            f"ArcGIS OD error: {data['error'].get('message', 'unknown')}"
            # Token deliberately not included in error message
        )
    return data


def _call_ors_matrix(
    demand: gpd.GeoDataFrame,
    facilities: gpd.GeoDataFrame,
) -> pd.DataFrame:
    """Call OpenRouteService Matrix API. Returns demand x facility travel time DataFrame (minutes)."""
    api_key = os.environ.get("ORS_API_KEY")
    if not api_key:
        raise RoutingError("ORS_API_KEY not set in environment")

    if demand.crs.to_epsg() != 4326:
        demand = demand.to_crs(epsg=4326)
    if facilities.crs.to_epsg() != 4326:
        facilities = facilities.to_crs(epsg=4326)

    demand_ids = demand["demand_id"].tolist() if "demand_id" in demand.columns else [str(i) for i in demand.index]
    facility_ids = facilities["facility_id"].tolist() if "facility_id" in facilities.columns else [str(i) for i in facilities.index]

    # ORS takes [lon, lat] pairs
    demand_coords = [[geom.x, geom.y] for geom in demand.geometry]
    facility_coords = [[geom.x, geom.y] for geom in facilities.geometry]

    # Free tier: max 3500 pairs per request — chunk demand if needed
    n_facilities = len(facility_coords)
    chunk_size = max(1, 3500 // n_facilities)

    matrix = pd.DataFrame(index=demand_ids, columns=facility_ids, dtype=float)
    matrix[:] = float("inf")

    for chunk_start in range(0, len(demand_coords), chunk_size):
        chunk_demand_coords = demand_coords[chunk_start : chunk_start + chunk_size]
        chunk_demand_ids = demand_ids[chunk_start : chunk_start + chunk_size]
        all_coords = chunk_demand_coords + facility_coords
        chunk_sources = list(range(len(chunk_demand_coords)))
        chunk_destinations = list(range(len(chunk_demand_coords), len(all_coords)))

        resp = requests.post(
            ORS_MATRIX_URL,
            headers={"Authorization": api_key, "Content-Type": "application/json"},
            json={
                "locations": all_coords,
                "sources": chunk_sources,
                "destinations": chunk_destinations,
                "metrics": ["duration"],
            },
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()

        if "error" in data:
            raise RoutingError(f"ORS error: {data['error'].get('message', data['error'])}")

        durations = data["durations"]  # seconds, shape: [chunk_demand][n_facilities]
        for i, row in enumerate(durations):
            for j, seconds in enumerate(row):
                val = float("inf") if seconds is None else seconds / 60.0
                matrix.loc[chunk_demand_ids[i], facility_ids[j]] = val

    return matrix


def compute_cache_key(
    demand: gpd.GeoDataFrame,
    facilities: gpd.GeoDataFrame,
    threshold_min: int,
) -> str:
    """Deterministic cache key from coordinates + threshold."""
    if demand.crs.to_epsg() != 4326:
        demand = demand.to_crs(epsg=4326)
    if facilities.crs.to_epsg() != 4326:
        facilities = facilities.to_crs(epsg=4326)

    demand_coords = sorted([(round(g.x, 5), round(g.y, 5)) for g in demand.geometry])
    facility_coords = sorted([(round(g.x, 5), round(g.y, 5)) for g in facilities.geometry])
    key_data = str(demand_coords) + str(facility_coords) + str(threshold_min)
    return hashlib.sha256(key_data.encode()).hexdigest()[:16]


def get_travel_time_matrix(
    demand: gpd.GeoDataFrame,
    facilities: gpd.GeoDataFrame,
    threshold_min: int,
    cache_dir: Path = CACHE_DIR,
) -> CoverageMatrix:
    """Return travel time matrix. Cache-first; provider selected by ROUTING_PROVIDER env var (arcgis|ors)."""
    cache_dir.mkdir(exist_ok=True)
    cache_key = compute_cache_key(demand, facilities, threshold_min)
    cache_path = cache_dir / f"{cache_key}.parquet"

    demand_ids = demand["demand_id"].tolist() if "demand_id" in demand.columns else [str(i) for i in demand.index]
    facility_ids = facilities["facility_id"].tolist() if "facility_id" in facilities.columns else [str(i) for i in facilities.index]

    if cache_path.exists():
        matrix = pd.read_parquet(cache_path)
        return CoverageMatrix(matrix=matrix, demand_ids=demand_ids, facility_ids=facility_ids)

    provider = os.environ.get("ROUTING_PROVIDER", "arcgis").lower()
    if provider == "ors":
        matrix = _call_ors_matrix(demand, facilities)
    else:
        raw = _call_arcgis_od_matrix(demand, facilities)
        matrix = _parse_od_response(raw, demand_ids, facility_ids)

    matrix.to_parquet(cache_path)
    return CoverageMatrix(matrix=matrix, demand_ids=demand_ids, facility_ids=facility_ids)
