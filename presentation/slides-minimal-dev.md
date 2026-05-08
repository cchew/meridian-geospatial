---
marp: true
theme: default
size: 16:9
paginate: true
---

<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&family=JetBrains+Mono:wght@400&display=swap');

:root {
  --color-background: #ffffff;
  --color-foreground: #1c1c1c;
  --color-heading: #111111;
  --color-muted: #888888;
  --color-rule: #e8e8e8;
  --color-accent: #0066cc;
  --color-highlight: #fff3b0;
  --font-default: 'Inter', 'Segoe UI', system-ui, sans-serif;
  --font-mono: 'JetBrains Mono', 'Consolas', monospace;
}

section {
  background-color: var(--color-background);
  color: var(--color-foreground);
  font-family: var(--font-default);
  font-weight: 300;
  box-sizing: border-box;
  padding: 56px 72px 48px;
  font-size: 21px;
  line-height: 1.6;
}

section::after {
  font-size: 13px;
  color: var(--color-muted);
  font-family: var(--font-default);
  font-weight: 300;
}

h1, h2, h3 {
  font-family: var(--font-default);
  margin: 0;
  padding: 0;
  color: var(--color-heading);
}

h1 { font-size: 52px; font-weight: 300; line-height: 1.2; letter-spacing: -0.02em; }
h2 {
  font-size: 34px; font-weight: 400; letter-spacing: -0.01em;
  margin-bottom: 24px; padding-bottom: 12px; border-bottom: 1px solid var(--color-rule);
}
h3 { font-size: 20px; font-weight: 500; color: var(--color-accent); margin-top: 22px; margin-bottom: 6px; }

ul, ol { padding-left: 22px; margin: 0; }
li { margin-bottom: 8px; color: var(--color-foreground); }
li strong { font-weight: 500; color: var(--color-heading); }
p { margin: 0 0 12px; }

code {
  font-family: var(--font-mono);
  font-size: 0.85em;
  background-color: #f4f4f4;
  color: #333;
  padding: 2px 6px;
  border-radius: 3px;
}

pre {
  background-color: #f6f8fa;
  border: 1px solid var(--color-rule);
  border-radius: 4px;
  padding: 14px 18px;
  font-family: var(--font-mono);
  font-size: 17px;
  line-height: 1.45;
  overflow: hidden;
}

pre code { background: none; padding: 0; border-radius: 0; }

.path {
  font-family: var(--font-mono);
  font-size: 14px;
  color: var(--color-muted);
  margin-bottom: 6px;
}

.callout {
  border-left: 3px solid var(--color-accent);
  padding: 8px 16px;
  margin-top: 14px;
  font-size: 0.92em;
  color: #333;
  background: #f7fafd;
}

.hl {
  background-color: var(--color-highlight);
  padding: 0 2px;
  border-radius: 2px;
}

table { width: 100%; border-collapse: collapse; font-size: 0.88em; font-weight: 300; margin-top: 8px; }
th {
  font-weight: 500; font-size: 0.82em; color: var(--color-muted);
  text-transform: uppercase; letter-spacing: 0.05em;
  padding: 6px 12px; border-bottom: 1px solid var(--color-rule); text-align: left;
}
td { padding: 8px 12px; border-bottom: 1px solid var(--color-rule); vertical-align: top; }

section.lead {
  display: flex; flex-direction: column; justify-content: center;
  padding: 72px; border-left: 3px solid var(--color-heading);
}
section.lead h1 { font-size: 56px; font-weight: 300; letter-spacing: -0.03em; margin-bottom: 20px; line-height: 1.15; }
section.lead p { font-size: 19px; color: var(--color-muted); font-weight: 300; margin: 0; line-height: 1.6; }

