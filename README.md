# Meridian

*Personal project. Views and code are my own and do not represent any past or current employer.*

AI-powered spatial decision support for Australian primary health care planning. Ask plain-English questions about GP coverage gaps; get optimised facility placement recommendations with briefing-quality narrative.

![Mode 1 - Diagnostic](presentation/screenshots/mode1-coverage-map.png)

**Flow:** Natural language query → Claude API (NL→params) → [GeoPandas](https://geopandas.org/) + [Filipcikova et al. 2026](https://doi.org/10.25855/uq-f9a2d9ab-d7dc-4862-a8e5-5e9d2ff26474) precomputed access (Mode 1) / [OpenRouteService](https://openrouteservice.org/) or [ArcGIS](https://www.esri.com/en-us/arcgis/products/arcgis-network-analyst/overview) routing (Mode 2) → [PuLP](https://coin-or.github.io/pulp/) [MCLP](https://en.wikipedia.org/wiki/Maximum_coverage_problem) solver → Claude API (narrative) → [Plotly](https://plotly.com/) map in [Streamlit](https://streamlit.io/)

---

## Modes

**Mode 1 — Diagnostic:** Where are the current coverage gaps?
> *"Which towns in Western NSW with more than 500 people are more than 45 minutes from the nearest bulk-billing GP?"*

**Mode 2 — Prescriptive:** Where should we commission new services?
> *"Where would you place 6 new GP clinics in Western NSW to maximise population coverage within 45 minutes?"*

---

## National Version

Meridian now generalises to all 31 Australian PHNs. The national version differs methodologically from the original single-PHN demo:

- Demand unit: **SA2** (replaces UCL; captures dispersed rural population that UCL excludes by construction)
- Mode 1 travel times: **Filipcikova et al. 2026** national OSRM dataset (replaces live ArcGIS routing; fixes cross-boundary clipping)
- Mode 2 routing: ArcGIS / OpenRouteService for candidate × demand only (~5,000 pairs/PHN)
- PHN ↔ SA2 membership: official DHDA concordance file (replaces polygon intersection)

Mode 1 numbers are not directly comparable to the original single-PHN demo numbers. See [docs/METHODOLOGY.md](docs/METHODOLOGY.md) for the methodological reasoning and [docs/figures/validation-output.md](docs/figures/validation-output.md) for the cross-validation evidence.

```bash
python scripts/download_data.py     # one-off
python scripts/precompute_matrix.py # one-off; ~30 minutes for all 31 PHNs
streamlit run app.py
```

The PHN selectbox in the app drives all queries. Demo queries reflow to the selected PHN automatically.

---

## Limitations

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
- [OpenRouteService](https://openrouteservice.org/) API key (free tier) **or** [ArcGIS Online](https://www.arcgis.com/) account with Network Analyst access — for Mode 2 prescriptive only; Mode 1 uses precomputed data with no routing calls

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
| `ROUTING_PROVIDER` | `ors` (default) or `arcgis` |
| `ORS_API_KEY` | [openrouteservice.org](https://openrouteservice.org/) → API key (free tier sufficient) |
| `ARCGIS_CLIENT_ID` | [ArcGIS Developer portal](https://developers.arcgis.com/) → OAuth 2.0 credentials (if using ArcGIS) |
| `ARCGIS_CLIENT_SECRET` | Same as above |

Mode 1 (diagnostic) requires no routing credentials — it uses the precomputed Filipcikova dataset. Only Mode 2 (prescriptive) calls the routing provider.

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

Builds Mode 2 candidate × demand travel matrices for all 31 PHNs and caches results to `cache/`. Requires a routing provider (ORS or ArcGIS). Takes ~30 minutes on first run; subsequent runs skip already-cached PHNs.

```bash
python scripts/precompute_matrix.py          # all 31 PHNs
python scripts/precompute_matrix.py --phn "Western NSW"  # single PHN smoke test
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
| PHN boundaries | [data.gov.au](https://data.gov.au/data/dataset/phn-boundaries-used-by-the-nbra) |
| Population localities | [ABS](https://www.abs.gov.au/statistics/standards/australian-statistical-geography-standard-asgs-edition-3/jul2021-jun2026) (ASGS + ERP) |
| GP practice locations | [Geoscience Australia NHSD](https://ecat.ga.gov.au/geonetwork/srv/api/records/1d95ca95-8bd7-4f25-835f-d33c0219435e) |
| Distribution Priority Areas | [Department of Health, Disability and Ageing](https://www.health.gov.au/topics/doctors-and-specialists/what-we-do/distribution-priority-areas) |
