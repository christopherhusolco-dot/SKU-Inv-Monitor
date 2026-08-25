# Data file requirements and ownership

## Governed sources

| Source | Preferred worksheet | Required fields | Join / purpose | Suggested owner |
|---|---|---|---|---|
| Current Inventory | `Export` | Client ID, Warehouse, Item Number, Item Description, Lot Number, Lot Expiration, Inventory Status, Lot Status, Quantity, Days Until Lot Expiration, UOM | Lot/status inventory base; NDC join | Operations / WMS |
| Product COGS | `Sheet1` | Material, Valid To, Valid From, Amount, per, UoM | Latest open-ended COGS by Material | Finance |
| Product Master | `Product Master` | Mat Code, NDC and variants, Description, Product Line, Supplier, Product Status | NDC-to-Material and product attributes | Master Data / SCM |
| SCM Actual vs. Forecast | `Forecast_Supply Plan` | SAP Mat No., NDC Code, Product Description, YYYY-MM columns | Demand, 6M average and 12M coverage | SCM |

Filename suffixes such as `(1)` or `(2)` are accepted. If multiple matching versions exist,
the newest modified file is selected. Temporary Excel lock files beginning with `~$` are ignored.

## Explicitly excluded

`Product Status Mapping Master` is not loaded, joined or required by this app. Its workbook
README identifies it as a mapping source for Inventory Reconciliation Control Tower Phase 2.5.
The SKU Inventory Monitor obtains Product Status directly from Product Master.

## Snapshot contract

`scripts/build_deploy_snapshot.py` reads the four Excel sources and creates:

- `data/inventory_snapshot.csv.gz` — enriched lot/status rows used by Streamlit;
- `data/snapshot_metadata.json` — as-of date, source filenames, worksheets, timestamps,
  row counts, warnings and forecast-month list;
- `data/inventory_history.csv` — optional historical reported points maintained separately.

The raw workbooks are ignored by Git and should remain in the centralized BOM folder.

## As-of date

The app infers the reporting date from the modal value of:

`Lot Expiration − Days Until Lot Expiration`

This prevents GitHub checkout timestamps from changing the inventory reporting date. The
current uploaded source produces `2026-08-25` with 100% consistency.

## Current data-quality review items

The current snapshot loads all four governed sources and has no missing expiration dates.
It also reports rows missing Product Master, COGS or Forecast mapping and possible duplicate
lot/status splits on the Data Quality page. Duplicate flags are review items, not automatically
removed records, because warehouse/location splits can be legitimate.

## Confidentiality

The deploy snapshot contains internal inventory and value data. Use a private GitHub repository,
restricted Streamlit access and company-approved retention/sharing controls.
