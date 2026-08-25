# SKU Inventory Monitor

A deploy-ready Streamlit control tower for CFO/Finance, SCM, Operations, Sales and
Customer Service. It turns four centralized BOM workbooks into one governed,
compressed snapshot and gives every team a consistent lot-level view.

Approved visual reference: [`docs/UI_PREVIEW.png`](docs/UI_PREVIEW.png).

## Included views

- **Enterprise Overview** — inventory quantity/value, expired and <12-month exposure,
  product-line concentration, priority actions and team signals.
- **CFO / Finance** — value exposure, COGS coverage and the preserved V9 60% management indicator.
- **SCM Planning** — six-month average demand, months of supply and 12-month shortage/overstock signals.
- **Operations** — restricted/recall quantity, expired inventory and priority lot actions.
- **Sales / Customer Service** — 0–12 month commercial-review candidates with channel-review flags.
- **Lot Explorer** — searchable, filterable lot-level detail.

## Governed source policy

Only these four centralized BOM files are used:

1. `Current Inventory*.xlsx`
2. `Product COGS*.xlsx`
3. `Product Master*.xlsx`
4. `SCM Actual vs. Forecast*.xlsx`

`Product Status Mapping Master` is intentionally excluded. It belongs to Inventory
Reconciliation Control Tower Phase 2.5; Product Status for this app comes directly from
Product Master. The source registry is in `config/source_registry.toml`.

## Fast refresh architecture

The hosted app does **not** parse four Excel files on every startup. A local refresh command:

1. reads the newest matching files from the centralized BOM folder;
2. performs all joins and formula calculations once;
3. writes `data/inventory_snapshot.csv.gz` plus source-lineage metadata;
4. lets Streamlit load the compressed snapshot directly and cache it by file signature.

Raw BOM workbooks stay outside the repository. Use a **private GitHub repository** and a
restricted Streamlit app because the snapshot still contains internal inventory, COGS and
forecast information.

## Local run

Windows PowerShell from the project root:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python scripts\validate_data.py --data-dir data
streamlit run app.py
```

The supplied package already contains the snapshot built from the uploaded files. To rebuild
it from `E:\BOM`:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\refresh_from_bom.ps1
```

For a different folder:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\refresh_from_bom.ps1 -SourceDir "D:\Your\BOM"
```

## Deploy

Start with [START_HERE_CN.md](START_HERE_CN.md), then follow the complete
[Chinese deployment guide](docs/DEPLOYMENT_GUIDE_CN.md).

## Business-rule notes

- Default dashboard filters exclude Recall rows, matching the V9 after-recall convention.
- At-risk inventory is Expired plus 0–6, 6–9 and 9–12 month buckets.
- Commercial-review candidates require Active/Active Product inventory status,
  Active/Short-dated lot status, no restricted/recall flag, a non-discontinued product,
  and a 0–12 month expiry bucket.
- Commercial-review candidate does not mean final sale authorization.
- The V9 60% indicator is not a final accounting reserve policy.

## Official Streamlit references

- https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy
- https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/app-dependencies
- https://docs.streamlit.io/deploy/streamlit-community-cloud/get-started/connect-your-github-account
- https://docs.streamlit.io/deploy/streamlit-community-cloud/share-your-app

## v2.1 UI changes
- Removed all Streamlit download controls for now.
- Removed the Data Quality & Refresh navigation page; backend validation remains intact.
- Converted global dropdowns to multi-select filters and expanded filter coverage.
- Restored the V9 `Days Left` field in lot/action views.
- Standardized displayed quantities and currency to comma-separated formats.
- Lightened the selected sidebar navigation color and simplified the Covered Sources area.

