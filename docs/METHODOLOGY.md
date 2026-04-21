# Meridian: AI-Assisted Spatial Decision Support for Rural GP Coverage Planning

## Overview

Meridian is a prototype spatial decision support tool demonstrating how natural language interfaces can make established location optimisation methods accessible to non-technical health policy stakeholders. Applied to the Western NSW Primary Health Network (PHN), it combines ABS population data, Geoscience Australia facility records, government workforce classification layers, and ArcGIS Online network routing with a Maximal Coverage Location Problem (MCLP) solver [1] to identify GP service gaps and recommend optimal placement for new facilities.

## Problem Context

Western NSW PHN — the largest Australian PHN by geography (over 433,000 km²), with a population of over 310,000 — was selected because it combines severe, documented GP workforce shortages with a real-world validation baseline. The 2022 NSW Parliamentary Inquiry into *Health Outcomes and Access to Health and Hospital Services in Rural, Regional and Remote NSW* found workforce shortages "at critical levels" in a number of named towns [2]; a 2024 progress report confirms ongoing remediation [3]. Ochre Health's subsequent deployment of six medical centres across the region (Bourke, Brewarrina, Collarenebri, Coonamble, Lightning Ridge, Walgett) [5] provides the primary validation reference for this analysis.

## Data Sources

| Dataset | Source | Vintage | Format |
|---|---|---|---|
| PHN boundaries | AIHW via data.gov.au [4] | 2023 edition | GeoJSON |
| Population — Urban Centres and Localities (UCL) | ABS ASGS Edition 3 [6] | 2021 Census (G01) | GeoPackage |
| GP practice locations | Geoscience Australia NHSD [7] | Nov 2025 snapshot | GeoJSON |
| Distribution Priority Areas (DPA) | Australian Government DHDA [8] | Current | Shapefile |

SHA-256 checksums of all data files are committed to the repository and verified at application startup.

## Methodology

### Mode 1: Accessibility Diagnosis

Travel time from each population locality to the nearest existing GP practice is resolved via the ArcGIS Online Origin-Destination Cost Matrix REST service (road network, drive time), with OpenRouteService available as an alternative provider via environment configuration. UCL polygon boundaries are converted to centroids prior to routing. A locality is classified as *uncovered* if its minimum travel time to any existing GP exceeds the travel time threshold specified in the query. All routing matrices are pre-computed and cached to disk prior to demonstration; the routing API is not called at query time.

### Mode 2: Facility Location Optimisation

In both modes, demand points are filtered by a population minimum specified in the query; the same threshold applies to the candidate pool in Mode 2. Candidate sites are localities within the PHN boundary that have no existing GP within a straight-line distance proxy (1 km per minute of travel threshold, assuming 60 km/h average rural road speed — e.g. 45 km for a 45-minute threshold), ranked by DPA classification then population. The population minimum is user-specified in both modes; the canonical demo queries use 500 for Mode 1 and 1,000 for Mode 2, reflecting different policy questions rather than a methodological distinction.

The optimisation objective is the Maximal Coverage Location Problem (MCLP) [1]:

**Maximise:** &Sigma;<sub>i</sub> p<sub>i</sub> y<sub>i</sub>

**Subject to:**
- &Sigma;<sub>j</sub> x<sub>j</sub> = k
- y<sub>i</sub> &le; &Sigma;<sub>j &isin; N<sub>i</sub></sub> x<sub>j</sub> &nbsp; &forall;i
- x<sub>j</sub>, y<sub>i</sub> &isin; {0, 1}

where p<sub>i</sub> is the population of demand point i; y<sub>i</sub> = 1 if demand point i is covered; x<sub>j</sub> = 1 if candidate site j is selected; N<sub>i</sub> is the set of candidate sites reachable within the coverage threshold from demand point i; and k is the number of new facilities to place. The integer program is solved using PuLP (CBC solver); solution time at PHN scale is under two seconds.

### Natural Language Interface

User queries are parsed to structured parameters via the Claude API using constrained tool use (`claude-sonnet-4-6`). The tool schema enforces mode, region, travel threshold, k, and population minimum. Region is validated against an allowlist; numeric bounds are enforced at both the model layer and the application data model. Raw user text never reaches the narrative generation step; briefing-quality narrative is generated from fully-structured solver output only.

## Validation

For k = 6, the MCLP solver's output is compared directly against Ochre Health's actual six-town deployment [5]. Agreement validates the coverage optimisation approach; partial disagreement opens a structured policy conversation about trade-offs between population coverage and placement criteria not captured in the spatial data (existing infrastructure, funding eligibility, community consultation).

## Limitations

- **Single PHN scope.** National generalisation requires data validation across diverse PHN geographies and facility density profiles.
- **2021 population counts.** Population figures are drawn from the 2021 Census (ABS G01 table); rural population distributions can shift materially over a five-year period.
- **Road network only.** Seasonal road conditions, patient transport availability, and telehealth substitution are not modelled.
- **Straight-line candidate pre-filter.** Candidate site derivation uses a distance proxy rather than a full travel time pre-filter; some candidates may be slightly mis-ranked.
- **Uniform coverage objective.** The MCLP maximises raw population coverage. It does not weight by health need, disease burden, socioeconomic vulnerability, or estimated facility cost.
- **DPA as sole need signal.** DPA classification captures GP workforce shortage designation but not demand-side factors such as chronic disease prevalence or Aboriginal and Torres Strait Islander population concentration.

## References

[1] Church, R.L. and ReVelle, C.S. (1974). The maximal covering location problem. *Papers of the Regional Science Association*, 32(1), 101–118.

[2] NSW Parliament, Portfolio Committee No. 2 (2022). *Health outcomes and access to health and hospital services in rural, regional and remote New South Wales*. https://www.parliament.nsw.gov.au/committees/inquiries/Pages/inquiry-details.aspx?pk=2615

[3] NSW Health (2024). *Rural Health Inquiry Progress Report 2024*. https://www.health.nsw.gov.au/regional/Pages/rural-health-inquiry-progress-report-2024.aspx

[4] Australian Institute of Health and Welfare (2023). *Primary Health Network boundaries* [dataset]. https://data.gov.au/data/dataset/primary-health-networks

[5] Ochre Health (2024). *Six new medical centres open in Western NSW*. https://ochrehealth.com.au/news/six-new-medical-centres-open-in-western-nsw/

[6] Australian Bureau of Statistics (2021). *Australian Statistical Geography Standard (ASGS) Edition 3 — Digital boundary files*. https://www.abs.gov.au/statistics/standards/australian-statistical-geography-standard-asgs-edition-3/jul2021-jun2026/access-and-downloads/digital-boundary-files

[7] Geoscience Australia (2025). *National Health Services Directory (NHSD) — General Practice locations* [dataset]. https://ecat.ga.gov.au/geonetwork/srv/api/records/1d95ca95-8bd7-4f25-835f-d33c0219435e

[8] Australian Government Department of Health, Disability and Ageing. *Distribution Priority Area (DPA) classification*. https://www.health.gov.au/topics/rural-health-workforce/classifications/dpa
