from __future__ import annotations
import os

import geopandas as gpd
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

# In Streamlit Cloud, secrets are available via st.secrets
# Fall back to environment variables for local dev
for key in ["ANTHROPIC_API_KEY", "ARCGIS_CLIENT_ID", "ARCGIS_CLIENT_SECRET"]:
    if key not in os.environ and hasattr(st, "secrets") and key in st.secrets:
        os.environ[key] = st.secrets[key]

import src.models as _models
from src.models import QueryParams, ValidationError, ParseError, RoutingError, NarrativeContext
from src.spatial import load_all_data, build_spatial_context, load_sa2_access, load_sa2_geometries, build_spatial_context_sa2, load_facility_layers, build_spatial_context_sa2_prescriptive, list_phns
from src.routing import get_travel_time_matrix
from src.optimiser import solve_mclp, compute_coverage, diagnose_sa2_coverage
from src.nlp import parse_query, generate_narrative, build_tool_schema
from src.visualisation import build_diagnostic_map, build_prescriptive_map

st.set_page_config(
    page_title="Meridian — Health Coverage Intelligence",
    layout="wide",
)

DEMO_QUERY_TEMPLATES = {
    "diagnostic": [
        "Which towns in {phn} with more than 500 people are more than 45 minutes from the nearest bulk-billing GP?",
    ],
    "prescriptive": [
        "Where would you place 6 new GP clinics in {phn} to maximise population coverage within 45 minutes?",
        "Where should the next 2 GP clinics go in {phn} within 45 minutes, after Ochre Health's 6 recent openings?",
    ],
}


def demo_queries(phn: str, mode: str) -> list[str]:
    """Return demo query strings with the given PHN name substituted in."""
    return [t.format(phn=phn) for t in DEMO_QUERY_TEMPLATES[mode]]


@st.cache_resource(show_spinner=False)
def _load_data():
    status = st.empty()
    status.write("Loading PHN boundaries...")
    phn, localities, gp_locations, dpa = load_all_data()
    status.write("Spatial data loaded.")
    return phn, localities, gp_locations, dpa


@st.cache_resource(show_spinner=False)
def _load_sa2_layers():
    return load_sa2_access(), load_sa2_geometries()


@st.cache_resource(show_spinner=False)
def _phn_options() -> list[str]:
    access, _ = _load_sa2_layers()
    try:
        phns = list_phns(access)
    except (KeyError, Exception):
        phns = ["Western NSW"]
    if not phns:
        phns = ["Western NSW"]
    # Expand ALLOWED_REGIONS to the full national list now that data is loaded
    _models.ALLOWED_REGIONS[:] = phns
    return phns


# ── Header ──────────────────────────────────────────────────────────────────
st.title("Meridian — Health Coverage Intelligence")

phn_names = _phn_options()
default_idx = phn_names.index("Western NSW") if "Western NSW" in phn_names else 0
selected_phn = st.selectbox("Select PHN", options=phn_names, index=default_idx)
st.caption(f"PHN: {selected_phn} · AI-powered spatial decision support")

# ── Mode toggle ─────────────────────────────────────────────────────────────
mode = st.radio(
    "Mode",
    options=["diagnostic", "prescriptive"],
    format_func=lambda x: "Mode 1: Diagnostic" if x == "diagnostic" else "Mode 2: Prescriptive",
    horizontal=True,
    label_visibility="collapsed",
)

# Clear stale query when mode changes
if st.session_state.get("_last_mode") != mode:
    st.session_state["user_input"] = ""
    st.session_state["_last_mode"] = mode
    st.session_state.pop("results", None)

# ── Suggested queries ────────────────────────────────────────────────────────
st.caption("Try a suggested query:")
for query in demo_queries(selected_phn, mode):
    if st.button(query, key=f"btn_{hash(query)}"):
        st.session_state["user_input"] = query

