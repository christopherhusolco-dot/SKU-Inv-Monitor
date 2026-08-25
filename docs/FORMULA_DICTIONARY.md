# Formula dictionary and V9 corrections

The complete formula table is also available inside the app and every Excel export.

## Core formulas

| Field | Formula / logic |
|---|---|
| Days To Exp | `=[@[Lot Expiration]]-AsOfDateCell` |
| Dollar Amount | `=IF(OR([@Quantity]="",[@COGS]=""),"",[@Quantity]*[@COGS])` |
| Expired Qty | `=IF([@[Days To Exp]]<0,[@Quantity],"")` |
| 0–6M Qty | `=IF(AND([@[Days To Exp]]>=0,[@[Days To Exp]]<182.5),[@Quantity],"")` |
| 6–9M Qty | `=IF(AND([@[Days To Exp]]>=182.5,[@[Days To Exp]]<273.75),[@Quantity],"")` |
| 9–12M Qty | `=IF(AND([@[Days To Exp]]>=273.75,[@[Days To Exp]]<365),[@Quantity],"")` |
| 12–15M Qty | `=IF(AND([@[Days To Exp]]>=365,[@[Days To Exp]]<456.25),[@Quantity],"")` |
| 15–18M Qty | `=IF(AND([@[Days To Exp]]>=456.25,[@[Days To Exp]]<547.501),[@Quantity],"")` |
| 18–24M Qty | `=IF(AND([@[Days To Exp]]>=547.501,[@[Days To Exp]]<730.56),[@Quantity],"")` |
| 24–36M Qty | `=IF(AND([@[Days To Exp]]>=730.56,[@[Days To Exp]]<1096),[@Quantity],"")` |
| Bucket value | `=[@[Bucket Qty]]*[@COGS]` |
| 6M Average Forecast | `=AVERAGE([@[Forecast Month 1]]:[@[Forecast Month 6]])` |
| Months of Supply | `=IFERROR([@[Inventory Qty]]/[@[6M Average Forecast]],"")` |
| 12M Shortage | `=MAX([@[12M Forecast]]-[@[Sellable Qty]],0)` |
| 12M Overstock | `=MAX([@[Sellable Qty]]-[@[12M Forecast]],0)` |

## V9 60% indicator

`=IF(AND([@[9–12 Months Qty]]<>"",[@[Month Ref]]>=3,[@[Month Ref]]<=6),[@[9–12 Months Qty]]*60%,"")`

This is carried over as a management indicator only. Finance should confirm whether and how it
relates to the official accounting reserve policy.

## V9 summary formula corrections

The uploaded V9 workbook currently contains:

- `Z3 = SUM(AF2,AH2,AK2,AN2)`. `AK2` is 9–12 month quantity, not dollars, and `AN2`
  is 12–15 month value, outside the Expired & <12M definition.
- `AA3 = SUM(AP2,AR2,AT2,AV2)`. This omits 12–15 month value and 36+ value, and `AV2`
  is not a long-dated dollar bucket.
- `AA2 = SUM(AM2,AO2,AQ2,AS2)`. This omits 36+ quantity.

Streamlit does not copy those totals. It recalculates every KPI directly from the lot-level
expiry bucket and COGS, which prevents column-shift and range-extension errors.

