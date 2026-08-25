from __future__ import annotations

from io import BytesIO

import pandas as pd

from .constants import FORMULA_DICTIONARY


def build_excel_export(
    filtered: pd.DataFrame,
    sku_view: pd.DataFrame,
    action_view: pd.DataFrame,
    quality: pd.DataFrame,
    manifest: pd.DataFrame,
    kpis: dict,
    as_of_date,
) -> bytes:
    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter", datetime_format="mm/dd/yyyy") as writer:
        workbook = writer.book
        title_format = workbook.add_format(
            {"bold": True, "font_size": 18, "font_color": "#FFFFFF", "bg_color": "#17324D"}
        )
        section_format = workbook.add_format(
            {"bold": True, "font_color": "#FFFFFF", "bg_color": "#2F6B8A", "border": 0}
        )
        label_format = workbook.add_format({"bold": True, "font_color": "#344054"})
        number_format = workbook.add_format({"num_format": "#,##0"})
        currency_format = workbook.add_format({"num_format": "$#,##0.00;[Red]($#,##0.00);-"})

        summary_sheet = workbook.add_worksheet("Summary")
        writer.sheets["Summary"] = summary_sheet
        summary_sheet.hide_gridlines(2)
        summary_sheet.merge_range("A1:F2", "SKU Inventory Monitor Export", title_format)
        summary_sheet.write("A4", "Inventory As Of", label_format)
        summary_sheet.write_datetime("B4", pd.Timestamp(as_of_date).to_pydatetime(), workbook.add_format({"num_format": "mm/dd/yyyy"}))
        summary_items = [
            ("Total Inventory Qty", kpis.get("total_qty", 0), number_format),
            ("Total Inventory Value", kpis.get("total_value", 0), currency_format),
            ("Expired & <12M Qty", kpis.get("at_risk_qty", 0), number_format),
            ("Expired & <12M Value", kpis.get("at_risk_value", 0), currency_format),
            ("Expired Qty", kpis.get("expired_qty", 0), number_format),
            ("Expired Value", kpis.get("expired_value", 0), currency_format),
            ("V9 Provision 60% Qty", kpis.get("provision_qty", 0), number_format),
            ("V9 Provision 60% Value", kpis.get("provision_value", 0), currency_format),
            ("SKU Count", kpis.get("sku_count", 0), number_format),
            ("Lot Count", kpis.get("lot_count", 0), number_format),
        ]
        summary_sheet.write_row("A6", ["Metric", "Value"], section_format)
        for row, (label, value, fmt) in enumerate(summary_items, start=6):
            summary_sheet.write(row, 0, label, label_format)
            summary_sheet.write(row, 1, value, fmt)
        summary_sheet.set_column("A:A", 32)
        summary_sheet.set_column("B:B", 20)

        export_columns = [
            "Material Number",
            "NDC 11",
            "Item Description Final",
            "Product Line",
            "Manufacturer",
            "Warehouse",
            "Lot Number",
            "Lot Expiration",
            "Days To Exp",
            "Expiry Bucket",
            "Priority",
            "Action Owner",
            "Primary Action",
            "Inventory Status",
            "Lot Status",
            "Quantity",
            "COGS",
            "Dollar Amount",
            "Customer Master Demand",
            "6M Average Forecast",
            "12M Forecast",
            "Provision 60%",
            "Provision 60% Value",
            "Product Status",
            "Controlled Sub.",
            "Recall Flag",
            "Restricted / Recall",
            "Sellable",
            "Commercial Review Eligible",
            "Shelf Life (Months)",
            "Case-Pack",
        ]
        detail = filtered[[c for c in export_columns if c in filtered]].copy()
        detail.to_excel(writer, sheet_name="Lot Detail", index=False)
        sku_view.to_excel(writer, sheet_name="SKU Summary", index=False)
        action_view.to_excel(writer, sheet_name="Action Queue", index=False)
        quality.to_excel(writer, sheet_name="Data Quality", index=False)
        manifest.to_excel(writer, sheet_name="Source Manifest", index=False)
        pd.DataFrame(FORMULA_DICTIONARY).to_excel(writer, sheet_name="Formula Dictionary", index=False)

        for sheet_name, frame in [
            ("Lot Detail", detail),
            ("SKU Summary", sku_view),
            ("Action Queue", action_view),
            ("Data Quality", quality),
            ("Source Manifest", manifest),
            ("Formula Dictionary", pd.DataFrame(FORMULA_DICTIONARY)),
        ]:
            sheet = writer.sheets[sheet_name]
            sheet.freeze_panes(1, 0)
            sheet.autofilter(0, 0, max(len(frame), 1), max(len(frame.columns) - 1, 0))
            sheet.set_row(0, 32, section_format)
            for idx, column in enumerate(frame.columns):
                width = min(max(len(str(column)) + 2, 12), 40)
                if "Description" in str(column) or "Action" in str(column) or "Impact" in str(column):
                    width = 34
                sheet.set_column(idx, idx, width)
    return output.getvalue()
