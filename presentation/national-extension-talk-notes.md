# Meridian: National Extension — Talk Notes

## What changed (and why)

| Aspect | Single-PHN demo | National version | Reason |
|---|---|---|---|
| Demand unit | UCL (built-up areas only) | SA2 (exhaustive) | UCL excludes ~15% dispersed rural population |
| Mode 1 routing | Live ArcGIS OD Cost Matrix | Filipcikova SA2 weighted averages | Pre-computed national OSRM, peer-reviewed, CC BY |
| Cross-boundary | Clipped to PHN — Wilcannia 120 min | National OSRM — Wilcannia 63 min | Real access is jurisdiction-blind |
| Mode 2 routing | ArcGIS for full demand × all facilities | ArcGIS for candidate × demand only | Smaller call volume; existing-coverage read off Filipcikova |
| PHN membership | Polygon intersection | DHDA official concordance | No slivers, AIHW-aligned |

## Two figures

- `docs/figures/ucl-vs-sa2.png` — the conceptual "why"
- `docs/figures/cross-validation-outliers.png` — the empirical "what"

## Caveats to surface

1. Bulk-billing GP locations in Filipcikova are public-directory derived (1,282 listings) — under-counts unadvertised practices.
2. SA2 weighted averages smooth within-area variation. Mesh Block file available for finer drill-down.
3. Mode 1 numbers from the national version are not directly comparable to the single-PHN demo numbers.

## What stays the same

- Two-mode tool: diagnostic + prescriptive.
- Claude tool use for NL → params and narrative generation.
- PuLP MCLP solver for facility location.
- Streamlit + Plotly for interface.
