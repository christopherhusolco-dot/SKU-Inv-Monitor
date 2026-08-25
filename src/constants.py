from __future__ import annotations

from collections import OrderedDict
from pathlib import Path
import tomllib

APP_TITLE = "SKU Inventory Monitor"
APP_VERSION = "2.0.0"
EXCLUDED_SOURCE_LABEL = "Product Status Mapping Master"

_REGISTRY_PATH = Path(__file__).resolve().parents[1] / "config" / "source_registry.toml"


def _load_source_specs() -> OrderedDict[str, dict]:
    with _REGISTRY_PATH.open("rb") as handle:
        registry = tomllib.load(handle)
    return OrderedDict((item["key"], item) for item in registry["sources"])


SOURCE_SPECS = _load_source_specs()

EXPIRY_BUCKETS = [
    "Expired",
    "0–6 Months",
    "6–9 Months",
    "9–12 Months",
    "12–15 Months",
    "15–18 Months",
    "18–24 Months",
    "24–36 Months",
    "36+ Months",
    "Unknown",
]

BUCKET_COLORS = {
    "Expired": "#B42318",
    "0–6 Months": "#E5484D",
    "6–9 Months": "#F5A524",
    "9–12 Months": "#4E79A7",
    "12–15 Months": "#8DBF67",
    "15–18 Months": "#5FAE61",
    "18–24 Months": "#388E5A",
    "24–36 Months": "#146C43",
    "36+ Months": "#1B4F72",
    "Unknown": "#98A2B3",
}

FORMULA_DICTIONARY = [
    {
        "Field": "NDC_Key",
        "Excel formula": "=LET(d,TEXTJOIN(\"\",TRUE,IFERROR(MID([@[Item Number]],SEQUENCE(LEN([@[Item Number]])),1)*1,\"\")),IF(LEN(d)=10,LEFT(d,5)&\"0\"&MID(d,6,3)&RIGHT(d,2),d))",
        "V9 / Streamlit logic": "Keep digits only; normalize 10-digit 5-3-2 NDC to 11 digits by inserting 0 in the product segment.",
        "Unit": "Identifier",
    },
    {
        "Field": "Days To Exp",
        "Excel formula": "=[@[Lot Expiration]]-AsOfDateCell",
        "V9 / Streamlit logic": "Calendar days between Lot Expiration and the inferred inventory as-of date.",
        "Unit": "Days",
    },
    {
        "Field": "Dollar Amount",
        "Excel formula": "=IF(OR([@Quantity]=\"\",[@COGS]=\"\"),\"\",[@Quantity]*[@COGS])",
        "V9 / Streamlit logic": "Quantity × latest open-ended Product COGS.",
        "Unit": "USD",
    },
    {
        "Field": "Expired Qty",
        "Excel formula": "=IF([@[Days To Exp]]<0,[@Quantity],\"\")",
        "V9 / Streamlit logic": "Quantity when Days To Exp < 0.",
        "Unit": "EA",
    },
    {
        "Field": "0–6 Months Qty",
        "Excel formula": "=IF(AND([@[Days To Exp]]>=0,[@[Days To Exp]]<182.5),[@Quantity],\"\")",
        "V9 / Streamlit logic": "0 ≤ Days To Exp < 182.5.",
        "Unit": "EA",
    },
    {
        "Field": "6–9 Months Qty",
        "Excel formula": "=IF(AND([@[Days To Exp]]>=182.5,[@[Days To Exp]]<273.75),[@Quantity],\"\")",
        "V9 / Streamlit logic": "182.5 ≤ Days To Exp < 273.75.",
        "Unit": "EA",
    },
    {
        "Field": "9–12 Months Qty",
        "Excel formula": "=IF(AND([@[Days To Exp]]>=273.75,[@[Days To Exp]]<365),[@Quantity],\"\")",
        "V9 / Streamlit logic": "273.75 ≤ Days To Exp < 365.",
        "Unit": "EA",
    },
    {
        "Field": "12–15 Months Qty",
        "Excel formula": "=IF(AND([@[Days To Exp]]>=365,[@[Days To Exp]]<456.25),[@Quantity],\"\")",
        "V9 / Streamlit logic": "365 ≤ Days To Exp < 456.25.",
        "Unit": "EA",
    },
    {
        "Field": "15–18 Months Qty",
        "Excel formula": "=IF(AND([@[Days To Exp]]>=456.25,[@[Days To Exp]]<547.501),[@Quantity],\"\")",
        "V9 / Streamlit logic": "456.25 ≤ Days To Exp < 547.501.",
        "Unit": "EA",
    },
    {
        "Field": "18–24 Months Qty",
        "Excel formula": "=IF(AND([@[Days To Exp]]>=547.501,[@[Days To Exp]]<730.56),[@Quantity],\"\")",
        "V9 / Streamlit logic": "547.501 ≤ Days To Exp < 730.56.",
        "Unit": "EA",
    },
    {
        "Field": "24–36 Months Qty",
        "Excel formula": "=IF(AND([@[Days To Exp]]>=730.56,[@[Days To Exp]]<1096),[@Quantity],\"\")",
        "V9 / Streamlit logic": "730.56 ≤ Days To Exp < 1096.",
        "Unit": "EA",
    },
    {
        "Field": "Bucket Dollar Amount",
        "Excel formula": "=IF([@[Bucket Qty]]=\"\",\"\",[@[Bucket Qty]]*[@COGS])",
        "V9 / Streamlit logic": "Each expiry-bucket quantity × COGS.",
        "Unit": "USD",
    },
    {
        "Field": "Customer Master Demand",
        "Excel formula": "=XLOOKUP([@[Material Number]],Forecast[ SAP Mat No. ],Forecast[First Forecast Month],\"\")",
        "V9 / Streamlit logic": "First chronologically sorted YYYY-MM column in Forecast_Supply Plan.",
        "Unit": "EA / month",
    },
    {
        "Field": "Long-Dated Coverage Ratio (V9: SC Demand Forecast)",
        "Excel formula": "=IFERROR(SUM([@[12–15 Months Qty]]:[@[24–36 Months Qty]])/[@[Customer Master Demand]],\"\")",
        "V9 / Streamlit logic": "12–36 month inventory quantity ÷ first-month demand.",
        "Unit": "Ratio",
    },
    {
        "Field": "V9 Provision 60% Qty",
        "Excel formula": "=IF(AND([@[9–12 Months Qty]]<>\"\",[@[Month Ref]]>=3,[@[Month Ref]]<=6),[@[9–12 Months Qty]]*60%,\"\")",
        "V9 / Streamlit logic": "60% of 9–12 month quantity only when V9 Month Ref is 3 through 6; management indicator, not an accounting-policy conclusion.",
        "Unit": "EA",
    },
    {
        "Field": "6M Average Forecast",
        "Excel formula": "=AVERAGE([@[Forecast Month 1]]:[@[Forecast Month 6]])",
        "V9 / Streamlit logic": "Average of the first six available forecast month columns. V9 left this field blank; Streamlit completes it.",
        "Unit": "EA / month",
    },
    {
        "Field": "Months of Supply",
        "Excel formula": "=IFERROR([@[Inventory Qty]]/[@[6M Average Forecast]],\"\")",
        "V9 / Streamlit logic": "SKU total inventory ÷ six-month average monthly forecast.",
        "Unit": "Months",
    },
]
