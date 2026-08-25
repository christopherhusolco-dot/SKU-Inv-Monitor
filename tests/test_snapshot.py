from __future__ import annotations

from datetime import date

import pandas as pd

from src.data_pipeline import DataBundle, load_snapshot_bundle, save_snapshot


def test_snapshot_round_trip(tmp_path):
    inventory = pd.DataFrame(
        {
            "Material Number": pd.Series(["000123"], dtype="string"),
            "NDC_Key": pd.Series(["12345067890"], dtype="string"),
            "NDC 11": pd.Series(["12345-0678-90"], dtype="string"),
            "Item Number": pd.Series(["12345067890"], dtype="string"),
            "Item Number Raw": pd.Series(["12345-678-90"], dtype="string"),
            "Lot Number": pd.Series(["LOT001"], dtype="string"),
            "Lot Expiration": [pd.Timestamp("2027-01-01")],
            "COGS Date": [pd.Timestamp("2026-01-01")],
            "Quantity": [12.0],
            "Dollar Amount": [30.0],
            "Recall Flag": [False],
            "Restricted / Recall": [False],
            "Sellable": [True],
            "Commercial Review Eligible": [True],
        }
    )
    manifest = pd.DataFrame(
        [
            {
                "Source": "Current Inventory",
                "Required": "Yes",
                "Status": "Loaded",
                "File": "Current Inventory.xlsx",
                "Mode": "Separate source file",
            }
        ]
    )
    bundle = DataBundle(
        inventory=inventory,
        product_master=pd.DataFrame(),
        cogs=pd.DataFrame(),
        forecast=pd.DataFrame(),
        status_mapping=pd.DataFrame(),
        history=pd.DataFrame(),
        manifest=manifest,
        as_of_date=date(2026, 8, 25),
        as_of_confidence=1.0,
        forecast_months=["2026-08"],
    )

    save_snapshot(bundle, tmp_path)
    loaded = load_snapshot_bundle(tmp_path)

    assert loaded.as_of_date == date(2026, 8, 25)
    assert loaded.source_mode == "Fast deploy snapshot"
    assert loaded.inventory.loc[0, "Material Number"] == "000123"
    assert loaded.inventory.loc[0, "Commercial Review Eligible"]
    assert loaded.manifest.loc[0, "Mode"] == "Deploy snapshot"
