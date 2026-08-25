from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from .constants import EXPIRY_BUCKETS


def safe_sum(series: pd.Series | None) -> float:
    if series is None:
        return 0.0
    return float(pd.to_numeric(series, errors="coerce").sum())


def calculate_kpis(frame: pd.DataFrame) -> dict[str, float | int]:
    if frame.empty:
        return {
            "total_qty": 0.0,
            "total_value": 0.0,
            "at_risk_qty": 0.0,
            "at_risk_value": 0.0,
            "expired_qty": 0.0,
            "expired_value": 0.0,
            "healthy_qty": 0.0,
            "healthy_value": 0.0,
            "provision_qty": 0.0,
            "provision_value": 0.0,
            "sku_count": 0,
            "lot_count": 0,
        }
    risk_mask = frame["Expiry Bucket"].isin(
        ["Expired", "0–6 Months", "6–9 Months", "9–12 Months"]
    )
    expired_mask = frame["Expiry Bucket"].eq("Expired")
    healthy_mask = frame["Expiry Bucket"].isin(
        ["12–15 Months", "15–18 Months", "18–24 Months", "24–36 Months", "36+ Months"]
    )
    return {
        "total_qty": safe_sum(frame["Quantity"]),
        "total_value": safe_sum(frame["Dollar Amount"]),
        "at_risk_qty": safe_sum(frame.loc[risk_mask, "Quantity"]),
        "at_risk_value": safe_sum(frame.loc[risk_mask, "Dollar Amount"]),
        "expired_qty": safe_sum(frame.loc[expired_mask, "Quantity"]),
        "expired_value": safe_sum(frame.loc[expired_mask, "Dollar Amount"]),
        "healthy_qty": safe_sum(frame.loc[healthy_mask, "Quantity"]),
        "healthy_value": safe_sum(frame.loc[healthy_mask, "Dollar Amount"]),
        "provision_qty": safe_sum(frame.get("Provision 60%")),
        "provision_value": safe_sum(frame.get("Provision 60% Value")),
        "sku_count": int(frame["NDC_Key"].nunique(dropna=True)),
        "lot_count": int(frame["Lot Number"].nunique(dropna=True)),
    }


def aggregate_by_bucket(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=["Expiry Bucket", "Quantity", "Inventory Value", "Lot Count", "SKU Count"])
    result = (
        frame.groupby("Expiry Bucket", observed=False)
        .agg(
            Quantity=("Quantity", "sum"),
            **{
                "Inventory Value": ("Dollar Amount", "sum"),
                "Lot Count": ("Lot Number", "nunique"),
                "SKU Count": ("NDC_Key", "nunique"),
            },
        )
        .reset_index()
    )
    result["Expiry Bucket"] = pd.Categorical(
        result["Expiry Bucket"], categories=EXPIRY_BUCKETS, ordered=True
    )
    return result.sort_values("Expiry Bucket").reset_index(drop=True)


