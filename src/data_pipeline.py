from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

from .constants import EXPIRY_BUCKETS, SOURCE_SPECS


SUPPORTED_EXTENSIONS = {".xlsx", ".xlsm", ".xls", ".xlsb", ".csv"}
SIGNATURE_EXTENSIONS = SUPPORTED_EXTENSIONS | {".gz", ".json"}
SNAPSHOT_FILENAME = "inventory_snapshot.csv.gz"
SNAPSHOT_METADATA_FILENAME = "snapshot_metadata.json"


@dataclass
class DataBundle:
    inventory: pd.DataFrame
    product_master: pd.DataFrame
    cogs: pd.DataFrame
    forecast: pd.DataFrame
    status_mapping: pd.DataFrame
    history: pd.DataFrame
    manifest: pd.DataFrame
    as_of_date: date
    as_of_confidence: float
    forecast_months: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    source_mode: str = "Excel sources"
    snapshot_created_at: str | None = None


def normalize_label(value: Any) -> str:
    text = "" if value is None else str(value)
    text = text.replace("\xa0", " ").replace("\n", " ").strip().lower()
    return re.sub(r"[^a-z0-9]+", "", text)


def clean_column_name(value: Any) -> str:
    if isinstance(value, (datetime, date, pd.Timestamp)):
        return pd.Timestamp(value).strftime("%Y-%m")
    text = "" if value is None else str(value)
    text = text.replace("\xa0", " ").replace("\n", " ")
    return re.sub(r"\s+", " ", text).strip()


