# Deploy data folder

The hosted app reads these files:

- `inventory_snapshot.csv.gz` — enriched lot/status data generated from four BOM workbooks;
- `snapshot_metadata.json` — as-of date, lineage, source timestamps and refresh warnings;
- `inventory_history.csv` — optional historical V9-reported points.

Rebuild the snapshot from the centralized BOM folder:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\refresh_from_bom.ps1
```

Raw BOM workbooks stay in the centralized source folder and are ignored by Git. The source
registry intentionally excludes Product Status Mapping Master.