# ── NL Input ────────────────────────────────────────────────────────────────
user_input = st.text_area(
    "Ask a question",
    value=st.session_state.get("user_input", ""),
    height=80,
    max_chars=500,
    label_visibility="collapsed",
)
analyse_clicked = st.button("Analyse", type="primary")

# ── Load spatial data (cold start) ──────────────────────────────────────────
with st.spinner("Loading spatial data..."):
    try:
        phn, localities, gp_locations, dpa = _load_data()
    except Exception as e:
        st.error(f"Failed to load spatial data: {e}")
        st.stop()

# ── Main logic ──────────────────────────────────────────────────────────────
if analyse_clicked and user_input.strip():
    error_placeholder = st.empty()

    # 1. Parse NL query
    with st.spinner("Parsing your question..."):
        try:
            _tool_schema = build_tool_schema(phn_names)
            params = parse_query(
                user_input,
                tool_schema=_tool_schema,
                fallback_region=selected_phn,
            )
        except ParseError as e:
            error_placeholder.error(
                "Could not interpret your question. "
                "Try rephrasing — e.g. 'Which towns lack GP coverage within 45 minutes?'"
            )
            st.stop()
        except ValidationError as e:
            error_placeholder.error(str(e))
            st.stop()
        except ValueError as e:
            error_placeholder.error(str(e))
            st.stop()

    if params.mode == "diagnostic":
        # ── Mode 1: SA2 precomputed access — no live routing ──────────────────
        with st.spinner("Preparing SA2 access data..."):
            access, sa2 = _load_sa2_layers()
            ctx = build_spatial_context_sa2(params, access, sa2)

        with st.spinner("Computing coverage from precomputed access..."):
            demand, summary = diagnose_sa2_coverage(
                ctx.demand_points, params.threshold_min, params.facility_type
            )

        covered_pop = summary["covered_population"]
        total_pop = summary["total_population"]
        pct = summary["coverage_pct"]
        uncovered_towns = demand.loc[~demand["covered"], "locality_name"].tolist()

        # Generate narrative
        with st.spinner("Generating briefing summary..."):
            narrative_ctx = NarrativeContext(
                mode=params.mode,
                region=params.region,
                threshold_min=params.threshold_min,
                covered_population=covered_pop,
                total_population=total_pop,
                coverage_pct=pct,
                uncovered_towns=uncovered_towns[:10],
            )
            narrative = generate_narrative(narrative_ctx)

        # Build map — demand already has `covered` column; no existing facilities layer
        empty_facilities = gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")
        folium_map = build_diagnostic_map(
            demand, empty_facilities, params.threshold_min,
            phn_boundary=None,
        )

        st.session_state["results"] = {
            "folium_map": folium_map,
            "mode": params.mode,
            "total_pop": total_pop,
            "covered_pop": covered_pop,
            "pct": pct,
            "threshold_min": params.threshold_min,
            "opt_result": None,
            "narrative": narrative,
            "sa2_summary": summary,
        }

    else:
        # ── Mode 2: Prescriptive — SA2 demand + buffered facility set ─────────
        with st.spinner("Preparing SA2 spatial data..."):
            access, sa2 = _load_sa2_layers()
            gp, dpa, phn = load_facility_layers()
            ctx = build_spatial_context_sa2_prescriptive(params, access, sa2, gp, dpa, phn)
            phn_region = phn[phn["PHN_NAME"] == params.region]

        with st.spinner("Computing coverage (using cached travel times)..."):
            try:
                all_facilities = gpd.GeoDataFrame(
                    pd.concat([ctx.existing_facilities, ctx.candidates], ignore_index=True),
                    crs=ctx.existing_facilities.crs,
                )
                cm = get_travel_time_matrix(ctx.demand_points, all_facilities, params.threshold_min)
            except RoutingError:
                error_placeholder.error(
                    "Could not compute travel times. Please check your ArcGIS credentials."
                )
                st.stop()

        opt_result = None
        if params.k:
            with st.spinner(f"Finding optimal {params.k} clinic locations..."):
                opt_result = solve_mclp(
                    ctx.demand_points, ctx.candidates, ctx.existing_facilities,
                    cm, k=params.k, threshold_min=params.threshold_min,
                )

        existing_ids = ctx.existing_facilities["facility_id"].tolist() if "facility_id" in ctx.existing_facilities.columns else []
        covered_pop, pct = compute_coverage(ctx.demand_points, existing_ids, cm.matrix, params.threshold_min)
        total_pop = int(ctx.demand_points["population"].sum())

        uncovered_mask = ctx.demand_points.apply(
            lambda row: (
                cm.matrix.loc[row["demand_id"], existing_ids].min() > params.threshold_min
                if row.get("demand_id") in cm.matrix.index and existing_ids else True
            ),
            axis=1,
        )
        uncovered_towns = ctx.demand_points[uncovered_mask]["locality_name"].tolist()

        with st.spinner("Generating briefing summary..."):
            narrative_ctx = NarrativeContext(
                mode=params.mode,
                region=params.region,
                threshold_min=params.threshold_min,
                covered_population=covered_pop,
                total_population=total_pop,
                coverage_pct=pct,
                uncovered_towns=uncovered_towns[:10],
                proposed_sites=opt_result.selected_sites["locality_name"].tolist() if opt_result is not None and "locality_name" in opt_result.selected_sites.columns else None,
                covered_before=opt_result.covered_before if opt_result else None,
                covered_after=opt_result.covered_after if opt_result else None,
                coverage_pct_before=opt_result.coverage_pct_before if opt_result else None,
                coverage_pct_after=opt_result.coverage_pct_after if opt_result else None,
                k=params.k,
            )
            narrative = generate_narrative(narrative_ctx)

        ctx.demand_points["covered"] = ctx.demand_points.apply(
            lambda row: (
                cm.matrix.loc[row["demand_id"], existing_ids].min() <= params.threshold_min
                if row.get("demand_id") in cm.matrix.index and existing_ids else False
            ),
            axis=1,
        )

        if opt_result is not None:
            folium_map = build_prescriptive_map(
                ctx.demand_points, ctx.existing_facilities,
                opt_result.selected_sites, params.threshold_min,
                phn_boundary=phn_region,
            )
        else:
            folium_map = build_diagnostic_map(
                ctx.demand_points, ctx.existing_facilities, params.threshold_min,
                phn_boundary=phn_region,
            )

        st.session_state["results"] = {
            "folium_map": folium_map,
            "mode": params.mode,
            "total_pop": total_pop,
            "covered_pop": covered_pop,
            "pct": pct,
            "threshold_min": params.threshold_min,
            "opt_result": opt_result,
            "narrative": narrative,
        }

