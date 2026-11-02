"""Matplotlib charts rendered to PNG bytes (served by Flask or saved by the CLI).

Uses the object-oriented ``Figure`` API (not ``pyplot``) so rendering is
thread-safe inside the Flask server.
"""
from __future__ import annotations

import io

import numpy as np
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from matplotlib.ticker import FuncFormatter

INDIGO, SLATE, GREEN, RED, AMBER, TEAL = "#4f46e5", "#94a3b8", "#16a34a", "#dc2626", "#d97706", "#0d9488"
STATUS_COLORS = {"Delivered": GREEN, "Shipped": INDIGO, "Processing": AMBER, "Cancelled": RED}


def _compact(symbol: str):
    def fmt(x, _pos=None):
        sign = "-" if x < 0 else ""
        x = abs(x)
        for div, suffix in ((1e9, "B"), (1e6, "M"), (1e3, "K")):
            if x >= div:
                value = f"{x / div:.1f}".rstrip("0").rstrip(".")
                return f"{sign}{symbol}{value}{suffix}"
        return f"{sign}{symbol}{x:,.0f}"
    return FuncFormatter(fmt)


def _figure(w=9.0, h=4.6):
    fig = Figure(figsize=(w, h), dpi=110, layout="constrained", facecolor="white")
    ax = fig.subplots()
    ax.spines[["top", "right"]].set_visible(False)
    ax.set_axisbelow(True)
    return fig, ax


def _empty(fig, ax, title):
    ax.set_title(title, fontsize=13, fontweight="bold", loc="left")
    ax.text(0.5, 0.5, "No data for the selected filters", ha="center", va="center",
            transform=ax.transAxes, color="#64748b", fontsize=12)
    ax.set_xticks([]); ax.set_yticks([])
    return fig