section.break {
  display: flex; flex-direction: column; justify-content: center;
  padding: 72px; background-color: var(--color-heading); color: #ffffff;
}
section.break h1 { font-size: 46px; font-weight: 300; color: #ffffff; letter-spacing: -0.02em; margin-bottom: 14px; }
section.break p { font-size: 19px; color: rgba(255,255,255,0.55); margin: 0; }

section.appendix h2 { color: var(--color-muted); font-size: 26px; border-bottom-color: #eeeeee; }
</style>

<!-- _class: lead -->
<!-- _paginate: false -->

# Meridian — Developer Walkthrough

<br/>

Geospatial data pipeline and decision support

Ching Chew · April 2026

<br/>

![w:200](screenshots/qr.png)

<!-- note:
30 seconds. One line: "Two-mode spatial decision support tool. NL in, optimised facility placement out. Code and presso public — scan QR."
Skip the subtitle.
-->

---

## The Problem

A decision maker asks: *"Where do we put two new GP clinics in Western NSW?"*

- Today: request GIS expert, output lives in an email attachment
- What-ifs require a new request each time
- The bottleneck isn't the analysis; it's translating request to specialised tool, then interpreting results from the tool.

<div class="callout">
  Goal: compress that to seconds, with a defensible quantitative baseline a non-GIS user can drive themselves.
</div>

<!-- note:
60 seconds max. Don't dwell. Devs care about the build, not the framing.
Land: "the bottleneck isn't the analysis, it's the translation layer." That's the thesis the architecture follows.
PHN = Primary Health Network, funded to coordinate primary care in region.
There are 2 parts: how do we calculate GP coverage shortage, and how do we add 2 new clinics to maximise coverage. Let's dive into first part.
-->

---

<!-- _class: break -->

![bg contain](screenshots/mode1-coverage-map.png)

<!-- note:
"That's the kind of answer we want — coverage gap diagnostic. Let's run it, then dig into how."
Bridge straight into the live demo.
-->

---

<!-- _class: break -->
<!-- _paginate: false -->

# Live Demo

Mode 1 — Coverage Gap Diagnostic

<!-- note:
Click suggested query: "Which towns in Western NSW with more than 500 people are more than 45 minutes from the nearest bulk-billing GP?"
Point at: parsed params in sidebar, latency, structured-params discipline.
4.5 minutes. Don't narrate every UI element.
After this slide the audience has the result in their head — every later slide refers back to it.
-->

---

## Data

Five public datasets.

| Dataset | Source | Format | Used for |
|---|---|---|---|
| PHN boundaries | AIHW | GeoJSON | Region clip, 31 PHNs |
| Population localities | ABS UCL 2021 + Census G01 | GeoPackage + CSV | Demand points + populations |
| GP locations | Geoscience Australia NHSD | GeoJSON (REST) | Existing facilities |
| Distribution Priority Areas | DHDA | Shapefile | Workforce-shortage flag |
| ARIA+ remoteness | AIHW / ABS | GeoJSON | Narrative context |

<div class="callout">
  Different formats, different coordinate systems, different ID conventions. Most of the work in a geospatial pipeline is reconciling these <em>before</em> any analysis runs.
</div>

<!-- note:
~2 minutes. Three things to land:
  1. Public data — patient data never in scope.
  2. The variety is the point — GeoJSON, GeoPackage, CSV, Shapefile, REST. There is no "the geospatial format".
  3. The ID-and-CRS reconciliation is where time goes. Concrete example coming next slide — UCL prefix bug.
-->

---

## Architecture — Data Pipeline

```
   Source datasets  (5 sources · 4 formats)
        │
        ▼
   scripts/download_data.py         — fetch + write SHA-256 manifest
        │
        ▼
   src/spatial.py · load_all_data()
        ├── verify_checksums()                       (security.py)
        ├── PHN boundaries           → GeoDataFrame
        ├── UCL localities + Census G01 join         (CSV merge ↓)
        ├── NHSD GP locations        → filter "General practice service"
        └── DPA shapefile            → GeoDataFrame
        │
        ▼
   Reproject all → EPSG:4326 (WGS84)
        │
        ▼
   ArcGIS OD pre-compute            (offline, one-time per snapshot)
        │
        ▼
   matrix.to_parquet(cache_path)    ── routing.py
        │
        ▼
   In memory: @st.cache_resource    ·  On disk: cache/*.parquet
```

<!-- note:
~2 minutes. The map for the data half. Three beats:
  1. Source datasets collapse into four GeoDataFrames + a Census join + a precomputed OD (origin-destination) matrix on disk.
  2. Checksum verification is real — same file every run, or fail loudly.
  3. The OD pre-compute is the single most expensive thing in the system. Done once, parquet on disk, runtime only ever reads.

The runtime code never re-fetches a source dataset or calls the routing API.
-->

---

## Data pipeline code — Census join

<div class="path">src/spatial.py · L16–31</div>

```python
localities = gpd.read_file(DATA_DIR / "localities.gpkg", layer=_UCL_LAYER)
pop = pd.read_csv(pop_path, usecols=["UCL_CODE_2021", "Tot_P_P"], dtype=str)

# Census CSV prefixes codes with "UCL" (e.g. "UCL101001");
# GeoPackage uses bare codes
pop["UCL_CODE_2021"] = pop["UCL_CODE_2021"].str.removeprefix("UCL")
pop["Tot_P_P"] = pd.to_numeric(pop["Tot_P_P"], errors="coerce").fillna(0).astype(int)
pop = pop.rename(columns={"Tot_P_P": "population"})

localities = localities.merge(pop, on="UCL_CODE_2021", how="left")
localities["population"] = localities["population"].fillna(0).astype(int)
```

<div class="callout">
  ABS Census prefixes the literal string <code>"UCL"</code>; the boundary GeoPackage doesn't. <br/>Three characters — a merge that silently produces zero matches if you miss it.
</div>

<!-- note:
~75 seconds. The single most representative data-pipeline code in the repo.
  1. removeprefix("UCL") — the actual bug. We discovered it because population was zero everywhere.
  2. fillna(0) on both sides — defensive: localities without population data still appear in the analysis with population zero, not NaN.

This is the kind of bug that makes geospatial pipelines slow to build. Worth flagging openly.
-->

---

## Architecture — UI Runtime (per-query)

```
   User input (Streamlit)
        │
        ▼
   parse_query()                    ── Claude tool use, forced
        │   QueryParams (typed, bounds-checked)
        ▼
   build_spatial_context()           ── GeoPandas
        ├── clip to PHN                  • drops "Remainder of …"
        ├── locality_name alias          • polygon → centroid
        └── derive candidates  [Mode 2]  • DPA + straight-line proxy
        │
        ▼
   get_travel_time_matrix()          ── cache hit (parquet read)
        │   demand × facility, minutes
        ▼
   solve_mclp()              [Mode 2] ── PuLP / CBC
        │
        ▼
   generate_narrative()              ── Claude, structured prompt only
        │
        ▼
   Plotly + Streamlit
```

<!-- note:
~1.5 minutes. Bridge: "we've seen what runs offline; now the user-facing flow that drives it."
Two beats:
  1. The model never reasons spatially — it fills a typed form at the top, writes from a typed context at the bottom. Called at start and end.
  2. Mode 2 = Mode 1 + two gated steps. Same pipeline, two outcomes. We'll see Mode 1 path code now; Mode 2 additions after Demo 2.
-->

---

## Tool-use schema

<div class="path">src/nlp.py · L24–59</div>

```python
_PARSE_TOOL = {
    "name": "extract_query_params",
    "input_schema": {
        "type": "object",
        "properties": {
            "mode": {"type": "string",
                     "enum": ["diagnostic", "prescriptive"]},
            "region": {"type": "string"},
            "facility_type": {"type": "string", "enum": ["gp"]},
            "threshold_min": {"type": "integer"},
            "k": {"type": "integer"},
            "pop_min": {"type": "integer"},
        },
        "required": ["mode", "region", "facility_type",
                     "threshold_min"],
    },
}
```

Six fields. Enums where the answer space is closed. No free-form spatial reasoning anywhere downstream.

<!-- note:
"This is the contract. Everything below this line in the call stack only ever sees these six fields. The model never reasons about geography — it fills a form."
-->

---

## Forced tool call + post-validation

<div class="path">src/nlp.py · L83–109   ·   src/models.py · L33–50</div>

```python
response = _client.messages.create(
    model=MODEL, max_tokens=512,
    system=_PARSE_SYSTEM, tools=[_PARSE_TOOL],
    tool_choice={"type": "any"},          # ← force tool call
    messages=[{"role": "user", "content": user_input}],
)
tool_use = next(b for b in response.content if b.type == "tool_use")
return QueryParams(**tool_use.input)      # ← raises if out of bounds
```

```python
# QueryParams.__post_init__ — defence in depth
if self.region not in ALLOWED_REGIONS: raise ValidationError(...)
if not 10 <= self.threshold_min <= 120: raise ValidationError(...)
if self.k is not None and not 1 <= self.k <= 10: raise ValidationError(...)
```

<div class="callout">
  Two checkpoints: schema at the model boundary, dataclass <code>__post_init__</code> at the application boundary. <br/>The schema lets <code>threshold_min: 9999</code> through; the dataclass rejects it.
</div>

<!-- note:
"tool_choice any" forces a tool call — no prose path. If Claude refuses, ParseError fires.
Two error types in the dataclass — ParseError (no tool call) and ValidationError (out of bounds) — drive distinct UX messages in app.py. Mention briefly; don't dwell.
-->

---

## PHN clip + locality filter

<div class="path">src/spatial.py · L62–80</div>

```python
phn_boundary = phn[phn["PHN_NAME"] == params.region]

demand = gpd.clip(localities, phn_boundary)
demand = demand[~demand["UCL_NAME_2021"].str.startswith("Remainder of")]
if params.pop_min is not None:
    demand = demand[demand["population"] >= params.pop_min].copy()

# Routing wants points; localities are polygons → projected centroid
if demand.geometry.geom_type.isin(["Polygon", "MultiPolygon"]).any():
    demand["geometry"] = (
        demand.geometry.to_crs(epsg=7855).centroid.to_crs(epsg=4326)
    )
```

<div class="callout">
  Two non-obvious bits: drop ABS "Remainder of …" residuals (they're not real places), and reproject to GDA2020/MGA-55 before taking centroids — taking centroids in WGS84 is a common silent bug.
</div>

<!-- note:
The "Remainder of" filter is from inspecting the data — those are residual aggregates, not towns.
EPSG:7855 = GDA2020 / MGA Zone 55, the right projected CRS for NSW. Centroids in lat/lon are wrong by enough to matter at this scale.
-->

---

## Cache-first routing

<div class="path">src/routing.py · L186–229</div>

```python
def compute_cache_key(demand, facilities, threshold_min) -> str:
    demand_coords   = sorted([(round(g.x,5), round(g.y,5))
                              for g in demand.geometry])
    facility_coords = sorted([(round(g.x,5), round(g.y,5))
                              for g in facilities.geometry])
    key = str(demand_coords) + str(facility_coords) + str(threshold_min)
    return hashlib.sha256(key.encode()).hexdigest()[:16]

def get_travel_time_matrix(demand, facilities, threshold_min, ...):
    cache_path = cache_dir / f"{compute_cache_key(...)}.parquet"
    if cache_path.exists():
        return CoverageMatrix(pd.read_parquet(cache_path), ...)
    # else: ArcGIS OD or ORS, then matrix.to_parquet(cache_path)
```

<div class="callout">
  Sorted, rounded coords + threshold → deterministic key. <br/>Demo never calls the API. Same query → same parquet → same map.
</div>

<!-- note:
Three things to land:
  1. Sorted + rounded — order-independent and tolerant of float jitter.
  2. Threshold is part of the key (different thresholds = different parquet).
  3. The demo runs entirely from disk. Reliability over freshness, deliberately.
-->

---

## Narrative — structured prompt, no raw user text

<div class="path">src/nlp.py · L112–131</div>

```python
def generate_narrative(ctx: NarrativeContext) -> str:
    # Build structured prompt — raw user text never reaches this function
    lines = [
        f"Region: {ctx.region}",
        f"Mode: {ctx.mode}",
        f"Travel time threshold: {ctx.threshold_min} minutes",
        f"Total population analysed: {ctx.total_population:,}",
        f"Population within threshold: {ctx.covered_population:,} "
        f"({ctx.coverage_pct:.1f}%)",
        f"Towns lacking coverage: {', '.join(ctx.uncovered_towns)}",
    ]
    # ... + Mode 2 prescriptive lines if relevant
    structured_input = "\n".join(lines)
```

<div class="callout">
  Output layer takes a typed <code>NarrativeContext</code>, not the user's question. <br/>Prompt-injection surface for the second LLM call is zero — there is no user text in the prompt.
</div>

<!-- note:
Two LLM calls, two different threat models:
  - parse_query: user input goes in, but tool schema constrains the output shape.
  - generate_narrative: no user input goes in at all.
Defence-in-depth.
-->

---

<!-- _class: break -->

![bg contain](screenshots/mode2-proposed-sites.png)

<!-- note:
Same architecture, different solver mode. "Now we're placing facilities, not diagnosing gaps."
-->

---

<!-- _class: break -->
<!-- _paginate: false -->

# Live Demo

Mode 2 — Facility Optimisation

<!-- note:
Click: "Where would you place 6 new GP clinics in Western NSW to maximise population coverage within 45 minutes?"
Point out: k=6, mode=prescriptive in parsed params. MCLP runs in seconds.
Land: "About 10 seconds. Equivalent GIS request: days."
-->

---

## MCLP — what just ran

**Maximal Coverage Location Problem** (Church & ReVelle, 1974)

Given **k** facilities to place, find the locations that maximise total population within travel-time threshold of at least one facility.

```
Decision variables
   xⱼ ∈ {0,1}    candidate site j is selected
   yᵢ ∈ {0,1}    demand point i is covered

Maximise      Σᵢ  pᵢ · yᵢ              (covered population)
subject to    Σⱼ  xⱼ ≤ k               (budget)
              yᵢ ≤ Σ_{j ∈ Cᵢ} xⱼ      (i covered ⇒ a covering site selected)
              xⱼ, yᵢ ∈ {0,1}

   pᵢ = population at i
   Cᵢ = candidates within threshold travel-time of i
```

<div class="callout">
  Exact integer program. At PHN scale (~50 demand × ~100 candidates) returns a provably optimal solution in seconds. <br/>No metaheuristics, no ML.
</div>

<!-- note:
~1.5 minutes. The math form of what they just saw run.
The point: the algorithm is 50 years old. The contribution is the natural-language interface that makes it accessible.
Next slide: where Mode 2 differs from Mode 1 at the system level. Then we'll walk the two specific code blocks.
-->

---

## Mode 2 — what's different in the call graph

<div class="path">src/spatial.py · L91–92   ·   app.py · L122–145</div>

```python
# spatial.py — candidate derivation only runs in Mode 2
if params.mode == "prescriptive":
    candidates = _derive_candidates(params, demand, facilities, dpa)
```

```python
# app.py — destinations widen, then solver runs
if params.mode == "prescriptive":
    all_facilities = gpd.GeoDataFrame(
        pd.concat([ctx.existing_facilities, ctx.candidates], ...))
    cm = get_travel_time_matrix(ctx.demand_points, all_facilities, ...)
else:
    cm = get_travel_time_matrix(ctx.demand_points, ctx.existing_facilities, ...)

if params.mode == "prescriptive" and params.k:
    opt_result = solve_mclp(ctx.demand_points, ctx.candidates, ...)
```

<div class="callout">
  Mode 2 = Mode 1 + three things: derive candidates, widen destinations, run solver. <br/>Three <code>if</code> blocks.
</div>

<!-- note:
~1.5 minutes. The roadmap for the next two slides.
"Three if blocks. Two of them point at code we haven't walked yet — candidate derivation, then the solver. Coming up next."
This isn't two systems pretending to be one. It's one system with three mode-gated steps. Easy to extend.
-->

---

## Candidate derivation

<div class="path">src/spatial.py · L101–146</div>

```python
# 1 minute @ ~60 km/h ≈ 1 km — straight-line proxy
proxy_distance_m = params.threshold_min * 1000

near_facility = demand_proj.geometry.apply(
    lambda g: facilities_proj.distance(g).min() <= proxy_distance_m
)
candidates_proj = demand_proj[~near_facility].copy()

# DPA priority flag (DHDA workforce-shortage classification)
candidates_proj["dpa_priority"] = candidates_proj.geometry.apply(
    lambda g: dpa_proj.intersects(g).any()
)

# Sort: DPA first, then population descending
candidates_proj = candidates_proj.sort_values(
    ["dpa_priority", "population"], ascending=[False, False]
)
```

<div class="callout">
  The single most approximate step in the pipeline. Straight-line ≠ road network. <br/>Road validation happens later via the OD matrix — only on shortlisted candidates.
</div>

<!-- note:
The slide where you earn dev respect. Name the approximation explicitly — straight-line first, road network later. The reason is API cost: full OD on all localities × all candidates would be huge. Pre-filter, then validate.
The DPA flag is a real DHDA dataset, not invented.
-->

---

## MCLP code

<div class="path">src/optimiser.py · L81–99</div>

```python
prob = LpProblem("MCLP", LpMaximize)
x = [LpVariable(f"x_{j}", cat="Binary") for j in range(n_candidates)]
y = [LpVariable(f"y_{i}", cat="Binary") for i in range(n_demand)]

prob += lpSum(pops[i] * y[i] for i in range(n_demand))   # objective
prob += lpSum(x) <= k                                    # budget

for i, did in enumerate(demand_ids):
    if already_covered_by_existing(did):
        prob += y[i] == 1
    elif covered_by[did]:
        prob += y[i] <= lpSum(x[j] for j in covered_by[did])
    else:
        prob += y[i] == 0

prob.solve(PULP_CBC_CMD(msg=0))
```

<!-- note:
LP = linear programming. Algebra, how to min/max given budget ($5, apples, oranges)

Connect line-by-line back to the math slide:
  - x_j ↔ LpVariable(f"x_{j}", Binary)
  - y_i ↔ LpVariable(f"y_{i}", Binary)
  - objective ↔ lpSum(pops[i] * y[i] ...)
  - budget ↔ lpSum(x) <= k
PuLP/CBC, exact solve. Provably optimal at PHN scale.

CBC (Coin-or Branch and Cut), for MCLP up to ~1,000 points.
-->

---

<!-- _class: break -->

![bg contain](screenshots/before-after-stats.png)

<!-- note:
Read the headline coverage delta. One line: "Specialist judgment still applies on top — but from a quantitative baseline, not from scratch."
30 seconds. Don't dwell.
-->

---

## Lessons + Limitations

- **Uniform coverage objective is a known limit.** MCLP weights by population alone, not health need, disease burden, or socioeconomic vulnerability. Demand-weighted variant is next.
- **Candidate derivation is approximate.** Straight-line pre-filter, road validation only on the shortlist.
- **Missing local context.** Does not incorporate specialist (e.g. PHN) reports and news that tell us whether a quantitative gap is already being worked on, has been tried and failed, is contested or is being read differently.
- **Data sourcing was harder than the solver.** ABS Census join, NHSD MapServer filter, DPA shapefile — each had a "gotcha".

<!-- note:
Don't rush it. ~3 minutes.
"I'm showing you a pattern and being straight about where it ends."
The key is the pattern. Demo in current state has severe limitations.
-->

---

## Forward — Demand-weighted MCLP

The solver formulation is identical:

```python
# current
prob += lpSum(pops[i] * y[i] for i in range(n_demand))

# extended
prob += lpSum(demand_scores[i] * y[i] for i in range(n_demand))
```

Composite `demand_scores[i]`:

- **PPH** (Potentially Preventable Hospitalisations, AIHW) — unmet primary care signal
- **DPA** classification — DHDA workforce-shortage signal (already loaded)
- **Chronic disease prevalence** (AIHW) — load factor

<div class="callout">
  Same skeleton, richer demand model, the narrative layer gets richer evidence to work with.
</div>

<!-- note:
~90 seconds. The point is the architecture absorbs the extension cleanly. One enum extension upstream, one term substitution in the solver. That's the whole change.
-->

---

## Forward — National Scale

Two engineering blockers (both solvable):

| Blocker | Mitigation |
|---|---|
| Routing API cost — travel distance for 2,400+ localities | Pre-compute once, refresh quarterly, parquet — pattern in demo, just bigger |
| PHN boundary edge cases — localities straddle SA3s | Centroid allocation today; per-edge handling for boundary towns |

<!-- note:
~90 seconds. "Engineering problems, not research problems" is the frame. Both have clear solutions; both fit the existing architecture.
-->

---

## Close

You have learnt how to design and build a geospatial data pipeline and geospatial decision support tool.

<br/>
You can also apply this pattern to any complex expert system:

**NL question → typed params → expert system → NL response.**

Reusable anywhere a domain tool sits behind a translation layer.

<br/>

- Thank you for your time
- Feedback: Teams, LinkedIn or via email
- Any questions?

<!-- note:
~30 seconds. Take questions.

I am still learning this myself.
-->
