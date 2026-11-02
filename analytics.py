"""KPI aggregation and period comparison (Pandas + NumPy).

Every number shown on the dashboard, in the REST API and in the charts comes
from this module, so the KPI definitions in ``kpi_definitions.py`` are
implemented in exactly one place.
"""
from __future__ import annotations

import json
from datetime import date, timedelta

import numpy as np
import pandas as pd

CANCELLED = "Cancelled"

ITEM_SQL = """
SELECT o.order_id, o.order_date, o.order_status, o.region,
       p.product_id, p.product_name, p.category,
       oi.quantity, oi.unit_price, oi.discount, oi.return_amount
FROM order_items oi
JOIN orders   o ON o.order_id   = oi.order_id
JOIN products p ON p.product_id = oi.product_id
WHERE o.order_date BETWEEN %s AND %s
"""

GROWTH_KEYS = ["gross_sales", "discounts", "returns", "net_sales", "orders", "units_sold", "aov"]


# --------------------------------------------------------------------------- helpers
def pct_change(current: float, previous: float | None) -> float | None:
    """Percentage change; ``None`` when the previous value is zero/unknown."""
    if previous is None or previous == 0:
        return None
    return round(float(np.divide(current - previous, abs(previous)) * 100), 2)


def to_records(df: pd.DataFrame) -> list[dict]:
    """DataFrame -> JSON-safe list of dicts (NaN becomes null)."""
    return json.loads(df.to_json(orient="records"))


def sales_only(df: pd.DataFrame) -> pd.DataFrame:
    """Rows that count towards revenue KPIs (cancelled orders excluded)."""
    return df[df["order_status"] != CANCELLED]


def load_items(db, start: date, end: date, region: str | None = None,
               category: str | None = None) -> pd.DataFrame:
    sql, params = ITEM_SQL, [start.isoformat(), end.isoformat()]
    if region:
        sql += " AND o.region = %s"
        params.append(region)
    if category:
        sql += " AND p.category = %s"
        params.append(category)
    df = db.query_df(sql + " ORDER BY o.order_date, o.order_id", params)

    df["order_date"] = pd.to_datetime(df["order_date"])
    df["quantity"] = df["quantity"].astype(int)
    for col in ("unit_price", "discount", "return_amount"):
        df[col] = df[col].astype(float)
    df["gross"] = df["quantity"] * df["unit_price"]
    df["net"] = df["gross"] - df["discount"] - df["return_amount"]
    return df


# --------------------------------------------------------------------------- KPIs
def compute_kpis(df: pd.DataFrame) -> dict:
    sales = sales_only(df)
    gross = float(sales["gross"].sum())
    discounts = float(sales["discount"].sum())
    returns = float(sales["return_amount"].sum())
    net = gross - discounts - returns
    orders = int(sales["order_id"].nunique())
    all_orders = int(df["order_id"].nunique())
    cancelled = all_orders - orders

    def rate(part: float, whole: float) -> float:
        return round(float(np.divide(part, whole) * 100), 2) if whole else 0.0

    return {
        "gross_sales": round(gross, 2),
        "discounts": round(discounts, 2),
        "returns": round(returns, 2),
        "net_sales": round(net, 2),
        "orders": orders,
        "aov": round(net / orders, 2) if orders else 0.0,
        "units_sold": int(sales["quantity"].sum()),
        "discount_rate": rate(discounts, gross),
        "return_rate": rate(returns, gross),
        "cancelled_orders": cancelled,
        "cancellation_rate": rate(cancelled, all_orders),
    }


def _breakdown(current: pd.DataFrame, previous: pd.DataFrame, by: str) -> pd.DataFrame:
    def agg(df):
        s = sales_only(df)
        return s.groupby(by).agg(
            gross_sales=("gross", "sum"),
            net_sales=("net", "sum"),
            orders=("order_id", "nunique"),
            units_sold=("quantity", "sum"),
        )

    cur = agg(current)
    prev = agg(previous)["net_sales"].rename("previous_net_sales")
    out = cur.join(prev, how="left").fillna({"previous_net_sales": 0.0})
    total = out["net_sales"].sum()
    out["share_pct"] = np.where(total > 0, out["net_sales"] / total * 100, 0.0)
    out["growth_pct"] = np.where(
        out["previous_net_sales"] > 0,
        (out["net_sales"] - out["previous_net_sales"]) / out["previous_net_sales"].replace(0, np.nan) * 100,
        np.nan,
    )
    out = out.sort_values("net_sales", ascending=False).reset_index()
    return out.round(2)