elif analyse_clicked and not user_input.strip():
    st.warning("Please enter a question before clicking Analyse.")

# ── Render results (runs on every render, including folium-triggered reruns) ──
if "results" in st.session_state:
    r = st.session_state["results"]
    col_map, col_summary = st.columns([0.6, 0.4])

    with col_map:
        st.plotly_chart(r["folium_map"], use_container_width=True)

    with col_summary:
        st.subheader("Coverage Summary")
        st.metric("Population analysed", f"{r['total_pop']:,}")
        st.metric(
            f"Within {r['threshold_min']} min of GP",
            f"{r['covered_pop']:,}",
            delta=f"{r['pct']:.1f}%",
        )

        if r["mode"] == "prescriptive" and r["opt_result"]:
            opt_result = r["opt_result"]
            st.divider()
            st.subheader("After proposed clinics")
            delta = opt_result.covered_after - opt_result.covered_before
            st.metric(
                "Additional people covered",
                f"+{delta:,}",
                delta=f"{opt_result.coverage_pct_after:.1f}% total",
            )
            st.write("**Proposed locations:**")
            for _, site in opt_result.selected_sites.iterrows():
                st.write(f"- {site.get('locality_name', 'Unknown')}")

        st.divider()
        st.subheader("Briefing Summary")
        st.write(r["narrative"])
        st.caption("Prepared by: Meridian Geospatial")
