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

from src.models import QueryParams, ValidationError, ParseError, RoutingError, NarrativeContext
from src.spatial import load_all_data, build_spatial_context
from src.routing import get_travel_time_matrix
from src.optimiser import solve_mclp, compute_coverage
from src.nlp import parse_query, generate_narrative
from src.visualisation import build_diagnostic_map, build_prescriptive_map

st.set_page_config(
    page_title="Meridian — Health Coverage Intelligence",
    layout="wide",
)

DEMO_QUERIES = {
    "diagnostic": [
        "Which towns in Western NSW with more than 500 people are more than 45 minutes from the nearest bulk-billing GP?",
    ],
    "prescriptive": [
        "Where would you place 6 new GP clinics in Western NSW to maximise population coverage within 45 minutes?",
        "Where should the next 2 GP clinics go in Western NSW within 45 minutes, after Ochre Health's 6 recent openings?",
    ],
}


@st.cache_resource(show_spinner=False)
def _load_data():
    status = st.empty()
    status.write("Loading PHN boundaries...")
    phn, localities, gp_locations, dpa = load_all_data()
    status.write("Spatial data loaded.")
    return phn, localities, gp_locations, dpa


# ── Header ──────────────────────────────────────────────────────────────────
st.title("Meridian — Health Coverage Intelligence")
st.caption("Western NSW PHN · AI-powered spatial decision support")

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
for query in DEMO_QUERIES[mode]:
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
            params = parse_query(user_input)
        except ParseError as e:
            error_placeholder.error(
                "Could not interpret your question. "
                "Try rephrasing — e.g. 'Which towns lack GP coverage within 45 minutes?'"
            )
            st.stop()
        except ValidationError as e:
            error_placeholder.error(
                "This demo is scoped to Western NSW PHN. "
                "Support for additional PHNs is in development."
            )
            st.stop()
        except ValueError as e:
            error_placeholder.error(str(e))
            st.stop()

    # 2. Build spatial context
    with st.spinner("Preparing spatial data..."):
        ctx = build_spatial_context(params, phn, localities, gp_locations, dpa)
        phn_region = phn[phn["PHN_NAME"] == params.region]

    # 3. Get travel time matrix
    with st.spinner("Computing coverage (using cached travel times)..."):
        try:
            if params.mode == "prescriptive":
                all_facilities = gpd.GeoDataFrame(
                    pd.concat([ctx.existing_facilities, ctx.candidates], ignore_index=True),
                    crs=ctx.existing_facilities.crs,
                )
                cm = get_travel_time_matrix(ctx.demand_points, all_facilities, params.threshold_min)
            else:
                cm = get_travel_time_matrix(ctx.demand_points, ctx.existing_facilities, params.threshold_min)
        except RoutingError as e:
            error_placeholder.error(
                "Could not compute travel times. Please check your ArcGIS credentials."
            )
            st.stop()

    # 4. Run solver (Mode 2 only)
    opt_result = None
    if params.mode == "prescriptive" and params.k:
        with st.spinner(f"Finding optimal {params.k} clinic locations..."):
            opt_result = solve_mclp(
                ctx.demand_points, ctx.candidates, ctx.existing_facilities,
                cm, k=params.k, threshold_min=params.threshold_min,
            )

    # 5. Compute coverage for diagnostic
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

    # 6. Generate narrative
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

    # 7. Add coverage flag to demand points
    ctx.demand_points["covered"] = ctx.demand_points.apply(
        lambda row: (
            cm.matrix.loc[row["demand_id"], existing_ids].min() <= params.threshold_min
            if row.get("demand_id") in cm.matrix.index and existing_ids else False
        ),
        axis=1,
    )

    # 8. Build map
    if params.mode == "prescriptive" and opt_result is not None:
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

    # 9. Store results in session state
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
