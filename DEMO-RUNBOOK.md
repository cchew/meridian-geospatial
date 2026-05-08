# Meridian — Demo Runbook

## Prerequisites

All of these must be in place before running any demo. They only need to be done once (or after data updates).

```bash
cd projects/meridian-geospatial/repo
source .venv/bin/activate
```

**`.env` must contain:**
```
ANTHROPIC_API_KEY=...
ARCGIS_CLIENT_ID=...
ARCGIS_CLIENT_SECRET=...
```

### First-time setup (one-time only)

```bash
# 1. Download all public datasets and generate checksums
python scripts/download_data.py

# 2. Pre-compute and cache ArcGIS travel time matrices for all three demo queries
#    This calls ArcGIS API (~1-2 min). Results are cached — the live demo never calls ArcGIS.
python scripts/precompute_matrix.py
```

---

## Before Every Demo

Run the smoke test. It validates all integrations and exits with a clear pass/fail.

```bash
source .venv/bin/activate
python scripts/smoke_test.py
```

**Expected output (all passing):**
```
1. Data files
  ✓ required data files present
  ✓ data file checksums valid
  ✓ cached travel time matrices present and readable

2. Python dependencies
  ✓ import geopandas
  ✓ import anthropic
  ✓ import streamlit
  ✓ import plotly
  ✓ import pulp
  ✓ import pyarrow
  ✓ import shapely
  ✓ import fiona

3. API connectivity
  ✓ Anthropic API reachable
  ✓ ArcGIS OAuth2 token fetch

4. End-to-end pipeline (diagnostic query, uses cache)
  ✓ spatial + routing + optimiser pipeline
  ✓ NLP query parsing (Claude tool use)

All N checks passed. Ready for demo.
```

Fix any `✗` failures before proceeding. `○` (skipped) means the env var wasn't set — check `.env`.

### Then start the app

```bash
streamlit run app.py
```

App opens at `http://localhost:8501`.

---

## Demo Script

### Mode 1 — Diagnostic

Select **Mode 1: Diagnostic**, click the suggested query button, then click **Analyse**.

> *Which towns in Western NSW with more than 500 people are more than 45 minutes from the nearest bulk-billing GP?*

Shows: coverage gap map, population metrics, town-level briefing note.

### Mode 2 — Prescriptive (query 1)

Select **Mode 2: Prescriptive**, click the first suggested query button.

> *Where would you place 6 new GP clinics in Western NSW to maximise population coverage within 45 minutes?*

Shows: optimal placement map, before/after coverage improvement. Compare proposed sites against Ochre Health's actual 2024 deployments.

### Mode 2 — Prescriptive (query 2)

Click the second suggested query button.

> *Where should the next 2 GP clinics go in Western NSW within 45 minutes, after Ochre Health's 6 recent openings?*

Shows: forward planning — where to invest next given the current state of deployments.

---

## After the Demo

Stop the Streamlit server with `Ctrl+C`.

No cleanup required — the travel time cache persists for next time.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Smoke test fails on checksums | Data file modified or corrupted | Re-run `python scripts/download_data.py` |
| Smoke test fails on cache | Matrices not pre-computed | Re-run `python scripts/precompute_matrix.py` |
| Smoke test fails on Anthropic API | API key missing or invalid | Check `ANTHROPIC_API_KEY` in `.env` |
| Smoke test fails on ArcGIS token | Credentials missing or expired | Check `ARCGIS_CLIENT_ID` / `ARCGIS_CLIENT_SECRET` in `.env` |
| App fails to load spatial data | Data directory missing | Run `python scripts/download_data.py` |
| Analysis hangs on routing step | Cache miss + ArcGIS API slow | Pre-warm with `python scripts/precompute_matrix.py` |
| Map shows no region outline | Empty demand points after filter | Lower `pop_min` threshold in the query |