def _month_labels(months):
    out = []
    for m in months:
        y, mo = m.split("-")
        out.append(["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][int(mo) - 1] + f" {y[2:]}")
    return out


def _period_label(start, end):
    return f"{start:%d %b %Y} – {end:%d %b %Y}"


# --------------------------------------------------------------------------- charts
def monthly_revenue(data, cur):
    title = "Monthly Gross vs Net Sales"
    fig, ax = _figure(14.0, 4.6)   # full-width card on the dashboard
    m = data.monthly()
    if m.empty:
        return _empty(fig, ax, title)
    x = np.arange(len(m))
    ax.bar(x, m["net_sales"], color=INDIGO, width=0.6, label="Net sales", zorder=2)
    ax.plot(x, m["gross_sales"], color=AMBER, marker="o", linewidth=2, label="Gross sales", zorder=3)
    ax.set_xticks(x, _month_labels(m["month"]), rotation=45 if len(m) > 8 else 0, ha="right" if len(m) > 8 else "center")
    ax.yaxis.set_major_formatter(_compact(cur))
    ax.grid(axis="y", color="#e2e8f0")
    ax.set_title(title, fontsize=13, fontweight="bold", loc="left")
    ax.set_xlabel("Month"); ax.set_ylabel(f"Sales ({cur})")
    ax.legend(frameon=False, loc="upper left")
    return fig


def mom_growth(data, cur):
    title = "Month-over-Month Net Sales Growth"
    fig, ax = _figure()
    m = data.monthly()
    if len(m) < 2:
        return _empty(fig, ax, title)
    vals = m["mom_growth_pct"].astype(float).fillna(0.0).to_numpy()
    x = np.arange(len(m))
    ax.bar(x, vals, color=[GREEN if v >= 0 else RED for v in vals], width=0.6, zorder=2)
    ax.axhline(0, color="#475569", linewidth=1)
    ax.set_xticks(x, _month_labels(m["month"]), rotation=45 if len(m) > 8 else 0, ha="right" if len(m) > 8 else "center")
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.0f}%"))
    ax.grid(axis="y", color="#e2e8f0")
    ax.set_title(title, fontsize=13, fontweight="bold", loc="left")
    ax.set_xlabel("Month"); ax.set_ylabel("Change vs previous month (%)")
    return fig


def sales_bridge(data, cur):
    title = "Sales Bridge: Gross to Net"
    fig, ax = _figure()
    k = data.kpis()["current"]
    if k["gross_sales"] == 0:
        return _empty(fig, ax, title)
    labels = ["Gross sales", "Discounts", "Returns", "Net sales"]
    gross, disc, ret, net = k["gross_sales"], k["discounts"], k["returns"], k["net_sales"]
    bottoms = [0, gross - disc, gross - disc - ret, 0]
    heights = [gross, disc, ret, net]
    colors = [INDIGO, RED, RED, GREEN]
    ax.bar(labels, heights, bottom=bottoms, color=colors, width=0.55, zorder=2)
    for i, (b, h) in enumerate(zip(bottoms, heights)):
        txt = ("-" if i in (1, 2) else "") + _compact(cur)(h)
        ax.text(i, b + h, txt, ha="center", va="bottom", fontsize=10, fontweight="bold")
    ax.yaxis.set_major_formatter(_compact(cur))
    ax.grid(axis="y", color="#e2e8f0")
    ax.set_ylim(0, gross * 1.12)
    ax.set_title(title, fontsize=13, fontweight="bold", loc="left")
    ax.set_ylabel(f"Amount ({cur})")
    return fig


def _grouped(data, cur, df, label_col, title, xlabel, horizontal):
    fig, ax = _figure(9.0, 4.6 if not horizontal else max(4.0, 0.6 * max(len(df), 1) + 1.8))
    if df.empty:
        return _empty(fig, ax, title)
    labels = df[label_col].tolist()
    idx = np.arange(len(labels))
    w = 0.38
    cur_lbl = "Current: " + _period_label(data.start, data.end)
    prev_lbl = "Previous: " + _period_label(data.prev_start, data.prev_end)
    if horizontal:
        ax.barh(idx - w / 2, df["net_sales"], w, color=INDIGO, label=cur_lbl, zorder=2)
        ax.barh(idx + w / 2, df["previous_net_sales"], w, color=SLATE, label=prev_lbl, zorder=2)
        ax.set_yticks(idx, labels); ax.invert_yaxis()
        ax.xaxis.set_major_formatter(_compact(cur)); ax.grid(axis="x", color="#e2e8f0")
        ax.set_xlabel(f"Net sales ({cur})"); ax.set_ylabel(xlabel)
    else:
        ax.bar(idx - w / 2, df["net_sales"], w, color=INDIGO, label=cur_lbl, zorder=2)
        ax.bar(idx + w / 2, df["previous_net_sales"], w, color=SLATE, label=prev_lbl, zorder=2)
        ax.set_xticks(idx, labels)
        ax.yaxis.set_major_formatter(_compact(cur)); ax.grid(axis="y", color="#e2e8f0")
        ax.set_ylabel(f"Net sales ({cur})"); ax.set_xlabel(xlabel)
    ax.set_title(title, fontsize=13, fontweight="bold", loc="left")
    ax.legend(frameon=False, fontsize=8.5, loc="lower right" if horizontal else "upper right")
    return fig


def category_comparison(data, cur):
    return _grouped(data, cur, data.by_category(), "category",
                    "Net Sales by Category: Current vs Previous Period", "Category", True)


def region_comparison(data, cur):
    return _grouped(data, cur, data.by_region(), "region",
                    "Net Sales by Region: Current vs Previous Period", "Region", False)


def top_products(data, cur):
    title = "Top 10 Products by Net Sales"
    t = data.top_products(10)
    fig, ax = _figure(9.0, max(4.0, 0.45 * max(len(t), 1) + 1.8))
    if t.empty:
        return _empty(fig, ax, title)
    y = np.arange(len(t))
    ax.barh(y, t["net_sales"], color=TEAL, zorder=2)
    ax.set_yticks(y, t["product_name"]); ax.invert_yaxis()
    for i, v in enumerate(t["net_sales"]):
        ax.text(v, i, " " + _compact(cur)(v), va="center", fontsize=9)
    ax.xaxis.set_major_formatter(_compact(cur)); ax.grid(axis="x", color="#e2e8f0")
    ax.set_xlim(0, t["net_sales"].max() * 1.15)
    ax.set_title(title, fontsize=13, fontweight="bold", loc="left")
    ax.set_xlabel(f"Net sales ({cur})"); ax.set_ylabel("Product")
    return fig


def order_status(data, cur):
    title = "Order Status Mix (all orders placed)"
    fig, ax = _figure(7.5, 4.6)
    s = data.order_status()
    if s.empty:
        return _empty(fig, ax, title)
    colors = [STATUS_COLORS.get(x, SLATE) for x in s["order_status"]]
    wedges, *_ = ax.pie(s["orders"], colors=colors, startangle=90, counterclock=False,
                        wedgeprops=dict(width=0.38, edgecolor="white"),
                        autopct=lambda p: f"{p:.1f}%" if p >= 3 else "", pctdistance=0.81,
                        textprops=dict(color="white", fontsize=9, fontweight="bold"))
    fig.legend(wedges, [f"{n} ({c:,})" for n, c in zip(s["order_status"], s["orders"])],
               title="Status (orders)", frameon=False, loc="outside right center", fontsize=10)
    ax.set_title(title, fontsize=13, fontweight="bold", loc="left")
    return fig


CHARTS = {
    "monthly_revenue": monthly_revenue,
    "mom_growth": mom_growth,
    "sales_bridge": sales_bridge,
    "category_comparison": category_comparison,
    "region_comparison": region_comparison,
    "top_products": top_products,
    "order_status": order_status,
}


def render_png(name: str, data, currency: str) -> bytes:
    fig = CHARTS[name](data, currency)
    buf = io.BytesIO()
    FigureCanvasAgg(fig)
    fig.savefig(buf, format="png")
    return buf.getvalue()
