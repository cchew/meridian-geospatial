from __future__ import annotations

import json
import math

import geopandas as gpd
import plotly.graph_objects as go


def _map_centre(demand: gpd.GeoDataFrame) -> tuple[float, float]:
    """Return (lat, lon) centroid of demand points."""
    return (
        (demand.geometry.y.min() + demand.geometry.y.max()) / 2,
        (demand.geometry.x.min() + demand.geometry.x.max()) / 2,
    )


def _calc_zoom(demand: gpd.GeoDataFrame) -> float:
    """Estimate zoom level from the geographic extent of demand points."""
    lat_range = demand.geometry.y.max() - demand.geometry.y.min()
    lon_range = demand.geometry.x.max() - demand.geometry.x.min()
    extent = max(lat_range, lon_range) if max(lat_range, lon_range) > 0 else 5.0
    return max(3.0, min(10.0, math.log2(360.0 / extent) - 1))


def _marker_sizes(demand: gpd.GeoDataFrame) -> list[int]:
    return [max(6, min(20, int(pop / 500))) for pop in demand["population"]]


def _phn_layer(phn_boundary: gpd.GeoDataFrame) -> dict:
    """Orange outline of the PHN boundary — drawn as a GeoJSON line layer."""
    return {
        "source": json.loads(phn_boundary.to_json()),
        "type": "line",
        "color": "#e67e22",
        "line": {"width": 2},
        "opacity": 0.9,
    }


def build_diagnostic_map(
    demand: gpd.GeoDataFrame,
    existing_facilities: gpd.GeoDataFrame,
    threshold_min: int,
    phn_boundary: gpd.GeoDataFrame | None = None,
) -> go.Figure:
    """
    Scatter map for Mode 1.
    demand must have columns: locality_name, population, covered (bool), geometry
    """
    fig = go.Figure()
    lat, lon = _map_centre(demand)
    zoom = _calc_zoom(demand)

    # Demand points — split by covered status
    for is_covered in (False, True):
        colour = "#2ecc71" if is_covered else "#e74c3c"
        label = "Covered" if is_covered else "Uncovered"
        status_word = "Within" if is_covered else "Outside"
        subset = (
            demand[demand["covered"] == is_covered]
            if "covered" in demand.columns
            else (gpd.GeoDataFrame() if is_covered else demand)
        )
        if len(subset) == 0:
            continue
        fig.add_trace(go.Scattermap(
            lat=subset.geometry.y.tolist(),
            lon=subset.geometry.x.tolist(),
            mode="markers",
            marker=dict(size=_marker_sizes(subset), color=colour, opacity=0.85),
            text=[
                f"<b>{row.get('locality_name', 'Unknown')}</b><br>"
                f"Population: {row['population']:,}<br>"
                f"{status_word} {threshold_min} min"
                for _, row in subset.iterrows()
            ],
            hoverinfo="text",
            name=label,
        ))

    # Existing GP facilities
    if len(existing_facilities) > 0:
        fig.add_trace(go.Scattermap(
            lat=existing_facilities.geometry.y.tolist(),
            lon=existing_facilities.geometry.x.tolist(),
            mode="markers",
            marker=dict(size=14, color="#2c3e50", symbol="circle"),
            text=[str(row.get("practice_name", "GP Practice")) for _, row in existing_facilities.iterrows()],
            hoverinfo="text",
            name="Existing GP",
        ))

    layers = (
        [_phn_layer(phn_boundary)]
        if phn_boundary is not None and len(phn_boundary) > 0
        else []
    )

    fig.update_layout(
        map=dict(
            style="open-street-map",
            center=dict(lat=lat, lon=lon),
            zoom=zoom,
            layers=layers,
        ),
        margin=dict(l=0, r=0, t=0, b=0),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        height=500,
    )
    return fig


def build_prescriptive_map(
    demand: gpd.GeoDataFrame,
    existing_facilities: gpd.GeoDataFrame,
    proposed_sites: gpd.GeoDataFrame,
    threshold_min: int,
    phn_boundary: gpd.GeoDataFrame | None = None,
) -> go.Figure:
    """
    Map for Mode 2 — shows existing facilities, demand coverage, and proposed sites.
    """
    fig = build_diagnostic_map(demand, existing_facilities, threshold_min, phn_boundary)

    if len(proposed_sites) > 0:
        # Outer ring (white) for contrast, then inner gold fill layered on top
        fig.add_trace(go.Scattermap(
            lat=proposed_sites.geometry.y.tolist(),
            lon=proposed_sites.geometry.x.tolist(),
            mode="markers",
            marker=dict(size=28, color="white", symbol="circle", opacity=0.95),
            hoverinfo="skip",
            showlegend=False,
        ))
        fig.add_trace(go.Scattermap(
            lat=proposed_sites.geometry.y.tolist(),
            lon=proposed_sites.geometry.x.tolist(),
            mode="markers",
            marker=dict(size=20, color="#f39c12", symbol="circle", opacity=1.0),
            text=[f"<b>Proposed: {row.get('locality_name', 'Site')}</b>" for _, row in proposed_sites.iterrows()],
            hoverinfo="text",
            name="Proposed clinic",
        ))

    return fig
