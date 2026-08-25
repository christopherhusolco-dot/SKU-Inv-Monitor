from __future__ import annotations

import os
from pathlib import Path

import pytest

from src.analytics import aggregate_by_bucket
from src.data_pipeline import load_bundle


@pytest.mark.skipif(not os.getenv("SKU_V9_TEST_DIR"), reason="Set SKU_V9_TEST_DIR for the private V9 workbook test")
def test_v9_current_bucket_reconciliation():
    bundle = load_bundle(Path(os.environ["SKU_V9_TEST_DIR"]))
    bucket = aggregate_by_bucket(bundle.inventory).set_index("Expiry Bucket")
    assert bundle.as_of_date.isoformat() == "2026-08-25"
    assert bucket.loc["Expired", "Quantity"] == 47149
    assert bucket.loc["0–6 Months", "Quantity"] == 6767
    assert bucket.loc["6–9 Months", "Quantity"] == 176365
    assert bucket.loc["9–12 Months", "Quantity"] == 178939