def clean_headers(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    names: list[str] = []
    seen: dict[str, int] = {}
    for raw in result.columns:
        name = clean_column_name(raw) or "Unnamed"
        count = seen.get(name, 0)
        seen[name] = count + 1
        names.append(name if count == 0 else f"{name}_{count + 1}")
    result.columns = names
    result = result.dropna(axis=0, how="all").dropna(axis=1, how="all")
    return result


def digits_only(value: Any) -> str | None:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return None
    text = str(value).strip()
    if text.endswith(".0") and re.fullmatch(r"\d+\.0", text):
        text = text[:-2]
    digits = "".join(re.findall(r"\d", text))
    return digits or None


def canonical_ndc11(value: Any) -> str | None:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return None
    raw = str(value).strip()
    groups = re.findall(r"\d+", raw)
    digits = "".join(groups)
    if not digits:
        return None
    if len(groups) >= 3:
        a, b, c = groups[-3], groups[-2], groups[-1]
        if len(a) == 4 and len(b) == 4 and len(c) == 2:
            return "0" + a + b + c
        if len(a) == 5 and len(b) == 3 and len(c) == 2:
            return a + "0" + b + c
        if len(a) == 5 and len(b) == 4 and len(c) == 1:
            return a + b + c + "0"
        if len(a) == 5 and len(b) == 4 and len(c) == 2:
            return a + b + c
    if len(digits) == 10:
        return digits[:5] + "0" + digits[5:]
    if len(digits) == 11:
        return digits
    return digits


def format_ndc11(value: Any) -> str | None:
    ndc = canonical_ndc11(value)
    if ndc is None or len(ndc) != 11:
        return ndc
    return f"{ndc[:5]}-{ndc[5:9]}-{ndc[9:]}"


def _path_matches(path: Path, includes: Iterable[str], excludes: Iterable[str] = ()) -> bool:
    stem = normalize_label(path.stem)
    include_ok = any(normalize_label(pattern) in stem for pattern in includes)
    exclude_ok = not any(normalize_label(pattern) in stem for pattern in excludes)
    return include_ok and exclude_ok


def discover_sources(data_dir: str | Path) -> dict[str, Path | None]:
    root = Path(data_dir)
    files = [
        path
        for path in root.glob("*")
        if path.is_file()
        and not path.name.startswith("~$")
        and path.suffix.lower() in SUPPORTED_EXTENSIONS
    ]
    discovered: dict[str, Path | None] = {}
    for key, spec in SOURCE_SPECS.items():
        candidates = [
            path
            for path in files
            if _path_matches(
                path,
                spec["patterns"],
                spec.get("exclude_patterns", []),
            )
        ]
        discovered[key] = max(candidates, key=lambda p: p.stat().st_mtime) if candidates else None
    workbook_candidates = [
        path
        for path in files
        if path.suffix.lower() == ".xlsm"
        and ("skuinvmonitor" in normalize_label(path.name) or "specialsku" in normalize_label(path.name))
    ]
    discovered["v9_workbook"] = (
        max(workbook_candidates, key=lambda p: p.stat().st_mtime)
        if workbook_candidates
        else None
    )
    history_candidates = [
        path
        for path in root.glob("*.csv")
        if "inventoryhistory" in normalize_label(path.name)
    ]
    discovered["history"] = (
        max(history_candidates, key=lambda p: p.stat().st_mtime)
        if history_candidates
        else None
    )
    return discovered


def source_signature(data_dir: str | Path) -> str:
    root = Path(data_dir)
    digest = hashlib.sha256()
    if not root.exists():
        return digest.hexdigest()
    for path in sorted(root.glob("*"), key=lambda p: p.name.lower()):
        if (
            not path.is_file()
            or path.name.startswith("~$")
            or path.suffix.lower() not in SIGNATURE_EXTENSIONS
        ):
            continue
        stat = path.stat()
        digest.update(path.name.encode("utf-8", errors="ignore"))
        digest.update(str(stat.st_size).encode())
        digest.update(str(stat.st_mtime_ns).encode())
    return digest.hexdigest()


def _score_header(row: pd.Series, tokens: Iterable[str]) -> int:
    normalized = {normalize_label(value) for value in row.tolist() if pd.notna(value)}
    return sum(1 for token in tokens if normalize_label(token) in normalized)


def _select_sheet(sheet_names: list[str], preferred: Iterable[str]) -> list[str]:
    preferred_norm = [normalize_label(x) for x in preferred]
    ranked: list[str] = []
    for target in preferred_norm:
        ranked.extend([name for name in sheet_names if normalize_label(name) == target and name not in ranked])
    for target in preferred_norm:
        ranked.extend([name for name in sheet_names if target in normalize_label(name) and name not in ranked])
    ranked.extend([name for name in sheet_names if name not in ranked])
    return ranked


def read_excel_flexible(
    path: Path,
    preferred_sheets: Iterable[str],
    header_tokens: Iterable[str],
    max_header_rows: int = 35,
) -> tuple[pd.DataFrame, str, int]:
    if path.suffix.lower() == ".csv":
        preview = pd.read_csv(path, header=None, nrows=max_header_rows, dtype=object)
        scores = [_score_header(preview.iloc[i], header_tokens) for i in range(len(preview))]
        header_row = int(np.argmax(scores)) if scores else 0
        return clean_headers(pd.read_csv(path, header=header_row, dtype=object)), "CSV", header_row + 1

    excel_engines = {
        ".xlsx": "openpyxl",
        ".xlsm": "openpyxl",
        ".xls": "xlrd",
        ".xlsb": "pyxlsb",
    }
    excel = pd.ExcelFile(path, engine=excel_engines.get(path.suffix.lower()))
    best: tuple[int, str, int] | None = None
    for sheet_name in _select_sheet(excel.sheet_names, preferred_sheets):
        try:
            preview = pd.read_excel(
                excel,
                sheet_name=sheet_name,
                header=None,
                nrows=max_header_rows,
                dtype=object,
            )
        except Exception:
            continue
        for idx in range(len(preview)):
            score = _score_header(preview.iloc[idx], header_tokens)
            candidate = (score, sheet_name, idx)
            if best is None or candidate[0] > best[0]:
                best = candidate
        if best and best[0] >= len(list(header_tokens)):
            break
    if best is None:
        raise ValueError(f"No readable worksheet found in {path.name}")
    _, sheet_name, header_row = best
    frame = pd.read_excel(excel, sheet_name=sheet_name, header=header_row, dtype=object)
    return clean_headers(frame), sheet_name, header_row + 1


def _rename_aliases(frame: pd.DataFrame, aliases: dict[str, list[str]]) -> pd.DataFrame:
    lookup: dict[str, str] = {}
    for canonical, variants in aliases.items():
        for variant in [canonical, *variants]:
            lookup[normalize_label(variant)] = canonical
    rename: dict[str, str] = {}
    occupied: set[str] = set()
    for column in frame.columns:
        canonical = lookup.get(normalize_label(column))
        if canonical and canonical not in occupied:
            rename[column] = canonical
            occupied.add(canonical)
    return frame.rename(columns=rename)


INVENTORY_ALIASES = {
    "Client ID": ["Client", "ClientID"],
    "Warehouse": ["WH", "Warehouse Code"],
    "Item Number": ["Item", "NDC", "NDC Code", "Item No"],
    "Item Description": ["Description", "Product Description"],
    "Lot Number": ["Lot", "Batch", "Batch Number"],
    "Lot Expiration": ["Expiration", "Expiration Date", "Expiry Date", "Lot Expiry"],
    "Inventory Status": ["Inv Status", "Status"],
    "Lot Status": ["Batch Status"],
    "Quantity": ["Qty", "On Hand", "Inventory Qty"],
    "Days Until Lot Expiration": ["Days Until Expiration", "Days to Expiration"],
    "Part Family": ["PartFamily"],
    "Is Serialized": ["Serialized", "Serialization"],
    "Allocation Key": ["Allocation"],
    "UOM": ["Unit of Measure", "Base UOM"],
    "Material Number": ["Material", "SAP Material", "SAP Mat No."],
}

PRODUCT_ALIASES = {
    "Material Number": ["Mat Code", "Material", "SAP Mat No.", "Material Number"],
    "NDC": ["NDC Code", "NDC 11"],
    "NDC Var 1": ["NDC Variant 1"],
    "NDC Var 2": ["NDC Variant 2"],
    "NDC Var 3": ["NDC Variant 3"],
    "PM Description": ["Description", "Product Description"],
    "Product Line": ["Product Family"],
    "Manufacturer": ["Supplier", "CMO"],
    "Product Status": ["Marketing Status"],
    "Controlled Sub.": ["Controlled Substance", "Controlled"],
    "Function": ["Therapeutic Function", "Indication"],
    "Special Requirements": ["Special Requirement"],
    "Shelf Life (Months)": ["Shelf Life", "Shelf Life Months"],
    "Case-Pack": ["Case Pack", "CasePack"],
}

COGS_ALIASES = {
    "Material Number": ["Material", "Mat Code", "SAP Mat No."],
    "COGS": ["Amount", "Cost", "Unit Cost"],
    "COGS Date": ["Valid From", "Effective Date"],
    "Valid To": ["ValidTo", "Expiration Date"],
    "per": ["Per", "Price Unit"],
    "UoM": ["UOM", "Unit of Measure"],
}

FORECAST_ALIASES = {
    "Material Number": ["SAP Mat No.", "SAP Mat No", "Material", "Mat Code"],
    "Forecast NDC": ["NDC Code", "NDC"],
    "Forecast Product Description": ["Product Description", "Description"],
    "Forecast Status": ["Status"],
}


def normalize_inventory(frame: pd.DataFrame) -> pd.DataFrame:
    data = _rename_aliases(clean_headers(frame), INVENTORY_ALIASES)
    required = [
        "Client ID",
        "Warehouse",
        "Item Number",
        "Item Description",
        "Lot Number",
        "Lot Expiration",
        "Inventory Status",
        "Lot Status",
        "Quantity",
        "Days Until Lot Expiration",
        "Part Family",
        "Is Serialized",
        "Allocation Key",
        "UOM",
    ]
    for column in required:
        if column not in data:
            data[column] = pd.NA
    if data["Client ID"].notna().any() and data["Client ID"].astype(str).str.upper().eq("SO").any():
        data = data.loc[data["Client ID"].astype(str).str.strip().str.upper().eq("SO")].copy()
    data = data.loc[data["Item Number"].notna() & data["Item Number"].astype(str).str.strip().ne("")].copy()
    data["Item Number Raw"] = data["Item Number"]
    data["Item Number"] = data["Item Number"].map(digits_only)
    data["NDC_Key"] = data["Item Number Raw"].map(canonical_ndc11)
    data["NDC 11"] = data["NDC_Key"].map(format_ndc11)
    data["Lot Number"] = data["Lot Number"].map(lambda x: None if pd.isna(x) else str(x).strip())
    data["Lot Expiration"] = pd.to_datetime(data["Lot Expiration"], errors="coerce")
    data["Quantity"] = pd.to_numeric(data["Quantity"], errors="coerce")
    data["Days Until Lot Expiration Source"] = pd.to_numeric(
        data["Days Until Lot Expiration"], errors="coerce"
    )
    data.insert(0, "Inventory Row ID", np.arange(1, len(data) + 1))
    return data.reset_index(drop=True)


def normalize_product_master(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    data = _rename_aliases(clean_headers(frame), PRODUCT_ALIASES)
    for column in [
        "Material Number",
        "NDC",
        "NDC Var 1",
        "NDC Var 2",
        "NDC Var 3",
        "PM Description",
        "Product Line",
        "Manufacturer",
        "Product Status",
        "Controlled Sub.",
        "Function",
        "Special Requirements",
        "Shelf Life (Months)",
        "Case-Pack",
    ]:
        if column not in data:
            data[column] = pd.NA
    data["Material Number"] = data["Material Number"].map(digits_only)
    data = data.loc[data["PM Description"].notna() | data["Material Number"].notna()].copy()
    ndc_columns = ["NDC", "NDC Var 1", "NDC Var 2", "NDC Var 3"]
    id_columns = [
        "Material Number",
        "PM Description",
        "Product Line",
        "Manufacturer",
        "Product Status",
        "Controlled Sub.",
        "Function",
        "Special Requirements",
        "Shelf Life (Months)",
        "Case-Pack",
    ]
    long = data[id_columns + ndc_columns].melt(
        id_vars=id_columns,
        value_vars=ndc_columns,
        var_name="NDC Source",
        value_name="NDC Value",
    )
    priority = {name: idx for idx, name in enumerate(ndc_columns)}
    long["NDC Priority"] = long["NDC Source"].map(priority)
    long["NDC_Key"] = long["NDC Value"].map(canonical_ndc11)
    long = long.loc[long["NDC_Key"].notna()].sort_values(["NDC Priority"])
    mapping = long.drop_duplicates("NDC_Key", keep="first").copy()
    mapping = mapping.drop(columns=["NDC Value", "NDC Priority"])
    master = data.drop_duplicates("Material Number", keep="first").reset_index(drop=True)
    return master, mapping.reset_index(drop=True)


def normalize_cogs(frame: pd.DataFrame) -> pd.DataFrame:
    data = _rename_aliases(clean_headers(frame), COGS_ALIASES)
    for column in ["Material Number", "COGS", "COGS Date", "Valid To", "per", "UoM"]:
        if column not in data:
            data[column] = pd.NA
    data["Material Number"] = data["Material Number"].map(digits_only)
    data["COGS"] = pd.to_numeric(data["COGS"], errors="coerce")
    data["COGS Date"] = pd.to_datetime(data["COGS Date"], errors="coerce")
    data["per"] = pd.to_numeric(data["per"], errors="coerce")
    valid_to = data["Valid To"].astype(str).str.replace("/", "-", regex=False)
    open_ended = valid_to.str.contains("9999", na=False)
    if open_ended.any():
        data = data.loc[open_ended].copy()
    data = data.sort_values("COGS Date", ascending=False, na_position="last")
    return data.drop_duplicates("Material Number", keep="first").reset_index(drop=True)


def _month_name(value: Any) -> str | None:
    if isinstance(value, (datetime, date, pd.Timestamp)):
        return pd.Timestamp(value).strftime("%Y-%m")
    text = clean_column_name(value)
    match = re.fullmatch(r"(20\d{2})[-_/](0?[1-9]|1[0-2])(?:[-_/]\d{1,2})?", text)
    if match:
        return f"{match.group(1)}-{int(match.group(2)):02d}"
    return None


def normalize_forecast(frame: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    data = _rename_aliases(clean_headers(frame), FORECAST_ALIASES)
    for column in ["Material Number", "Forecast NDC", "Forecast Product Description", "Forecast Status"]:
        if column not in data:
            data[column] = pd.NA
    rename_months: dict[str, str] = {}
    for column in data.columns:
        month = _month_name(column)
        if month:
            rename_months[column] = month
    data = data.rename(columns=rename_months)
    month_columns = sorted({month for month in rename_months.values() if month in data.columns})
    data["Material Number"] = data["Material Number"].map(digits_only)
    data["Forecast NDC"] = data["Forecast NDC"].map(canonical_ndc11)
    for column in month_columns:
        data[column] = pd.to_numeric(data[column], errors="coerce")
    if month_columns:
        data["Customer Master Demand"] = data[month_columns[0]]
        data["6M Average Forecast"] = data[month_columns[:6]].mean(axis=1, skipna=True)
        data["12M Forecast"] = data[month_columns[:12]].sum(axis=1, min_count=1)
        data["Forecast Start Month"] = month_columns[0]
        data["Forecast Months Available"] = len(month_columns)
    else:
        data["Customer Master Demand"] = np.nan
        data["6M Average Forecast"] = np.nan
        data["12M Forecast"] = np.nan
        data["Forecast Start Month"] = pd.NA
        data["Forecast Months Available"] = 0
    data = data.sort_values("Material Number", na_position="last")
    return data.drop_duplicates("Material Number", keep="first").reset_index(drop=True), month_columns


def infer_as_of_date(inventory: pd.DataFrame, fallback: date | None = None) -> tuple[date, float]:
    fallback = fallback or date.today()
    valid = inventory.loc[
        inventory["Lot Expiration"].notna()
        & inventory["Days Until Lot Expiration Source"].notna()
    ].copy()
    if valid.empty:
        return fallback, 0.0
    candidates = (
        valid["Lot Expiration"].dt.normalize()
        - pd.to_timedelta(valid["Days Until Lot Expiration Source"], unit="D")
    ).dt.date
    counts = candidates.value_counts()
    if counts.empty:
        return fallback, 0.0
    inferred = counts.index[0]
    confidence = float(counts.iloc[0] / counts.sum())
    return inferred, confidence


def _combine_first(data: pd.DataFrame, primary: str, fallback: str) -> None:
    if primary not in data:
        data[primary] = pd.NA
    if fallback in data:
        data[primary] = data[primary].combine_first(data[fallback])


def _month_ref(days: pd.Series) -> pd.Series:
    base = np.where(days > 365, days - 365, np.where(days > 182.5, days - 182.5, days))
    months = np.floor(base / 30.4375)
    remainder = np.mod(base, 30.4375)
    result = np.where((months == 0) & (remainder >= 15), 0.5, months)
    result = np.where(days < 0, -1, result)
    result = np.where(days.isna(), np.nan, result)
    return pd.Series(result, index=days.index, dtype="float64")


def _days_left_text(days: Any) -> str | None:
    if pd.isna(days):
        return None
    days = float(days)
    if days < 0:
        return "Expired"
    if days > 365:
        base, suffix = days - 365, "to SD"
    elif days > 182.5:
        base, suffix = days - 182.5, "to 6 M"
    else:
        base, suffix = days, "to Expire"
    months = int(np.floor(base / 30.4375))
    remaining = int(np.floor(np.mod(base, 30.4375)))
    return f"{months} months, {remaining} days {suffix}"


def derive_inventory(
    inventory: pd.DataFrame,
    product_mapping: pd.DataFrame,
    cogs: pd.DataFrame,
    forecast: pd.DataFrame,
    as_of_date: date,
) -> pd.DataFrame:
    data = inventory.copy()
    if not product_mapping.empty:
        pm_cols = [
            "NDC_Key",
            "Material Number",
            "PM Description",
            "Product Line",
            "Manufacturer",
            "Product Status",
            "Controlled Sub.",
            "Function",
            "Special Requirements",
            "Shelf Life (Months)",
            "Case-Pack",
        ]
        data = data.merge(
            product_mapping[[c for c in pm_cols if c in product_mapping]],
            on="NDC_Key",
            how="left",
            suffixes=("", " PM"),
            validate="m:1",
        )
        _combine_first(data, "Material Number", "Material Number PM")
    if "Material Number" not in data:
        data["Material Number"] = pd.NA
    data["Material Number"] = data["Material Number"].map(digits_only)
    if not cogs.empty:
        data = data.merge(
            cogs[[c for c in ["Material Number", "COGS", "COGS Date", "per", "UoM"] if c in cogs]],
            on="Material Number",
            how="left",
            validate="m:1",
        )
    else:
        data["COGS"] = np.nan
        data["COGS Date"] = pd.NaT
    forecast_keep = [
        "Material Number",
        "Customer Master Demand",
        "6M Average Forecast",
        "12M Forecast",
        "Forecast Start Month",
        "Forecast Months Available",
    ]
    if not forecast.empty:
        data = data.merge(
            forecast[[c for c in forecast_keep if c in forecast]],
            on="Material Number",
            how="left",
            validate="m:1",
        )
    else:
        for column in forecast_keep[1:]:
            data[column] = np.nan

    _combine_first(data, "Item Description Final", "Item Description")
    _combine_first(data, "Item Description Final", "PM Description")
    for column in ["Product Line", "Manufacturer", "Product Status", "Controlled Sub."]:
        if column not in data:
            data[column] = pd.NA

    as_of_ts = pd.Timestamp(as_of_date)
    data["Days To Exp"] = (data["Lot Expiration"].dt.normalize() - as_of_ts).dt.days
    days = data["Days To Exp"]
    conditions = [
        days < 0,
        (days >= 0) & (days < 182.5),
        (days >= 182.5) & (days < 273.75),
        (days >= 273.75) & (days < 365),
        (days >= 365) & (days < 456.25),
        (days >= 456.25) & (days < 547.501),
        (days >= 547.501) & (days < 730.56),
        (days >= 730.56) & (days < 1096),
        days >= 1096,
    ]
    data["Expiry Bucket"] = np.select(conditions, EXPIRY_BUCKETS[:9], default="Unknown")
    data["Date Range"] = data["Expiry Bucket"]
    data["Days Left"] = days.map(_days_left_text)
    data["Month Ref"] = _month_ref(days)
    data["LOT SD Ref"] = data["Lot Expiration"].dt.strftime("%b-%y")
    data["Dollar Amount"] = data["Quantity"] * data["COGS"]

    bucket_to_column = {
        "Expired": "Expired Qty",
        "0–6 Months": "0 ≤ X < 6",
        "6–9 Months": "6 ≤ X < 9",
        "9–12 Months": "9 ≤ X < 12",
        "12–15 Months": "12 ≤ X < 15 Qty",
        "15–18 Months": "15 ≤ X < 18",
        "18–24 Months": "18 ≤ X < 24",
        "24–36 Months": "24 ≤ X < 36",
    }
    for bucket, column in bucket_to_column.items():
        data[column] = data["Quantity"].where(data["Expiry Bucket"].eq(bucket))
        data[f"{column} Dollar Amount"] = data[column] * data["COGS"]
    data["Expired Qty Dollar Amount $ per Lot"] = data["Expired Qty"] * data["COGS"]

    long_dated_qty = (
        data[["12 ≤ X < 15 Qty", "15 ≤ X < 18", "18 ≤ X < 24", "24 ≤ X < 36"]]
        .fillna(0)
        .sum(axis=1)
    )
    demand = pd.to_numeric(data.get("Customer Master Demand"), errors="coerce")
    data["SC Demand Forecast"] = np.where(
        demand.notna() & demand.ne(0) & long_dated_qty.ne(0),
        long_dated_qty / demand,
        np.nan,
    )
    data["Provision 60%"] = np.where(
        data["9 ≤ X < 12"].notna()
        & data["Month Ref"].between(3, 6, inclusive="both"),
        data["9 ≤ X < 12"] * 0.60,
        np.nan,
    )
    data["Provision 60% Value"] = data["Provision 60%"] * data["COGS"]
    data["6 Mos Avg"] = data.get("6M Average Forecast")

    combined_status = (
        data[["Inventory Status", "Lot Status", "Product Status"]]
        .fillna("")
        .astype(str)
        .agg(" | ".join, axis=1)
        .str.lower()
    )
    recall_flag = combined_status.str.contains(r"recall", regex=True)
    restricted = combined_status.str.contains(
        r"recall|hold|quarantine|damag|destruct|blocked|embargo|inactive",
        regex=True,
    )
    inventory_status = (
        data["Inventory Status"]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.lower()
        .str.replace(r"[\s_-]+", " ", regex=True)
    )
    lot_status = (
        data["Lot Status"]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.lower()
        .str.replace(r"[\s_-]+", " ", regex=True)
    )
    product_status = data["Product Status"].fillna("").astype(str).str.strip().str.lower()
    active_inventory = inventory_status.isin(["active", "active product"])
    active_lot = lot_status.isin(["active", "short dated", "shortdated"])
    product_unavailable = product_status.str.contains(r"discontinu|inactive", regex=True)
    data["Recall Flag"] = recall_flag
    data["Restricted / Recall"] = restricted
    data["Sellable"] = active_inventory & active_lot & ~restricted & ~product_unavailable
    data["Commercial Review Eligible"] = data["Sellable"] & data["Expiry Bucket"].isin(
        ["0–6 Months", "6–9 Months", "9–12 Months"]
    )

    risk_conditions = [
        restricted,
        data["Expiry Bucket"].eq("Expired"),
        data["Expiry Bucket"].eq("0–6 Months"),
        data["Expiry Bucket"].eq("6–9 Months"),
        data["Expiry Bucket"].eq("9–12 Months"),
        data["Expiry Bucket"].isin(["12–15 Months", "15–18 Months"]),
    ]
    data["Priority"] = np.select(
        risk_conditions,
        [
            "P0 Restricted / Recall",
            "P1 Expired",
            "P1 Immediate: 0–6M",
            "P2 Monetize: 6–9M",
            "P3 Protect: 9–12M",
            "P4 Monitor: 12–18M",
        ],
        default="Routine",
    )
    data["Primary Action"] = np.select(
        risk_conditions,
        [
            "Confirm disposition, ownership and release blocker",
            "Confirm adjustment / destruction / return path",
            "Immediate sell-through, resale or donation action",
            "Channel, price and customer allocation action",
            "Demand alignment; avoid new excess and protect value",
            "FEFO monitoring and forecast alignment",
        ],
        default="Routine replenishment and FEFO monitoring",
    )
    data["Action Owner"] = np.select(
        risk_conditions,
        [
            "QA / SCM / Operations",
            "SCM / Operations / Finance",
            "Sales / Customer Service / SCM",
            "Sales / Customer Service",
            "SCM / Finance / Sales",
            "SCM / Operations",
        ],
        default="SCM",
    )
    return data


def _read_v9_sheet(workbook: Path, sheet_name: str, header: int = 0) -> pd.DataFrame:
    return clean_headers(
        pd.read_excel(workbook, sheet_name=sheet_name, header=header, dtype=object, engine="openpyxl")
    )


def extract_v9_history(workbook: Path) -> pd.DataFrame:
    report = pd.read_excel(
        workbook,
        sheet_name="Report - Inv Status",
        header=None,
        dtype=object,
        engine="openpyxl",
    )
    rows: list[dict[str, Any]] = []
    for idx in range(len(report)):
        label = str(report.iat[idx, 0]) if pd.notna(report.iat[idx, 0]) else ""
        if "Total Qty" not in label or idx + 5 >= len(report):
            continue
        value_row = report.iloc[idx + 1]
        dollars_row = report.iloc[idx + 2]
        date_row = report.iloc[idx + 5]
        raw_date = date_row.iloc[1] if len(date_row) > 1 else None
        parsed_date = pd.to_datetime(raw_date, errors="coerce")
        if pd.isna(parsed_date):
            continue
        get = lambda series, position: series.iloc[position] if position < len(series) else np.nan
        recall_qty = get(report.iloc[idx + 4], 5) if idx + 4 < len(report) else np.nan
        if isinstance(recall_qty, str):
            recall_qty = np.nan
        rows.append(
            {
                "Inventory Date": parsed_date,
                "Total Expired & SD Qty (Reported)": get(value_row, 0),
                "Total Expired & SD Value (Reported)": get(dollars_row, 0),
                "12M+ Qty (Reported)": get(value_row, 1),
                "12M+ Value (Reported)": get(dollars_row, 1),
                "Expired Qty": get(value_row, 5),
                "Expired Value": get(value_row, 6),
                "0–6M Qty": get(value_row, 7),
                "0–6M Value": get(value_row, 8),
                "6–9M Qty": get(value_row, 9),
                "6–9M Value": get(value_row, 10),
                "9–12M Qty": get(value_row, 11),
                "9–12M Value": get(value_row, 12),
                "12–15M Qty": get(value_row, 13),
                "12–15M Value": get(value_row, 14),
                "15–18M Qty": get(value_row, 15),
                "15–18M Value": get(value_row, 16),
                "18–24M Qty": get(value_row, 17),
                "18–24M Value": get(value_row, 18),
                "24–36M Qty": get(value_row, 19),
                "24–36M Value": get(value_row, 20),
                "Recall Qty": recall_qty,
                "Expired After Recall Qty": get(date_row, 5),
                "Source": "V9 historical report",
            }
        )
    return pd.DataFrame(rows).sort_values("Inventory Date").reset_index(drop=True)


def _manifest_row(
    key: str,
    path: Path | None,
    source_mode: str,
    sheet: str | None = None,
    header_row: int | None = None,
    rows: int | None = None,
    note: str = "",
) -> dict[str, Any]:
    spec = SOURCE_SPECS[key]
    return {
        "Source": spec["label"],
        "Required": "Yes" if spec["required"] else "Optional",
        "Status": "Loaded" if path is not None or source_mode == "Embedded V9" else "Missing",
        "File": path.name if path else "—",
        "Mode": source_mode,
        "Sheet": sheet or "—",
        "Header Row": header_row,
        "Rows": rows,
        "Note": note,
        "Modified UTC": (
            datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()
            if path is not None
            else "—"
        ),
    }


def _load_excel_bundle(data_dir: str | Path) -> DataBundle:
    root = Path(data_dir)
    sources = discover_sources(root)
    v9 = sources.get("v9_workbook")
    raw_frames: dict[str, pd.DataFrame] = {}
    manifest_rows: list[dict[str, Any]] = []
    warnings: list[str] = []

    v9_sheet_map = {
        "current_inventory": "CurrentInventory_Raw",
        "product_cogs": "COGS_Raw",
        "product_master": "ProductMaster_Raw",
        "forecast": "Forecast_Supply Plan",
    }
    for key, spec in SOURCE_SPECS.items():
        path = sources.get(key)
        if path:
            try:
                frame, sheet, header_row = read_excel_flexible(
                    path,
                    spec["preferred_sheets"],
                    spec["header_tokens"],
                )
                raw_frames[key] = frame
                manifest_rows.append(
                    _manifest_row(key, path, "Separate source file", sheet, header_row, len(frame))
                )
            except Exception as exc:
                warnings.append(f"{spec['label']} could not be loaded: {exc}")
                manifest_rows.append(
                    _manifest_row(key, path, "Separate source file", note=f"Load error: {exc}")
                )
        elif v9 and key in v9_sheet_map:
            sheet = v9_sheet_map[key]
            try:
                frame = _read_v9_sheet(v9, sheet, header=0)
                raw_frames[key] = frame
                manifest_rows.append(
                    _manifest_row(key, None, "Embedded V9", sheet, 1, len(frame), "Live source file not supplied")
                )
            except Exception as exc:
                warnings.append(f"Embedded {spec['label']} sheet could not be loaded: {exc}")
                manifest_rows.append(
                    _manifest_row(key, None, "Missing", note=f"Embedded load error: {exc}")
                )
        else:
            manifest_rows.append(_manifest_row(key, None, "Missing"))

    if "current_inventory" not in raw_frames:
        raise FileNotFoundError(
            "Current Inventory was not found. Put Current Inventory.xlsx or the V9 .xlsm file in data/."
        )

    inventory = normalize_inventory(raw_frames["current_inventory"])
    fallback_date = (
        datetime.fromtimestamp(sources["current_inventory"].stat().st_mtime).date()
        if sources.get("current_inventory")
        else datetime.fromtimestamp(v9.stat().st_mtime).date() if v9 else date.today()
    )
    as_of_date, as_of_confidence = infer_as_of_date(inventory, fallback_date)

    if "product_master" in raw_frames:
        product_master, product_mapping = normalize_product_master(raw_frames["product_master"])
    else:
        product_master, product_mapping = pd.DataFrame(), pd.DataFrame()
    cogs = normalize_cogs(raw_frames["product_cogs"]) if "product_cogs" in raw_frames else pd.DataFrame()
    if "forecast" in raw_frames:
        forecast, forecast_months = normalize_forecast(raw_frames["forecast"])
    else:
        forecast, forecast_months = pd.DataFrame(), []
    status_mapping = pd.DataFrame()

    enriched = derive_inventory(inventory, product_mapping, cogs, forecast, as_of_date)

    history_path = sources.get("history")
    if history_path:
        history = pd.read_csv(history_path)
        if "Inventory Date" in history:
            history["Inventory Date"] = pd.to_datetime(history["Inventory Date"], errors="coerce")
    elif v9:
        try:
            history = extract_v9_history(v9)
        except Exception as exc:
            warnings.append(f"V9 history could not be extracted: {exc}")
            history = pd.DataFrame()
    else:
        history = pd.DataFrame()

    if as_of_confidence < 0.8:
        warnings.append(
            f"Inventory as-of date confidence is {as_of_confidence:.0%}; verify the source Days Until Lot Expiration column."
        )
    return DataBundle(
        inventory=enriched,
        product_master=product_master,
        cogs=cogs,
        forecast=forecast,
        status_mapping=status_mapping,
        history=history,
        manifest=pd.DataFrame(manifest_rows),
        as_of_date=as_of_date,
        as_of_confidence=as_of_confidence,
        forecast_months=forecast_months,
        warnings=warnings,
        source_mode="Excel sources",
    )


def load_excel_bundle(data_dir: str | Path) -> DataBundle:
    """Load and enrich the four centralized BOM workbooks."""
    return _load_excel_bundle(data_dir)


def _manifest_records(manifest: pd.DataFrame) -> list[dict[str, Any]]:
    if manifest.empty:
        return []
    return json.loads(manifest.to_json(orient="records", date_format="iso"))


def save_snapshot(
    bundle: DataBundle,
    output_dir: str | Path,
    source_label: str = "Centralized BOM",
) -> tuple[Path, Path]:
    """Write the enriched lot-level dataset used by the hosted app.

    The compressed snapshot removes Excel parsing from the Streamlit startup path while
    preserving source filenames, timestamps and row counts in the metadata manifest.
    """
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    snapshot_path = root / SNAPSHOT_FILENAME
    metadata_path = root / SNAPSHOT_METADATA_FILENAME
    snapshot_temp = root / f"{SNAPSHOT_FILENAME}.tmp"
    metadata_temp = root / f"{SNAPSHOT_METADATA_FILENAME}.tmp"

    bundle.inventory.to_csv(
        snapshot_temp,
        index=False,
        compression={"method": "gzip", "compresslevel": 6, "mtime": 0},
    )
    created_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    metadata = {
        "snapshot_version": 2,
        "created_at_utc": created_at,
        "source_label": source_label,
        "as_of_date": bundle.as_of_date.isoformat(),
        "as_of_confidence": bundle.as_of_confidence,
        "inventory_rows": len(bundle.inventory),
        "forecast_months": bundle.forecast_months,
        "warnings": bundle.warnings,
        "source_manifest": _manifest_records(bundle.manifest),
        "excluded_sources": [
            {
                "label": "Product Status Mapping Master",
                "reason": "Reserved for Inventory Reconciliation Control Tower Phase 2.5.",
            }
        ],
    }
    metadata_temp.write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False, allow_nan=False),
        encoding="utf-8",
    )
    snapshot_temp.replace(snapshot_path)
    metadata_temp.replace(metadata_path)
    return snapshot_path, metadata_path


def _read_history(root: Path) -> pd.DataFrame:
    candidates = sorted(
        (path for path in root.glob("*.csv") if "inventoryhistory" in normalize_label(path.name)),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        return pd.DataFrame()
    history = pd.read_csv(candidates[0])
    if "Inventory Date" in history:
        history["Inventory Date"] = pd.to_datetime(history["Inventory Date"], errors="coerce")
    return history


def load_snapshot_bundle(data_dir: str | Path) -> DataBundle:
    root = Path(data_dir)
    snapshot_path = root / SNAPSHOT_FILENAME
    metadata_path = root / SNAPSHOT_METADATA_FILENAME
    if not snapshot_path.exists() or not metadata_path.exists():
        raise FileNotFoundError("Deploy snapshot or snapshot metadata is missing.")

    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    header = pd.read_csv(snapshot_path, compression="gzip", nrows=0).columns.tolist()
    identifier_columns = {
        "Material Number",
        "NDC 11",
        "NDC_Key",
        "Lot Number",
        "Item Number",
        "Item Number Raw",
    }
    dtype = {column: "string" for column in identifier_columns.intersection(header)}
    inventory = pd.read_csv(
        snapshot_path,
        compression="gzip",
        dtype=dtype,
        low_memory=False,
    )
    for column in ["Lot Expiration", "COGS Date"]:
        if column in inventory:
            inventory[column] = pd.to_datetime(inventory[column], errors="coerce")
    for column in ["Recall Flag", "Restricted / Recall", "Sellable", "Commercial Review Eligible"]:
        if column in inventory:
            inventory[column] = (
                inventory[column]
                .fillna(False)
                .astype(str)
                .str.strip()
                .str.lower()
                .isin(["true", "1", "yes"])
            )

    manifest = pd.DataFrame(metadata.get("source_manifest", []))
    if not manifest.empty:
        manifest["Mode"] = "Deploy snapshot"
    warnings = list(metadata.get("warnings", []))
    expected_rows = metadata.get("inventory_rows")
    if expected_rows is not None and int(expected_rows) != len(inventory):
        warnings.append(
            f"Snapshot row count mismatch: metadata={int(expected_rows):,}, loaded={len(inventory):,}."
        )
    return DataBundle(
        inventory=inventory,
        product_master=pd.DataFrame(),
        cogs=pd.DataFrame(),
        forecast=pd.DataFrame(),
        status_mapping=pd.DataFrame(),
        history=_read_history(root),
        manifest=manifest,
        as_of_date=date.fromisoformat(metadata["as_of_date"]),
        as_of_confidence=float(metadata.get("as_of_confidence", 0.0)),
        forecast_months=list(metadata.get("forecast_months", [])),
        warnings=warnings,
        source_mode="Fast deploy snapshot",
        snapshot_created_at=metadata.get("created_at_utc"),
    )


def load_bundle(data_dir: str | Path) -> DataBundle:
    """Load the fast snapshot when available; otherwise build directly from Excel."""
    root = Path(data_dir)
    force_excel = os.getenv("SKU_FORCE_EXCEL", "").strip().lower() in {"1", "true", "yes"}
    if not force_excel and (root / SNAPSHOT_FILENAME).exists() and (root / SNAPSHOT_METADATA_FILENAME).exists():
        return load_snapshot_bundle(root)
    return _load_excel_bundle(root)
