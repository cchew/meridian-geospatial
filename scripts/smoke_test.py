#!/usr/bin/env python3
"""
Pre-demo smoke test — verify all integrations before running a live demo.
Usage: python scripts/smoke_test.py
Exit 0 = all checks pass. Exit 1 = failures.
"""
from __future__ import annotations
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
PASS = "  \u2713"
FAIL = "  \u2717"
SKIP = "  \u25cb"

results: list[bool] = []


def check(label: str, fn, skip_if_missing_env: str | None = None) -> bool:
    if skip_if_missing_env and not os.environ.get(skip_if_missing_env):
        print(f"{SKIP} {label} (skipped — {skip_if_missing_env} not set)")
        return True  # don't fail for missing optional env
    try:
        fn()
        print(f"{PASS} {label}")
        return True
    except Exception as e:
        print(f"{FAIL} {label}: {e}")
        return False


# ── 1. Data files ─────────────────────────────────────────────────────────────
print("\n1. Data files")

def _check_data_files():
    required = [
        "data/phn_boundaries.geojson",
        "data/gp_locations.geojson",
        "data/dpa.shp",
        "data/health_access_sa2.csv",
        "data/phn_sa2_concordance.csv",
        "data/sa2_2021_aust.geojson",
        "data/checksums.sha256",
    ]
    missing = [f for f in required if not (ROOT / f).exists()]
    if missing:
        raise FileNotFoundError(f"Missing: {', '.join(missing)}")

results.append(check("required data files present", _check_data_files))

def _check_checksums():
    from src.security import verify_checksums, ChecksumError
    verify_checksums(ROOT / "data", ROOT / "data" / "checksums.sha256")

results.append(check("data file checksums valid", _check_checksums))

def _check_cache():
    parquet_files = list((ROOT / "cache").glob("*.parquet"))
    if not parquet_files:
        raise FileNotFoundError("No cached travel time matrices in cache/ — run scripts/precompute_matrix.py")
    # check they're readable
    import pandas as pd
    for f in parquet_files[:1]:
        df = pd.read_parquet(f)
        if df.empty:
            raise ValueError(f"{f.name} is empty")

results.append(check("cached travel time matrices present and readable", _check_cache))

# ── 2. Python imports ──────────────────────────────────────────────────────────
print("\n2. Python dependencies")

def _import(name: str):
    return lambda: __import__(name)

for pkg in ["geopandas", "anthropic", "streamlit", "plotly", "pulp", "pyarrow", "shapely", "fiona"]:
    results.append(check(f"import {pkg}", _import(pkg)))

# ── 3. API connectivity ────────────────────────────────────────────────────────
print("\n3. API connectivity")

def _check_anthropic():
    import anthropic
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    resp = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=5,
        messages=[{"role": "user", "content": "Reply with: OK"}],
    )
    assert resp.content[0].text.strip() != ""

results.append(check("Anthropic API reachable", _check_anthropic, skip_if_missing_env="ANTHROPIC_API_KEY"))

def _check_arcgis():
    from src.routing import _get_token
    token = _get_token()
    assert token and len(token) > 10

results.append(check("ArcGIS OAuth2 token fetch", _check_arcgis, skip_if_missing_env="ARCGIS_CLIENT_ID"))

# ── 4. End-to-end pipeline ────────────────────────────────────────────────────
print("\n4. End-to-end pipeline (diagnostic query, SA2 precomputed access)")

def _check_pipeline():
    from src.models import QueryParams
    from src.spatial import load_sa2_access, load_sa2_geometries, build_spatial_context_sa2
    from src.optimiser import diagnose_sa2_coverage

    params = QueryParams(
        mode="diagnostic", region="Western NSW", facility_type="gp_bulk_billing",
        threshold_min=45, pop_min=500,
    )
    access = load_sa2_access()
    sa2 = load_sa2_geometries()
    ctx = build_spatial_context_sa2(params, access, sa2)
    assert len(ctx.demand_points) > 0, "No demand points loaded"

    _, summary = diagnose_sa2_coverage(ctx.demand_points, params.threshold_min, params.facility_type)
    assert 0 <= summary["coverage_pct"] <= 100, f"Coverage out of range: {summary['coverage_pct']}"

    print(f"     SA2s: {len(ctx.demand_points)}, covered population: {summary['covered_population']:,} ({summary['coverage_pct']:.1f}%)")

results.append(check("spatial + SA2 access + optimiser pipeline", _check_pipeline))

def _check_nlp_parse():
    from src.nlp import parse_query, build_tool_schema
    from src.spatial import load_sa2_access, list_phns
    access = load_sa2_access()
    phns = list_phns(access)
    params = parse_query(
        "Which towns in Western NSW with more than 500 people are more than 45 minutes from the nearest GP?",
        tool_schema=build_tool_schema(phns),
        fallback_region="Western NSW",
    )
    assert params.mode == "diagnostic"
    assert params.threshold_min == 45

results.append(check("NLP query parsing (Claude tool use)", _check_nlp_parse, skip_if_missing_env="ANTHROPIC_API_KEY"))

# ── Summary ───────────────────────────────────────────────────────────────────
passed = sum(results)
total = len(results)
print(f"\n{'=' * 40}")
if all(results):
    print(f"All {total} checks passed. Ready for demo.")
else:
    failed = total - passed
    print(f"{failed} of {total} checks failed.")
    sys.exit(1)
