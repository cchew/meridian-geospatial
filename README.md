# Meridian

AI-powered spatial decision support for Australian primary health care planning. Ask plain-English questions about GP coverage gaps; get optimised facility placement recommendations with briefing-quality narrative.

**Flow:** Natural language query → Claude API (NL→params) → [GeoPandas](https://geopandas.org/) + [ArcGIS Network Analyst](https://www.esri.com/en-us/arcgis/products/arcgis-network-analyst/overview) routing → [PuLP](https://coin-or.github.io/pulp/) [MCLP](https://en.wikipedia.org/wiki/Maximum_coverage_location_problem) solver → Claude API (narrative) → [Folium](https://python-visualization.github.io/folium/) map in [Streamlit](https://streamlit.io/)

---

## Modes

**Mode 1 — Diagnostic:** Where are the current coverage gaps?
> *"Which towns in Western NSW with more than 500 people are more than 45 minutes from the nearest bulk-billing GP?"*

**Mode 2 — Prescriptive:** Where should we commission new services?
> *"Where would you place 6 new GP clinics in Western NSW to maximise population coverage within 45 minutes?"*

---

## Limitations

- **Western NSW PHN only.** The region is validated against an allowlist; national generalisation requires data validation across diverse PHN geographies.
- **2021 Census population counts.** Rural population distributions can shift materially over a five-year period.
- **Road network only.** Seasonal road conditions, patient transport availability, and telehealth substitution are not modelled.
- **GP facilities only.** Allied health, specialists, and hospitals are out of scope.
- **Straight-line candidate pre-filter.** Candidate sites are derived using a distance proxy rather than a full travel-time pre-filter; some candidates may be slightly mis-ranked.
- **Uniform coverage objective.** MCLP maximises raw population coverage. It does not weight by health need, disease burden, or socioeconomic vulnerability.
- **DPA as sole need signal.** DPA classification captures GP workforce shortage designation but not demand-side factors such as chronic disease prevalence.
- **No real-time data.** GP locations are a Nov 2025 NHSD snapshot; population figures are 2021 Census.

See [docs/METHODOLOGY.md](docs/METHODOLOGY.md) for full methodological detail.

---

## Requirements

- Python 3.12+
- Anthropic API key
- [ArcGIS Online](https://www.arcgis.com/) account with Network Analyst access (or [OpenRouteService](https://openrouteservice.org/) as fallback)

---

## Setup

### 1. Python environment

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Environment variables

```bash
cp .env.example .env
```

Fill in all values in `.env`:

| Variable | Description |
|---|---|
| `ANTHROPIC_API_KEY` | [Anthropic Console](https://console.anthropic.com/) → API Keys |
| `ARCGIS_CLIENT_ID` | [ArcGIS Developer portal](https://developers.arcgis.com/) → OAuth 2.0 credentials |
| `ARCGIS_CLIENT_SECRET` | Same as above |
| `ROUTING_PROVIDER` | `arcgis` or `ors` |
| `ORS_API_KEY` | [openrouteservice.org](https://openrouteservice.org/) → API key (if using ORS) |

### 3. Download data

Fetches all public datasets (PHN boundaries, GP locations, population localities, DPA shapefiles) into `data/`:

```bash
python scripts/download_data.py
```

Verify integrity after download:

```bash
python scripts/verify_data.py
```

### 4. Pre-compute travel time matrices

Builds an [ArcGIS OD Cost Matrix](https://pro.arcgis.com/en/pro-app/latest/help/analysis/networks/od-cost-matrix-analysis-layer.htm) for all population centre × facility pairs and caches results to `cache/`. Takes a few minutes on first run; subsequent runs use the cache.

```bash
python scripts/precompute_matrix.py
```

---

## Running

```bash
source .venv/bin/activate
streamlit run app.py
```

Opens at [http://localhost:8501](http://localhost:8501).

---

## Demo

### Before the demo

Run the smoke test to validate all integrations:

```bash
python scripts/smoke_test.py
```

Expect 10+ passing checks covering data files, Python dependencies, API connectivity, and an end-to-end pipeline run.

### Demo queries

**Mode 1 — Diagnostic:**
> Which towns in Western NSW with more than 500 people are more than 45 minutes from the nearest bulk-billing GP?

**Mode 2 — Prescriptive:**
> Where would you place 6 new GP clinics in Western NSW to maximise population coverage within 45 minutes?

> Where should the next 2 GP clinics go in Western NSW within 45 minutes, after Ochre Health's 6 recent openings?

---

## Tests

```bash
source .venv/bin/activate
pytest
```

Integration tests (call the Claude API and ArcGIS) are marked `integration` and excluded by default:

```bash
pytest -m integration
```

---

## Project structure

```
.
├── app.py                    # Streamlit entry point
├── requirements.txt
├── src/
│   ├── models.py             # Pydantic query parameter models
│   ├── nlp.py                # Claude API: NL→params + narrative generation
│   ├── optimiser.py          # PuLP MCLP solver
│   ├── routing.py            # ArcGIS / ORS travel time matrix
│   ├── security.py           # Input validation
│   ├── spatial.py            # GeoPandas data loading + spatial joins
│   └── visualisation.py      # Folium + Plotly map builders
├── scripts/
│   ├── download_data.py      # Fetch all public datasets into data/
│   ├── precompute_matrix.py  # Build and cache travel time matrices
│   ├── verify_data.py        # Validate checksums against checksums.sha256
│   ├── smoke_test.py         # Pre-demo integration check
│   └── demo_cli.py           # Run demo queries from the command line
├── tests/
│   ├── conftest.py
│   └── test_*.py             # Unit tests per src module
├── data/                     # Downloaded datasets (gitignored — run download_data.py)
├── cache/                    # Pre-computed matrices (gitignored — run precompute_matrix.py)
└── docs/
    └── METHODOLOGY.md        # Spatial methodology, data sources, model limitations
```

---

## Data sources

All datasets are publicly available from Australian government sources:

| Dataset | Source |
|---|---|
| PHN boundaries | [AIHW](https://www.aihw.gov.au/reports-data/myhospitals/sectors/primary-health-networks) |
| Population localities | [ABS](https://www.abs.gov.au/statistics/standards/australian-statistical-geography-standard-asgs-edition-3/jul2021-jun2026) (ASGS + ERP) |
| GP / facility locations | [Health Workforce Dataset](https://hwd.health.gov.au/) |
| Distribution Priority Areas | [Department of Health, Disability and Ageing](https://www.health.gov.au/topics/doctors-and-specialists/what-we-do/distribution-priority-areas) |
