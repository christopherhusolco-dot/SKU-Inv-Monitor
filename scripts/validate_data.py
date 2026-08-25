from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.analytics import calculate_kpis, data_quality_checks
from src.data_pipeline import load_bundle


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the SKU Inventory Monitor deploy data.")
    parser.add_argument("--data-dir", default="data", help="Folder containing the deploy snapshot or Excel sources.")
    args = parser.parse_args()
    data_dir = Path(args.data_dir)
    try:
        bundle = load_bundle(data_dir)
    except Exception as exc:
        print(f"FAIL: {exc}")
        return 2
    print(f"Inventory as of: {bundle.as_of_date} (confidence {bundle.as_of_confidence:.1%})")
    print(f"Load mode: {bundle.source_mode}")
    print(f"Inventory rows: {len(bundle.inventory):,}")
    print("\nSOURCE MANIFEST")
    print(bundle.manifest.to_string(index=False))
    quality = data_quality_checks(
        bundle.inventory,
        bundle.manifest,
        bundle.as_of_date,
        bundle.as_of_confidence,
    )
    print("\nDATA QUALITY")
    print(quality.to_string(index=False))
    print("\nKEY TOTALS")
    for key, value in calculate_kpis(bundle.inventory).items():
        print(f"{key}: {value}")
    if bundle.warnings:
        print("\nWARNINGS")
        for warning in bundle.warnings:
            print(f"- {warning}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