def sku_summary(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame()
    keys = ["Material Number", "NDC 11", "Item Description Final", "Product Line", "Manufacturer"]
    for key in keys:
        if key not in frame:
            frame = frame.assign(**{key: pd.NA})
    work = frame.copy()
    work["At Risk Qty"] = work["Quantity"].where(
        work["Expiry Bucket"].isin(["Expired", "0–6 Months", "6–9 Months", "9–12 Months"]), 0
    )
    work["At Risk Value"] = work["Dollar Amount"].where(
        work["Expiry Bucket"].isin(["Expired", "0–6 Months", "6–9 Months", "9–12 Months"]), 0
    )
    work["Expired Qty Summary"] = work["Quantity"].where(work["Expiry Bucket"].eq("Expired"), 0)
    work["Expired Value Summary"] = work["Dollar Amount"].where(work["Expiry Bucket"].eq("Expired"), 0)
    work["Sellable Qty"] = work["Quantity"].where(work["Sellable"], 0)
    grouped = (
        work.groupby(keys, dropna=False)
        .agg(
            **{
                "Inventory Qty": ("Quantity", "sum"),
                "Inventory Value": ("Dollar Amount", "sum"),
                "Sellable Qty": ("Sellable Qty", "sum"),
                "At Risk Qty": ("At Risk Qty", "sum"),
                "At Risk Value": ("At Risk Value", "sum"),
                "Expired Qty": ("Expired Qty Summary", "sum"),
                "Expired Value": ("Expired Value Summary", "sum"),
                "Earliest Expiration": ("Lot Expiration", "min"),
                "Lot Count": ("Lot Number", "nunique"),
                "Monthly Demand": ("Customer Master Demand", "first"),
                "6M Avg Forecast": ("6M Average Forecast", "first"),
                "12M Forecast": ("12M Forecast", "first"),
                "Product Status": ("Product Status", "first"),
                "Controlled Sub.": ("Controlled Sub.", "first"),
            }
        )
        .reset_index()
    )
    denominator = pd.to_numeric(grouped["6M Avg Forecast"], errors="coerce")
    grouped["Months of Supply"] = np.where(
        denominator.notna() & denominator.gt(0), grouped["Sellable Qty"] / denominator, np.nan
    )
    demand_12 = pd.to_numeric(grouped["12M Forecast"], errors="coerce")
    grouped["12M Shortage Qty"] = np.maximum(demand_12 - grouped["Sellable Qty"], 0)
    grouped["12M Overstock Qty"] = np.maximum(grouped["Sellable Qty"] - demand_12, 0)
    grouped["Coverage Status"] = np.select(
        [
            grouped["Months of Supply"].isna(),
            grouped["Months of Supply"] < 3,
            grouped["Months of Supply"].between(3, 9, inclusive="both"),
            grouped["Months of Supply"] > 18,
        ],
        ["No Forecast", "Supply Risk", "Balanced", "Overstock"],
        default="Watch",
    )
    return grouped.sort_values(["At Risk Value", "At Risk Qty"], ascending=False).reset_index(drop=True)


def action_queue(frame: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "Priority",
        "Action Owner",
        "Primary Action",
        "Material Number",
        "NDC 11",
        "Item Description Final",
        "Product Line",
        "Lot Number",
        "Lot Expiration",
        "Days To Exp",
        "Expiry Bucket",
        "Inventory Status",
        "Lot Status",
        "Quantity",
        "COGS",
        "Dollar Amount",
        "Customer Master Demand",
        "6M Average Forecast",
        "Manufacturer",
        "Controlled Sub.",
    ]
    present = [column for column in columns if column in frame]
    queue = frame.loc[~frame["Priority"].eq("Routine"), present].copy()
    priority_order = {
        "P0 Restricted / Recall": 0,
        "P1 Expired": 1,
        "P1 Immediate: 0–6M": 2,
        "P2 Monetize: 6–9M": 3,
        "P3 Protect: 9–12M": 4,
        "P4 Monitor: 12–18M": 5,
    }
    queue["_priority"] = queue["Priority"].map(priority_order).fillna(99)
    queue = queue.sort_values(["_priority", "Dollar Amount", "Quantity"], ascending=[True, False, False])
    return queue.drop(columns="_priority").reset_index(drop=True)


def data_quality_checks(
    frame: pd.DataFrame,
    manifest: pd.DataFrame,
    as_of_date: date,
    as_of_confidence: float,
) -> pd.DataFrame:
    total_rows = max(len(frame), 1)
    missing_required = 0
    if not manifest.empty:
        missing_required = int(
            (
                manifest["Required"].eq("Yes")
                & manifest["Status"].ne("Loaded")
                & manifest["Mode"].ne("Embedded V9")
            ).sum()
        )
    checks: list[dict[str, Any]] = [
        {
            "Check": "Required source files available",
            "Status": "PASS" if missing_required == 0 else "WARN",
            "Count / Rate": missing_required,
            "Impact": "All four governed BOM sources must be present when the deploy snapshot is rebuilt.",
        },
        {
            "Check": "Inventory as-of date consistency",
            "Status": "PASS" if as_of_confidence >= 0.8 else "WARN",
            "Count / Rate": f"{as_of_confidence:.1%}",
            "Impact": f"Inferred as-of date: {as_of_date:%Y-%m-%d}.",
        },
        {
            "Check": "Missing Product Master mapping",
            "Status": "PASS" if frame["Material Number"].notna().all() else "WARN",
            "Count / Rate": f"{frame['Material Number'].isna().sum():,} / {len(frame):,}",
            "Impact": "Rows without material mapping cannot receive forecast or COGS reliably.",
        },
        {
            "Check": "Missing COGS",
            "Status": "PASS" if frame["COGS"].notna().all() else "WARN",
            "Count / Rate": f"{frame['COGS'].isna().sum():,} / {len(frame):,}",
            "Impact": "Inventory value and provision-value metrics are understated when COGS is missing.",
        },
        {
            "Check": "Missing forecast",
            "Status": "PASS" if frame["Customer Master Demand"].notna().all() else "WARN",
            "Count / Rate": f"{frame['Customer Master Demand'].isna().sum():,} / {len(frame):,}",
            "Impact": "Coverage, shortage and overstock metrics are unavailable for these rows.",
        },
        {
            "Check": "Invalid or missing lot expiration",
            "Status": "PASS" if frame["Lot Expiration"].notna().all() else "WARN",
            "Count / Rate": f"{frame['Lot Expiration'].isna().sum():,} / {len(frame):,}",
            "Impact": "Expiry bucket cannot be assigned.",
        },
        {
            "Check": "Negative inventory quantity",
            "Status": "PASS" if not frame["Quantity"].lt(0).any() else "WARN",
            "Count / Rate": int(frame["Quantity"].lt(0).sum()),
            "Impact": "Review reversal, adjustment or source-sign convention.",
        },
        {
            "Check": "Duplicate lot/status rows",
            "Status": "PASS",
            "Count / Rate": int(
                frame.duplicated(
                    ["NDC_Key", "Lot Number", "Inventory Status", "Lot Status", "Warehouse"],
                    keep=False,
                ).sum()
            ),
            "Impact": "Duplicates may be legitimate location/status splits; review before removing.",
        },
    ]
    checks[-1]["Status"] = "PASS" if checks[-1]["Count / Rate"] == 0 else "REVIEW"
    checks.append(
        {
            "Check": "Rows valued",
            "Status": "PASS" if frame["Dollar Amount"].notna().mean() >= 0.98 else "WARN",
            "Count / Rate": f"{frame['Dollar Amount'].notna().mean():.1%}",
            "Impact": f"{total_rows - frame['Dollar Amount'].notna().sum():,} rows are not valued.",
        }
    )
    return pd.DataFrame(checks)


def append_current_history(history: pd.DataFrame, frame: pd.DataFrame, as_of_date: date) -> pd.DataFrame:
    kpis = calculate_kpis(frame)
    bucket = aggregate_by_bucket(frame).set_index("Expiry Bucket")

    def metric(bucket_name: str, column: str) -> float:
        try:
            return float(bucket.loc[bucket_name, column])
        except Exception:
            return 0.0

    current = {
        "Inventory Date": pd.Timestamp(as_of_date),
        "Total Expired & SD Qty (Reported)": kpis["at_risk_qty"],
        "Total Expired & SD Value (Reported)": kpis["at_risk_value"],
        "12M+ Qty (Reported)": kpis["healthy_qty"],
        "12M+ Value (Reported)": kpis["healthy_value"],
        "Expired Qty": metric("Expired", "Quantity"),
        "Expired Value": metric("Expired", "Inventory Value"),
        "0–6M Qty": metric("0–6 Months", "Quantity"),
        "0–6M Value": metric("0–6 Months", "Inventory Value"),
        "6–9M Qty": metric("6–9 Months", "Quantity"),
        "6–9M Value": metric("6–9 Months", "Inventory Value"),
        "9–12M Qty": metric("9–12 Months", "Quantity"),
        "9–12M Value": metric("9–12 Months", "Inventory Value"),
        "12–15M Qty": metric("12–15 Months", "Quantity"),
        "12–15M Value": metric("12–15 Months", "Inventory Value"),
        "15–18M Qty": metric("15–18 Months", "Quantity"),
        "15–18M Value": metric("15–18 Months", "Inventory Value"),
        "18–24M Qty": metric("18–24 Months", "Quantity"),
        "18–24M Value": metric("18–24 Months", "Inventory Value"),
        "24–36M Qty": metric("24–36 Months", "Quantity"),
        "24–36M Value": metric("24–36 Months", "Inventory Value"),
        "Recall Qty": safe_sum(frame.loc[frame["Recall Flag"], "Quantity"]),
        "Expired After Recall Qty": safe_sum(
            frame.loc[frame["Expiry Bucket"].eq("Expired") & ~frame["Recall Flag"], "Quantity"]
        ),
        "Source": "Streamlit calculated",
    }
    result = history.copy() if history is not None else pd.DataFrame()
    if not result.empty and "Inventory Date" in result:
        result["Inventory Date"] = pd.to_datetime(result["Inventory Date"], errors="coerce")
        result = result.loc[result["Inventory Date"].dt.date.ne(as_of_date)].copy()
    result = pd.concat([result, pd.DataFrame([current])], ignore_index=True, sort=False)
    return result.sort_values("Inventory Date").reset_index(drop=True)
