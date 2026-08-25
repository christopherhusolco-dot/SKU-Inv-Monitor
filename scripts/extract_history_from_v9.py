from __future__ import annotations

import argparse
from pathlib import Path

from src.data_pipeline import extract_v9_history


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract aggregate snapshot history from V9.")
    parser.add_argument("workbook", type=Path)
    parser.add_argument("--output", type=Path, default=Path("data/inventory_history.csv"))
    args = parser.parse_args()
    history = extract_v9_history(args.workbook)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    history.to_csv(args.output, index=False)
    print(f"Wrote {len(history)} snapshots to {args.output}")


if __name__ == "__main__":
    main()

