from __future__ import annotations

import os
from html import escape
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

from src.analytics import (
    action_queue,
    aggregate_by_bucket,
    append_current_history,
    calculate_kpis,
    data_quality_checks,
    sku_summary,
)
from src.constants import (
    APP_TITLE,
    APP_VERSION,
    BUCKET_COLORS,
    EXCLUDED_SOURCE_LABEL,
    EXPIRY_BUCKETS,
    FORMULA_DICTIONARY,
    SOURCE_SPECS,
)
from src.data_pipeline import load_bundle, source_signature
from src.export_excel import build_excel_export
from src.styles import APP_CSS


APP_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv("SKU_DATA_DIR", APP_DIR / "data"))

NAV_ITEMS = [
    "Enterprise Overview",
    "CFO / Finance",
    "SCM Planning",
    "Operations",
    "Sales / Customer Service",
    "Lot Explorer",
    "Data Quality & Refresh",
]
NAV_LABELS = {
    "Enterprise Overview": "▦  Enterprise Overview",
    "CFO / Finance": "$  CFO / Finance",
    "SCM Planning": "↗  SCM Planning",
    "Operations": "▤  Operations",
    "Sales / Customer Service": "◎  Sales / Customer Service",
    "Lot Explorer": "⌕  Lot Explorer",
    "Data Quality & Refresh": "✓  Data Quality & Refresh",
}
PAGE_SUBTITLES = {
    "Enterprise Overview": "One governed inventory view for every commercial and operating team.",
    "CFO / Finance": "Inventory value exposure, COGS coverage and management provision indicators.",
    "SCM Planning": "Demand coverage, shortage, overstock and expiry signals by SKU.",
    "Operations": "Restricted inventory, expired lots and the operational action queue.",
    "Sales / Customer Service": "Commercial-review candidates for short-dated inventory action.",
    "Lot Explorer": "Search, inspect and download the filtered lot-level inventory view.",
    "Data Quality & Refresh": "Source lineage, data checks, formulas and snapshot refresh status.",
}