class DashboardData:
    """Loads the selected period and the equal-length previous period once."""

    def __init__(self, db, start: date, end: date, region: str | None = None,
                 category: str | None = None):
        self.start, self.end, self.region, self.category = start, end, region, category
        length = (end - start).days + 1
        self.prev_end = start - timedelta(days=1)
        self.prev_start = self.prev_end - timedelta(days=length - 1)
        self.current = load_items(db, start, end, region, category)
        self.previous = load_items(db, self.prev_start, self.prev_end, region, category)

    # ---- KPI summary + growth
    def kpis(self) -> dict:
        cur, prev = compute_kpis(self.current), compute_kpis(self.previous)
        growth = {k: pct_change(cur[k], prev[k]) for k in GROWTH_KEYS}
        return {
            "period": {"start": self.start.isoformat(), "end": self.end.isoformat()},
            "previous_period": {"start": self.prev_start.isoformat(), "end": self.prev_end.isoformat()},
            "filters": {"region": self.region, "category": self.category},
            "current": cur,
            "previous": prev,
            "growth_pct": growth,
        }

    # ---- time series
    def monthly(self) -> pd.DataFrame:
        s = sales_only(self.current)
        cols = ["month", "gross_sales", "discounts", "returns", "net_sales", "orders", "mom_growth_pct"]
        if s.empty:
            return pd.DataFrame(columns=cols)
        g = s.groupby(s["order_date"].dt.to_period("M")).agg(
            gross_sales=("gross", "sum"),
            discounts=("discount", "sum"),
            returns=("return_amount", "sum"),
            net_sales=("net", "sum"),
            orders=("order_id", "nunique"),
        )
        g = g.reindex(pd.period_range(g.index.min(), g.index.max(), freq="M"), fill_value=0)
        prev = g["net_sales"].shift(1)
        g["mom_growth_pct"] = np.where(prev > 0, (g["net_sales"] - prev) / prev.replace(0, np.nan) * 100, np.nan)
        g.index = g.index.astype(str)
        return g.rename_axis("month").reset_index().round(2)

    # ---- comparisons
    def by_category(self) -> pd.DataFrame:
        return _breakdown(self.current, self.previous, "category")

    def by_region(self) -> pd.DataFrame:
        return _breakdown(self.current, self.previous, "region")

    def top_products(self, n: int = 10) -> pd.DataFrame:
        s = sales_only(self.current)
        if s.empty:
            return pd.DataFrame(columns=["product_name", "category", "net_sales", "units_sold"])
        g = s.groupby(["product_name", "category"]).agg(
            net_sales=("net", "sum"), units_sold=("quantity", "sum")
        )
        return g.sort_values("net_sales", ascending=False).head(n).reset_index().round(2)

    def order_status(self) -> pd.DataFrame:
        if self.current.empty:
            return pd.DataFrame(columns=["order_status", "orders"])
        g = self.current.groupby("order_status")["order_id"].nunique().rename("orders")
        return g.reset_index()

    # ---- flat KPI report (CSV export)
    def report_rows(self) -> list[dict]:
        k = self.kpis()
        labels = [
            ("Gross Sales", "gross_sales"), ("Discounts", "discounts"), ("Returns", "returns"),
            ("Net Sales", "net_sales"), ("Orders", "orders"), ("Average Order Value", "aov"),
            ("Units Sold", "units_sold"), ("Discount Rate (%)", "discount_rate"),
            ("Return Rate (%)", "return_rate"), ("Cancelled Orders", "cancelled_orders"),
            ("Cancellation Rate (%)", "cancellation_rate"),
        ]
        rows = []
        for label, key in labels:
            rows.append({
                "KPI": label,
                f"Current ({k['period']['start']} to {k['period']['end']})": k["current"][key],
                f"Previous ({k['previous_period']['start']} to {k['previous_period']['end']})": k["previous"][key],
                "Change (%)": "n/a" if k["growth_pct"].get(key) is None and key in GROWTH_KEYS
                              else k["growth_pct"].get(key, "-"),
            })
        return rows
