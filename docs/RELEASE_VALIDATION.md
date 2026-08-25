# Release validation — 2026-08-25 source snapshot

## Source loading

| Source | Result | Loaded source rows |
|---|---:|---:|
| Current Inventory | Loaded | 3,547 raw / 3,545 usable |
| Product COGS | Loaded | 1,078 raw |
| Product Master | Loaded | 534 raw |
| SCM Actual vs. Forecast | Loaded | 337 raw |
| Product Status Mapping Master | Intentionally excluded | — |

Inventory as-of inference: `2026-08-25`, 100% consistency.

## Default dashboard result

The default UI excludes Recall rows.

| KPI | Validated result |
|---|---:|
| Total quantity | 21,181,653 |
| Inventory value | $37,263,107.20 |
| Expired & <12M quantity | 387,763 |
| Expired & <12M value | $859,647.05 |
| Expired quantity | 25,692 |
| Expired value | $38,356.81 |
| SKU count | 300 |
| Lot count | 2,434 |

Commercial-review pool: 331,485 units, $694,137.03, 43 SKUs and 68 lots.

## Data-quality review items

| Check | Current result |
|---|---:|
| Missing Product Master mapping | 37 rows |
| Missing COGS | 43 rows |
| Missing forecast | 49 rows |
| Missing/invalid lot expiration | 0 rows |
| Possible duplicate lot/status rows | 268 rows for review |
| Rows valued | 98.8% gross source view |

Possible duplicates remain visible because location and status splits may be legitimate.

## Technical validation

- Python compilation passed for the complete project.
- Formula, NDC, commercial-status and snapshot round-trip tests passed.
- Snapshot reload reproduced the source totals and identifiers.
- Compressed snapshot size: approximately 240 KB.
- Local snapshot load smoke test: approximately 0.06 seconds in the build environment.
- Full current-view Excel export generated successfully.
- ZIP package integrity is checked as part of release packaging.

Load time on Streamlit Community Cloud also depends on container startup and dependency
installation; the 0.06-second measurement covers application data loading only.
