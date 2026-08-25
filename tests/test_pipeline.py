from __future__ import annotations

from datetime import date

import pandas as pd

from src.analytics import aggregate_by_bucket, calculate_kpis, sku_summary
from src.data_pipeline import (
    canonical_ndc11,
    derive_inventory,
    infer_as_of_date,
    normalize_cogs,
    normalize_forecast,
    normalize_inventory,
    normalize_product_master,
)


def fixture_frames():
    inventory = pd.DataFrame(
        {
            "Client ID": ["SO", "SO", "SO"],
            "Warehouse": ["MEM", "MEM", "MEM"],
            "Item Number": ["4354736703", "4354736703", "FDA PALLET CRT"],
            "Item Description": ["Product A", "Product A", "FDA Pallet"],
            "Lot Number": ["L1", "L2", "L3"],
            "Lot Expiration": [pd.Timestamp("2026-08-20"), pd.Timestamp("2027-02-25"), pd.Timestamp("2026-08-01")],
            "Inventory Status": ["Active", "Active Product", "FDA Hold"],
            "Lot Status": ["Active", "Short-Dated", "Expired"],
            "Quantity": [10, 20, 3],
            "Days Until Lot Expiration": [-5, 184, -24],
            "Part Family": ["CRT", "CRT", "CRT"],
            "Is Serialized": ["Y", "Y", "N"],
            "Allocation Key": [None, None, None],
            "UOM": ["EA", "EA", "Pallet"],
        }
    )
    product = pd.DataFrame(
        {
            "Mat Code": [616001],
            "NDC": [4354736703],
            "Description": ["Product A"],
            "Product Line": ["Line A"],
            "Supplier": ["CMO A"],
            "Product Status": ["Marketed"],
        }
    )
    cogs = pd.DataFrame(
        {
            "Material": [616001],
            "Amount": [2.5],
            "Valid From": [pd.Timestamp("2026-01-01")],
            "Valid To": [date(9999, 12, 31)],
            "per": [1],
            "UoM": ["EA"],
        }
    )
    forecast = pd.DataFrame(
        {
            "SAP Mat No.": [616001],
            "NDC Code": [4354736703],
            "Product Description": ["Product A"],
            "2026-08": [5],
            "2026-09": [7],
            "2026-10": [6],
            "2026-11": [8],
            "2026-12": [9],
            "2027-01": [7],
        }
    )
    return inventory, product, cogs, forecast


def test_ndc_normalization():
    assert canonical_ndc11("4354736703") == "43547036703"
    assert canonical_ndc11("43547-0367-03") == "43547036703"
    assert canonical_ndc11("SO4354736703") == "43547036703"


def test_pipeline_and_metrics():
    inv_raw, pm_raw, cogs_raw, fc_raw = fixture_frames()
    inv = normalize_inventory(inv_raw)
    inferred, confidence = infer_as_of_date(inv)
    assert inferred == date(2026, 8, 25)
    assert confidence == 1.0
    pm, mapping = normalize_product_master(pm_raw)
    cogs = normalize_cogs(cogs_raw)
    forecast, months = normalize_forecast(fc_raw)
    assert months[:2] == ["2026-08", "2026-09"]
    enriched = derive_inventory(inv, mapping, cogs, forecast, inferred)
    assert len(enriched) == 3
    assert enriched.loc[0, "Expiry Bucket"] == "Expired"
    assert enriched.loc[1, "Expiry Bucket"] == "6–9 Months"
    assert enriched.loc[0, "Dollar Amount"] == 25
    assert enriched.loc[2, "Restricted / Recall"]
    assert enriched.loc[1, "Sellable"]
    assert enriched.loc[1, "Commercial Review Eligible"]
    assert not enriched.loc[0, "Commercial Review Eligible"]
    kpis = calculate_kpis(enriched)
    assert kpis["total_qty"] == 33
    assert kpis["total_value"] == 75
    bucket = aggregate_by_bucket(enriched)
    assert bucket.loc[bucket["Expiry Bucket"].eq("Expired"), "Quantity"].iloc[0] == 13
    summary = sku_summary(enriched)
    assert len(summary) >= 1