st.set_page_config(
    page_title=APP_TITLE,
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.markdown(APP_CSS, unsafe_allow_html=True)


@st.cache_data(show_spinner=False)
def cached_bundle(data_dir: str, signature: str):
    del signature
    return load_bundle(data_dir)


def fmt_qty(value: float | int) -> str:
    return f"{float(value or 0):,.0f}"


def fmt_money(value: float | int) -> str:
    value = float(value or 0)
    if abs(value) >= 1_000_000:
        return f"${value / 1_000_000:,.2f}M"
    if abs(value) >= 1_000:
        return f"${value / 1_000:,.1f}K"
    return f"${value:,.0f}"


def chart_layout(fig, height: int = 345):
    fig.update_layout(
        height=height,
        margin=dict(l=8, r=8, t=18, b=8),
        paper_bgcolor="white",
        plot_bgcolor="white",
        font=dict(family="Inter, Segoe UI, Arial", color="#526174", size=11),
        legend_title_text="",
        hoverlabel=dict(bgcolor="white"),
    )
    fig.update_xaxes(showgrid=False, linecolor="#E4EAF0", tickfont=dict(size=10))
    fig.update_yaxes(gridcolor="#EEF2F6", zeroline=False, tickfont=dict(size=10))
    return fig


def section_title(title: str, subtitle: str | None = None) -> None:
    st.markdown(f'<div class="section-title">{escape(title)}</div>', unsafe_allow_html=True)
    if subtitle:
        st.markdown(f'<div class="section-subtitle">{escape(subtitle)}</div>', unsafe_allow_html=True)


def metric_cards(cards: list[tuple[str, str, str, str]]) -> None:
    columns = st.columns(len(cards))
    for column, (label, value, foot, tone) in zip(columns, cards):
        with column:
            st.markdown(
                f"""
                <div class="kpi-card {escape(tone)}">
                    <div class="kpi-label">{escape(label)}</div>
                    <div class="kpi-value">{escape(value)}</div>
                    <div class="kpi-foot">{escape(foot)}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def team_cards(cards: list[tuple[str, str, str]]) -> None:
    columns = st.columns(len(cards))
    for column, (team, value, note) in zip(columns, cards):
        with column:
            st.markdown(
                f"""
                <div class="team-card">
                    <div class="team-name">{escape(team)}</div>
                    <div class="team-value">{escape(value)}</div>
                    <div class="team-note">{escape(note)}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def render_sidebar(bundle) -> str:
    st.sidebar.markdown(
        """
        <div class="sidebar-brand">
            <span class="brand-mark">▦</span><span class="brand-name">SKU Inventory Monitor</span>
            <div class="brand-subtitle">Enterprise Control Tower</div>
        </div>
        <div class="sidebar-label">Team views</div>
        """,
        unsafe_allow_html=True,
    )
    page = st.sidebar.radio(
        "Team views",
        NAV_ITEMS,
        format_func=lambda item: NAV_LABELS[item],
        label_visibility="collapsed",
        key="nav_page",
    )

    manifest = bundle.manifest if bundle.manifest is not None else pd.DataFrame()
    source_items: list[str] = []
    for spec in SOURCE_SPECS.values():
        label = spec["label"]
        row = manifest.loc[manifest.get("Source", pd.Series(dtype=str)).eq(label)] if not manifest.empty else pd.DataFrame()
        loaded = not row.empty and str(row.iloc[0].get("Status", "")).lower() == "loaded"
        source_items.append(
            f'<div class="source-item"><span class="source-dot {"" if loaded else "missing"}"></span>'
            f'<span>{escape(label)}</span></div>'
        )
    st.sidebar.markdown(
        '<div class="sidebar-label">Governed sources</div>'
        f'<div class="source-list">{"".join(source_items)}</div>'
        f'<div class="excluded-source"><strong>{escape(EXCLUDED_SOURCE_LABEL)}</strong><br>'
        "Not used in this app — reserved for Inventory Reconciliation Phase 2.5.</div>",
        unsafe_allow_html=True,
    )
    st.sidebar.caption(f"v{APP_VERSION} · {bundle.source_mode}")
    return page


def render_header(page: str, bundle) -> None:
    loaded_count = 0
    if not bundle.manifest.empty and "Status" in bundle.manifest:
        loaded_count = int(bundle.manifest["Status"].eq("Loaded").sum())
    title = "Enterprise Inventory Overview" if page == "Enterprise Overview" else page
    snapshot_badge = "Fast deploy snapshot" if "snapshot" in bundle.source_mode.lower() else "Direct Excel mode"
    st.markdown(
        f"""
        <div class="app-header">
            <div>
                <h1>{escape(title)}</h1>
                <p>{escape(PAGE_SUBTITLES[page])}</p>
            </div>
            <div class="header-badges">
                <span class="header-badge">Data as of {bundle.as_of_date:%b %d, %Y}</span>
                <span class="header-badge live">{loaded_count} governed sources</span>
                <span class="header-badge">{escape(snapshot_badge)}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _filter_options(frame: pd.DataFrame, column: str) -> list[str]:
    if column not in frame:
        return ["All"]
    values = sorted(frame[column].dropna().astype(str).str.strip().loc[lambda item: item.ne("")].unique())
    return ["All", *values]


def render_filter_bar(frame: pd.DataFrame) -> pd.DataFrame:
    with st.container(border=True):
        columns = st.columns([2.2, 1.25, 1.05, 1.05, 1.05])
        search = columns[0].text_input(
            "Search SKU / NDC / lot",
            placeholder="Product, material, NDC or lot…",
            key="global_search",
        )
        product_line = columns[1].selectbox(
            "Product line",
            _filter_options(frame, "Product Line"),
            key="filter_product_line",
        )
        inventory_status = columns[2].selectbox(
            "Inventory status",
            _filter_options(frame, "Inventory Status"),
            key="filter_inventory_status",
        )
        lot_status = columns[3].selectbox(
            "Lot status",
            _filter_options(frame, "Lot Status"),
            key="filter_lot_status",
        )
        recall_mode = columns[4].selectbox(
            "Recall view",
            ["Recall excluded", "All inventory", "Recall only"],
            key="filter_recall",
        )

        filtered = frame.copy()
        if recall_mode == "Recall excluded":
            filtered = filtered.loc[~filtered["Recall Flag"]].copy()
        elif recall_mode == "Recall only":
            filtered = filtered.loc[filtered["Recall Flag"]].copy()
        for column_name, selected in [
            ("Product Line", product_line),
            ("Inventory Status", inventory_status),
            ("Lot Status", lot_status),
        ]:
            if selected != "All" and column_name in filtered:
                filtered = filtered.loc[filtered[column_name].astype(str).eq(selected)].copy()
        if search.strip():
            needle = search.strip().lower()
            search_columns = [
                "Material Number",
                "NDC 11",
                "NDC_Key",
                "Item Description Final",
                "Product Line",
                "Lot Number",
            ]
            mask = pd.Series(False, index=filtered.index)
            for column_name in search_columns:
                if column_name in filtered:
                    mask |= (
                        filtered[column_name]
                        .fillna("")
                        .astype(str)
                        .str.lower()
                        .str.contains(needle, regex=False)
                    )
            filtered = filtered.loc[mask].copy()
        st.caption(f"Showing {len(filtered):,} of {len(frame):,} lot/status rows")
    return filtered


def render_bucket_chart(frame: pd.DataFrame, metric: str = "Inventory Value", height: int = 335) -> None:
    bucket = aggregate_by_bucket(frame)
    y = "Quantity" if metric == "Quantity" else "Inventory Value"
    fig = px.bar(
        bucket,
        x="Expiry Bucket",
        y=y,
        color="Expiry Bucket",
        color_discrete_map=BUCKET_COLORS,
        category_orders={"Expiry Bucket": EXPIRY_BUCKETS},
        text_auto=".3s",
    )
    fig.update_traces(textposition="outside", cliponaxis=False, hovertemplate="%{x}<br>%{y:,.2f}<extra></extra>")
    fig.update_layout(showlegend=False)
    fig.update_yaxes(tickprefix="$" if y == "Inventory Value" else "", tickformat="~s")
    st.plotly_chart(chart_layout(fig, height), use_container_width=True, config={"displayModeBar": False})


def render_risk_product_lines(frame: pd.DataFrame, height: int = 335) -> None:
    risk = frame.loc[frame["Expiry Bucket"].isin(EXPIRY_BUCKETS[:4])].copy()
    risk["Product Line"] = risk["Product Line"].fillna("Unmapped")
    top = (
        risk.groupby("Product Line", dropna=False)["Dollar Amount"]
        .sum()
        .nlargest(10)
        .sort_values()
        .reset_index()
    )
    if top.empty:
        st.info("No expired or <12-month inventory under the current filters.")
        return
    fig = px.bar(
        top,
        x="Dollar Amount",
        y="Product Line",
        orientation="h",
        color_discrete_sequence=["#2F6B8A"],
        text_auto=".3s",
    )
    fig.update_traces(hovertemplate="%{y}<br>$%{x:,.2f}<extra></extra>")
    fig.update_xaxes(tickprefix="$", tickformat="~s")
    st.plotly_chart(chart_layout(fig, height), use_container_width=True, config={"displayModeBar": False})


def render_priority_table(frame: pd.DataFrame, rows: int = 12) -> None:
    queue = action_queue(frame).head(rows)
    columns = [
        "Priority",
        "Action Owner",
        "Item Description Final",
        "Product Line",
        "Lot Number",
        "Lot Expiration",
        "Expiry Bucket",
        "Quantity",
        "Dollar Amount",
        "Primary Action",
    ]
    st.dataframe(
        queue[[column for column in columns if column in queue]],
        use_container_width=True,
        hide_index=True,
        column_config={
            "Lot Expiration": st.column_config.DateColumn(format="MM/DD/YYYY"),
            "Quantity": st.column_config.NumberColumn(format="%.0f"),
            "Dollar Amount": st.column_config.NumberColumn(format="$%.2f"),
        },
    )


def render_overview(frame: pd.DataFrame, bundle) -> None:
    kpis = calculate_kpis(frame)
    sku = sku_summary(frame)
    commercial = frame.loc[frame.get("Commercial Review Eligible", False)].copy()
    restricted_qty = frame.loc[frame["Restricted / Recall"], "Quantity"].sum()
    overstock_qty = sku.loc[sku["Coverage Status"].eq("Overstock"), "12M Overstock Qty"].sum() if not sku.empty else 0

    metric_cards(
        [
            ("Total Inventory Qty", fmt_qty(kpis["total_qty"]), "Current filtered inventory", ""),
            ("Inventory Value", fmt_money(kpis["total_value"]), "Quantity × latest COGS", "good"),
            ("Expired & <12M Qty", fmt_qty(kpis["at_risk_qty"]), "Immediate cross-team attention", "warn"),
            ("Expired & <12M Value", fmt_money(kpis["at_risk_value"]), "Value exposure under 12 months", "risk"),
            ("Expired Value", fmt_money(kpis["expired_value"]), f"{fmt_qty(kpis['expired_qty'])} expired units", "risk"),
            ("SKUs / Lots", f"{kpis['sku_count']:,} / {kpis['lot_count']:,}", "Distinct NDCs and lots", ""),
        ]
    )

    st.write("")
    left, right = st.columns([1.18, .82])
    with left:
        with st.container(border=True):
            section_title("Inventory Value by Expiry Bucket", "All values are recalculated from lot quantity × latest open-ended COGS.")
            render_bucket_chart(frame, "Inventory Value")
    with right:
        with st.container(border=True):
            section_title("At-Risk Value by Product Line", "Expired plus 0–12 month inventory.")
            render_risk_product_lines(frame)

    section_title("Priority Action Queue", "Highest-priority open lot/status rows in the current view.")
    render_priority_table(frame)

    section_title("Team Action Views", "The same governed dataset, translated into each team's working signal.")
    team_cards(
        [
            ("CFO / Finance", fmt_money(kpis["at_risk_value"]), "Expired and <12M value exposure"),
            ("SCM", fmt_qty(overstock_qty), "Potential 12M overstock units"),
            ("Operations", fmt_qty(restricted_qty), "Restricted / recall units in view"),
            ("Sales", fmt_money(commercial["Dollar Amount"].sum()), "0–12M commercial review pool"),
            ("Customer Service", f"{commercial['Lot Number'].nunique():,} lots", "Candidate lots for customer action"),
        ]
    )

    history = append_current_history(
        bundle.history,
        bundle.inventory.loc[~bundle.inventory["Recall Flag"]],
        bundle.as_of_date,
    )
    if not history.empty:
        with st.expander("Historical expired & <12M trend"):
            trend = history.dropna(subset=["Inventory Date"]).copy()
            fig = px.line(
                trend,
                x="Inventory Date",
                y="Total Expired & SD Qty (Reported)",
                markers=True,
                color_discrete_sequence=["#D92D20"],
                hover_data=["Source"] if "Source" in trend else None,
            )
            fig.update_yaxes(tickformat="~s")
            st.plotly_chart(chart_layout(fig, 320), use_container_width=True, config={"displayModeBar": False})
            st.caption("Historical V9 snapshots plus the latest recalculated, recall-excluded point.")


def render_finance(frame: pd.DataFrame) -> None:
    kpis = calculate_kpis(frame)
    valued_rate = frame["Dollar Amount"].notna().mean() if len(frame) else 0.0
    metric_cards(
        [
            ("Inventory Value", fmt_money(kpis["total_value"]), "Filtered gross inventory value", "good"),
            ("At-Risk Value", fmt_money(kpis["at_risk_value"]), "Expired plus <12 months", "risk"),
            ("Expired Value", fmt_money(kpis["expired_value"]), "Past lot expiration date", "risk"),
            ("60% Indicator", fmt_money(kpis["provision_value"]), "V9 management indicator", "warn"),
            ("Rows Valued", f"{valued_rate:.1%}", "Rows with mapped COGS", ""),
        ]
    )
    st.markdown(
        '<div class="callout">The 60% provision is a preserved V9 management indicator, not a final accounting reserve policy. Finance approval remains required.</div>',
        unsafe_allow_html=True,
    )
    left, right = st.columns(2)
    with left:
        with st.container(border=True):
            section_title("Inventory Value by Expiry Bucket")
            render_bucket_chart(frame, "Inventory Value")
    with right:
        with st.container(border=True):
            section_title("Top SKUs by At-Risk Value")
            risk = sku_summary(frame).nlargest(15, "At Risk Value").sort_values("At Risk Value")
            if risk.empty:
                st.info("No at-risk SKU value under the current filters.")
            else:
                fig = px.bar(
                    risk,
                    x="At Risk Value",
                    y="Item Description Final",
                    orientation="h",
                    color_discrete_sequence=["#B42318"],
                    text_auto=".3s",
                )
                fig.update_xaxes(tickprefix="$", tickformat="~s")
                st.plotly_chart(chart_layout(fig), use_container_width=True, config={"displayModeBar": False})

    section_title("60% Provision Indicator Detail")
    provision = frame.loc[frame["Provision 60%"].notna()].copy()
    if provision.empty:
        st.success("No rows meet the V9 60% indicator under the current filters.")
    else:
        detail = (
            provision.groupby(
                ["Material Number", "NDC 11", "Item Description Final", "Product Line"],
                dropna=False,
            )
            .agg(
                **{
                    "9–12M Qty": ("9 ≤ X < 12", "sum"),
                    "Indicator Qty": ("Provision 60%", "sum"),
                    "Indicator Value": ("Provision 60% Value", "sum"),
                    "Earliest Expiration": ("Lot Expiration", "min"),
                }
            )
            .reset_index()
            .sort_values("Indicator Value", ascending=False)
        )
        st.dataframe(
            detail,
            use_container_width=True,
            hide_index=True,
            column_config={
                "9–12M Qty": st.column_config.NumberColumn(format="%.0f"),
                "Indicator Qty": st.column_config.NumberColumn(format="%.0f"),
                "Indicator Value": st.column_config.NumberColumn(format="$%.2f"),
                "Earliest Expiration": st.column_config.DateColumn(format="MM/DD/YYYY"),
            },
        )


def render_scm(frame: pd.DataFrame) -> None:
    sku = sku_summary(frame)
    shortage = sku["12M Shortage Qty"].sum() if not sku.empty else 0
    overstock = sku["12M Overstock Qty"].sum() if not sku.empty else 0
    no_forecast = int(sku["Coverage Status"].eq("No Forecast").sum()) if not sku.empty else 0
    sellable_qty = frame.loc[frame["Sellable"], "Quantity"].sum()
    metric_cards(
        [
            ("Inventory Qty", fmt_qty(frame["Quantity"].sum()), "All filtered lot/status rows", ""),
            ("Operationally Available", fmt_qty(sellable_qty), "Active and short-dated status pool", "good"),
            ("12M Shortage Signal", fmt_qty(shortage), "Forecast minus available inventory", "risk"),
            ("12M Overstock Signal", fmt_qty(overstock), "Available inventory minus forecast", "warn"),
            ("SKUs Missing Forecast", f"{no_forecast:,}", "Requires SCM source review", ""),
        ]
    )
    left, right = st.columns([.78, 1.22])
    with left:
        with st.container(border=True):
            section_title("SKU Coverage Status")
            coverage = sku["Coverage Status"].value_counts().rename_axis("Coverage Status").reset_index(name="SKU Count")
            if coverage.empty:
                st.info("No SKU coverage results.")
            else:
                fig = px.bar(
                    coverage,
                    x="Coverage Status",
                    y="SKU Count",
                    color="Coverage Status",
                    color_discrete_map={
                        "Supply Risk": "#D92D20",
                        "Balanced": "#16865B",
                        "Watch": "#F5A524",
                        "Overstock": "#7A5AF8",
                        "No Forecast": "#98A2B3",
                    },
                    text_auto=True,
                )
                fig.update_layout(showlegend=False)
                st.plotly_chart(chart_layout(fig), use_container_width=True, config={"displayModeBar": False})
    with right:
        with st.container(border=True):
            section_title("Months of Supply vs. At-Risk Value")
            scatter = sku.loc[sku["Months of Supply"].notna()].copy()
            if scatter.empty:
                st.info("No mapped forecast coverage under the current filters.")
            else:
                scatter["Bubble Size"] = scatter["Inventory Value"].fillna(0).clip(lower=1)
                fig = px.scatter(
                    scatter,
                    x="Months of Supply",
                    y="At Risk Value",
                    size="Bubble Size",
                    color="Coverage Status",
                    hover_name="Item Description Final",
                    hover_data=["Material Number", "Inventory Qty", "6M Avg Forecast", "Earliest Expiration"],
                    color_discrete_map={
                        "Supply Risk": "#D92D20",
                        "Balanced": "#16865B",
                        "Watch": "#F5A524",
                        "Overstock": "#7A5AF8",
                    },
                    size_max=38,
                )
                fig.update_yaxes(tickprefix="$", tickformat="~s")
                st.plotly_chart(chart_layout(fig), use_container_width=True, config={"displayModeBar": False})

    section_title("SKU Supply / Excess Signals")
    columns = [
        "Material Number",
        "NDC 11",
        "Item Description Final",
        "Product Line",
        "Inventory Qty",
        "At Risk Qty",
        "6M Avg Forecast",
        "12M Forecast",
        "Months of Supply",
        "12M Shortage Qty",
        "12M Overstock Qty",
        "Coverage Status",
        "Earliest Expiration",
    ]
    st.dataframe(
        sku[[column for column in columns if column in sku]],
        use_container_width=True,
        hide_index=True,
        column_config={
            "Inventory Qty": st.column_config.NumberColumn(format="%.0f"),
            "At Risk Qty": st.column_config.NumberColumn(format="%.0f"),
            "6M Avg Forecast": st.column_config.NumberColumn(format="%.1f"),
            "12M Forecast": st.column_config.NumberColumn(format="%.0f"),
            "Months of Supply": st.column_config.NumberColumn(format="%.1f"),
            "12M Shortage Qty": st.column_config.NumberColumn(format="%.0f"),
            "12M Overstock Qty": st.column_config.NumberColumn(format="%.0f"),
            "Earliest Expiration": st.column_config.DateColumn(format="MM/DD/YYYY"),
        },
    )


def render_operations(frame: pd.DataFrame) -> None:
    kpis = calculate_kpis(frame)
    queue = action_queue(frame)
    restricted = frame.loc[frame["Restricted / Recall"], "Quantity"].sum()
    warehouses = frame["Warehouse"].nunique(dropna=True) if "Warehouse" in frame else 0
    metric_cards(
        [
            ("Restricted / Recall Qty", fmt_qty(restricted), "Hold, recall, damage or blocker status", "risk"),
            ("Expired Qty", fmt_qty(kpis["expired_qty"]), "Past lot expiration date", "risk"),
            ("Open Action Rows", f"{len(queue):,}", "Non-routine priority rows", "warn"),
            ("Action Lots", f"{queue['Lot Number'].nunique():,}", "Distinct lots requiring review", "warn"),
            ("Warehouses", f"{warehouses:,}", "Locations represented in view", ""),
        ]
    )
    left, right = st.columns(2)
    with left:
        with st.container(border=True):
            section_title("Action Quantity by Priority")
            priority = queue.groupby("Priority", dropna=False)["Quantity"].sum().reset_index()
            if priority.empty:
                st.success("No open operational actions under the current filters.")
            else:
                fig = px.bar(
                    priority,
                    x="Priority",
                    y="Quantity",
                    color="Priority",
                    text_auto=".3s",
                    color_discrete_sequence=["#B42318", "#E5484D", "#F5A524", "#4E79A7", "#7A5AF8"],
                )
                fig.update_layout(showlegend=False)
                fig.update_yaxes(tickformat="~s")
                st.plotly_chart(chart_layout(fig), use_container_width=True, config={"displayModeBar": False})
    with right:
        with st.container(border=True):
            section_title("Inventory / Lot Status Quantity")
            status = frame.copy()
            status["Status Pair"] = (
                status["Inventory Status"].fillna("Unknown").astype(str)
                + " / "
                + status["Lot Status"].fillna("Unknown").astype(str)
            )
            status = status.groupby("Status Pair")["Quantity"].sum().nlargest(12).sort_values().reset_index()
            fig = px.bar(
                status,
                x="Quantity",
                y="Status Pair",
                orientation="h",
                color_discrete_sequence=["#2F6B8A"],
                text_auto=".3s",
            )
            fig.update_xaxes(tickformat="~s")
            st.plotly_chart(chart_layout(fig), use_container_width=True, config={"displayModeBar": False})
    section_title("Operations Action Queue")
    render_priority_table(frame, rows=30)


def render_sales(frame: pd.DataFrame) -> None:
    candidates = frame.loc[frame["Commercial Review Eligible"]].copy()
    controlled = (
        candidates["Controlled Sub."]
        .fillna("")
        .astype(str)
        .str.lower()
        .str.contains(r"yes|c-?ii|c-?iii|c-?iv|c-?v", regex=True)
    )
    candidates["Channel Review"] = np.where(controlled, "Controlled — additional review", "Standard review")
    kpis = calculate_kpis(candidates)
    metric_cards(
        [
            ("Review Pool Qty", fmt_qty(kpis["total_qty"]), "Active / short-dated, 0–12M", "warn"),
            ("Review Pool Value", fmt_money(kpis["total_value"]), "Potential value recovery pool", "good"),
            ("Candidate SKUs", f"{kpis['sku_count']:,}", "Distinct NDCs", ""),
            ("Candidate Lots", f"{kpis['lot_count']:,}", "Distinct lots", ""),
            ("Controlled Review Rows", f"{int(controlled.sum()):,}", "Requires additional channel review", "risk"),
        ]
    )
    st.markdown(
        '<div class="callout">This is a commercial review pool, not final sale authorization. QA, Regulatory, contract, customer and channel requirements still apply.</div>',
        unsafe_allow_html=True,
    )
    if candidates.empty:
        st.success("No 0–12 month commercial-review candidates under the current filters.")
        return
    left, right = st.columns(2)
    with left:
        with st.container(border=True):
            section_title("Review Pool by Expiry Bucket")
            render_bucket_chart(candidates, "Quantity")
    with right:
        with st.container(border=True):
            section_title("Top Candidate SKUs by Quantity")
            top = (
                candidates.groupby(["Item Description Final", "Product Line"], dropna=False)
                .agg(Quantity=("Quantity", "sum"), Value=("Dollar Amount", "sum"))
                .reset_index()
                .nlargest(15, "Quantity")
                .sort_values("Quantity")
            )
            fig = px.bar(
                top,
                x="Quantity",
                y="Item Description Final",
                orientation="h",
                color="Product Line",
                text_auto=".3s",
            )
            fig.update_xaxes(tickformat="~s")
            st.plotly_chart(chart_layout(fig), use_container_width=True, config={"displayModeBar": False})

    section_title("Sales & Customer Service Action List")
    columns = [
        "Expiry Bucket",
        "Material Number",
        "NDC 11",
        "Item Description Final",
        "Product Line",
        "Lot Number",
        "Lot Expiration",
        "Quantity",
        "Dollar Amount",
        "Case-Pack",
        "Customer Master Demand",
        "Manufacturer",
        "Controlled Sub.",
        "Channel Review",
        "Primary Action",
    ]
    detail = candidates[[column for column in columns if column in candidates]].sort_values(
        ["Expiry Bucket", "Dollar Amount"], ascending=[True, False]
    )
    st.dataframe(
        detail,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Lot Expiration": st.column_config.DateColumn(format="MM/DD/YYYY"),
            "Quantity": st.column_config.NumberColumn(format="%.0f"),
            "Dollar Amount": st.column_config.NumberColumn(format="$%.2f"),
        },
    )


def render_explorer(frame: pd.DataFrame, bundle) -> None:
    section_title("Lot-Level Inventory Explorer", "The table and downloads respect all global filters.")
    columns = [
        "Priority",
        "Action Owner",
        "Material Number",
        "NDC 11",
        "Item Description Final",
        "Product Line",
        "Manufacturer",
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
        "Product Status",
        "Controlled Sub.",
        "Commercial Review Eligible",
        "Primary Action",
    ]
    detail = frame[[column for column in columns if column in frame]].sort_values(
        ["Days To Exp", "Dollar Amount"], ascending=[True, False]
    )
    st.dataframe(
        detail,
        use_container_width=True,
        hide_index=True,
        height=650,
        column_config={
            "Lot Expiration": st.column_config.DateColumn(format="MM/DD/YYYY"),
            "Quantity": st.column_config.NumberColumn(format="%.0f"),
            "COGS": st.column_config.NumberColumn(format="$%.4f"),
            "Dollar Amount": st.column_config.NumberColumn(format="$%.2f"),
            "Customer Master Demand": st.column_config.NumberColumn(format="%.0f"),
            "6M Average Forecast": st.column_config.NumberColumn(format="%.1f"),
        },
    )
    st.download_button(
        "Download filtered detail (CSV)",
        data=detail.to_csv(index=False).encode("utf-8-sig"),
        file_name=f"sku_inventory_lot_detail_{bundle.as_of_date:%Y%m%d}.csv",
        mime="text/csv",
    )


def render_quality(frame: pd.DataFrame, bundle) -> None:
    quality = data_quality_checks(frame, bundle.manifest, bundle.as_of_date, bundle.as_of_confidence)
    pass_count = int(quality["Status"].eq("PASS").sum())
    review_count = len(quality) - pass_count
    metric_cards(
        [
            ("Checks Passed", f"{pass_count}/{len(quality)}", "Current data-quality result", "good"),
            ("Review / Warning", f"{review_count}", "Items needing source-owner review", "warn"),
            ("As-of Confidence", f"{bundle.as_of_confidence:.1%}", "Inferred from source expiration days", ""),
            ("Forecast Months", f"{len(bundle.forecast_months)}", "Available monthly columns", ""),
            ("Load Mode", "Snapshot" if "snapshot" in bundle.source_mode.lower() else "Excel", "Hosted app uses fast snapshot", "good"),
        ]
    )
    st.markdown(
        f'<div class="callout good"><strong>{escape(EXCLUDED_SOURCE_LABEL)}</strong> is intentionally excluded. Product status comes directly from Product Master.</div>',
        unsafe_allow_html=True,
    )
    section_title("Source Manifest", "Four centralized BOM sources are the governed inputs for this application.")
    st.dataframe(bundle.manifest, use_container_width=True, hide_index=True)
    section_title("Data Quality Checks")
    st.dataframe(quality, use_container_width=True, hide_index=True)
    for warning in bundle.warnings:
        st.warning(warning)

    with st.expander("Formula dictionary"):
        st.dataframe(pd.DataFrame(FORMULA_DICTIONARY), use_container_width=True, hide_index=True)
    with st.expander("Refresh workflow"):
        st.markdown(
            "1. Keep the four current Excel sources in the centralized `E:\\BOM` folder.  \n"
            "2. Run `powershell -ExecutionPolicy Bypass -File scripts\\refresh_from_bom.ps1`.  \n"
            "3. The script rebuilds `data/inventory_snapshot.csv.gz` and validates all metrics.  \n"
            "4. Commit only the refreshed snapshot and metadata, then push to the private GitHub repository.  \n"
            "5. Streamlit redeploys automatically and reads the compressed snapshot directly."
        )


def render_excel_export(frame: pd.DataFrame, bundle) -> None:
    with st.expander("Download audit-friendly Excel package"):
        st.caption(
            "Creates Summary, Lot Detail, SKU Summary, Action Queue, Data Quality, Source Manifest and Formula Dictionary tabs."
        )
        if st.button("Prepare current-view Excel package", type="primary"):
            with st.spinner("Preparing Excel package…"):
                st.session_state["excel_export"] = build_excel_export(
                    frame,
                    sku_summary(frame),
                    action_queue(frame),
                    data_quality_checks(frame, bundle.manifest, bundle.as_of_date, bundle.as_of_confidence),
                    bundle.manifest,
                    calculate_kpis(frame),
                    bundle.as_of_date,
                )
        if "excel_export" in st.session_state:
            st.download_button(
                "Download Excel package",
                data=st.session_state["excel_export"],
                file_name=f"SKU_Inventory_Monitor_{bundle.as_of_date:%Y%m%d}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )


def main() -> None:
    if not DATA_DIR.exists():
        st.error(f"Data folder not found: {DATA_DIR}")
        st.stop()
    try:
        signature = source_signature(DATA_DIR)
        with st.spinner("Loading governed inventory snapshot…"):
            bundle = cached_bundle(str(DATA_DIR), signature)
    except Exception as exc:
        st.error("The inventory data could not be loaded.")
        st.code(str(exc))
        st.markdown(
            "Run `scripts/refresh_from_bom.ps1` to create the deploy snapshot from the four BOM sources: "
            "Current Inventory, Product COGS, Product Master and SCM Actual vs. Forecast."
        )
        st.stop()

    page = render_sidebar(bundle)
    render_header(page, bundle)
    filtered = render_filter_bar(bundle.inventory)
    if filtered.empty and page != "Data Quality & Refresh":
        st.warning("No rows match the current filters.")
        st.stop()

    if page == "Enterprise Overview":
        render_overview(filtered, bundle)
    elif page == "CFO / Finance":
        render_finance(filtered)
    elif page == "SCM Planning":
        render_scm(filtered)
    elif page == "Operations":
        render_operations(filtered)
    elif page == "Sales / Customer Service":
        render_sales(filtered)
    elif page == "Lot Explorer":
        render_explorer(filtered, bundle)
    else:
        render_quality(bundle.inventory, bundle)

    render_excel_export(filtered if not filtered.empty else bundle.inventory, bundle)


if __name__ == "__main__":
    main()
