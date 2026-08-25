from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.analytics import calculate_kpis, data_quality_checks  # noqa: E402
from src.data_pipeline import load_excel_bundle, save_snapshot  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build the fast Streamlit deploy snapshot from the four centralized BOM files."
    )
    parser.add_argument("--source-dir", default=r"E:\BOM", help="Central BOM source folder.")
    parser.add_argument("--output-dir", default="data", help="Project data folder for the snapshot.")
    args = parser.parse_args()

    source_dir = Path(args.source_dir)
    output_dir = Path(args.output_dir)
    if not source_dir.exists():
        print(f"FAIL: source folder not found: {source_dir}")
        return 2

    started = time.perf_counter()
    try:
        bundle = load_excel_bundle(source_dir)
    except Exception as exc:
        print(f"FAIL: {exc}")
        return 2

    missing_required = bundle.manifest.loc[
        bundle.manifest["Required"].eq("Yes") & bundle.manifest["Status"].ne("Loaded")
    ]
    if not missing_required.empty:
        print("FAIL: one or more required BOM sources could not be loaded:")
        print(missing_required.to_string(index=False))
        return 2

    quality = data_quality_checks(
        bundle.inventory,
        bundle.manifest,
        bundle.as_of_date,
        bundle.as_of_confidence,
    )
    snapshot_path, metadata_path = save_snapshot(bundle, output_dir)
    elapsed = time.perf_counter() - started
    kpis = calculate_kpis(bundle.inventory)

    print(f"Snapshot created: {snapshot_path}")
    print(f"Metadata created: {metadata_path}")
    print(f"Inventory as of: {bundle.as_of_date} ({bundle.as_of_confidence:.1%} confidence)")
    print(f"Rows: {len(bundle.inventory):,}")
    print(f"Quantity: {kpis['total_qty']:,.0f}")
    print(f"Inventory value: ${kpis['total_value']:,.2f}")
    print(f"Build time: {elapsed:.2f} seconds")
    print("\nSOURCE MANIFEST")
    print(bundle.manifest.to_string(index=False))
    print("\nDATA QUALITY")
    print(quality.to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
