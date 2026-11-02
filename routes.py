"""Web pages, REST API and chart endpoints."""
from __future__ import annotations

import csv
import io
import threading
import time
from datetime import date

from flask import Blueprint, Response, current_app, jsonify, render_template, request

import analytics
from charts import CHARTS, render_png
from kpi_definitions import KPI_DEFINITIONS, TREATMENT_RULES

bp = Blueprint("main", __name__)


class ApiError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status, self.message = status, message


def _db():
    return current_app.extensions["db"]


def _lists():
    db = _db()
    regions = db.query_df("SELECT DISTINCT region FROM orders ORDER BY region")["region"].tolist()
    categories = db.query_df("SELECT DISTINCT category FROM products ORDER BY category")["category"].tolist()
    lo = db.scalar("SELECT MIN(order_date) FROM orders")
    hi = db.scalar("SELECT MAX(order_date) FROM orders")
    return regions, categories, lo, hi


def _as_date(value, label: str) -> date:
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        raise ApiError(400, f"'{label}' must be a valid date in YYYY-MM-DD format.")


def parse_filters() -> dict:
    """Validate query-string filters; defaults to the full data range."""
    regions, categories, lo, hi = _lists()
    if lo is None:
        raise ApiError(404, "The database has no orders yet. Run 'python manage.py seed' first.")
    start = _as_date(request.args.get("start") or lo, "start")
    end = _as_date(request.args.get("end") or hi, "end")
    if start > end:
        raise ApiError(400, "'start' must not be later than 'end'.")
    region = request.args.get("region") or None
    category = request.args.get("category") or None
    if region and region not in regions:
        raise ApiError(400, f"Unknown region '{region}'. Valid: {', '.join(regions)}.")
    if category and category not in categories:
        raise ApiError(400, f"Unknown category '{category}'. Valid: {', '.join(categories)}.")
    return dict(start=start, end=end, region=region, category=category)


# Small in-memory cache: the dashboard fires ~11 requests per view that all need the
# same data, so compute it once (important on low-CPU hosts such as Render's free plan).
_CACHE: dict = {}
_CACHE_LOCK = threading.Lock()
_BUILD_LOCK = threading.RLock()   # re-entrant: a chart build also builds its data
CACHE_TTL = 300


def _cached(key, builder):
    def lookup():
        with _CACHE_LOCK:
            hit = _CACHE.get(key)
        return hit[1] if hit and time.time() - hit[0] < CACHE_TTL else None

    value = lookup()
    if value is not None:
        return value
    with _BUILD_LOCK:                      # one expensive build at a time
        value = lookup()
        if value is None:
            value = builder()
            with _CACHE_LOCK:
                if len(_CACHE) > 80:
                    _CACHE.clear()
                _CACHE[key] = (time.time(), value)
    return value


def _data() -> analytics.DashboardData:
    f = parse_filters()
    key = ("data", id(_db()), f["start"], f["end"], f["region"], f["category"])
    return _cached(key, lambda: analytics.DashboardData(_db(), **f))


# ------------------------------------------------------------------ pages
@bp.get("/")
def dashboard():
    return render_template("index.html", currency=current_app.config["CURRENCY_SYMBOL"],
                           charts=list(CHARTS))


@bp.get("/kpi-definitions")
def kpi_definitions_page():
    return render_template("definitions.html", kpis=KPI_DEFINITIONS, rules=TREATMENT_RULES,
                           currency=current_app.config["CURRENCY_SYMBOL"])


# ------------------------------------------------------------------ REST API
@bp.get("/api/health")
def health():
    try:
        _db().scalar("SELECT 1")
        return jsonify(status="ok", database=current_app.config["DB_ENGINE"])
    except Exception as exc:  # noqa: BLE001
        return jsonify(status="error", detail=str(exc)), 503


@bp.get("/api/filters")
def filters():
    regions, categories, lo, hi = _lists()
    return jsonify(regions=regions, categories=categories, min_date=lo and str(lo)[:10],
                   max_date=hi and str(hi)[:10], currency=current_app.config["CURRENCY_SYMBOL"])


@bp.get("/api/kpis")
def kpis():
    return jsonify(_data().kpis())


@bp.get("/api/revenue/monthly")
def revenue_monthly():
    return jsonify(analytics.to_records(_data().monthly()))


@bp.get("/api/revenue/category")
def revenue_category():
    return jsonify(analytics.to_records(_data().by_category()))


@bp.get("/api/revenue/region")
def revenue_region():
    return jsonify(analytics.to_records(_data().by_region()))


@bp.get("/api/products/top")
def products_top():
    return jsonify(analytics.to_records(_data().top_products(10)))


@bp.get("/api/kpi-definitions")
def kpi_definitions_api():
    return jsonify(kpis=KPI_DEFINITIONS, treatment_rules=TREATMENT_RULES)


@bp.get("/api/report.csv")
def report_csv():
    rows = _data().report_rows()
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    return Response(buf.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=kpi_report.csv"})


# ------------------------------------------------------------------ charts
@bp.get("/charts/<name>.png")
def chart(name: str):
    if name not in CHARTS:
        raise ApiError(404, f"Unknown chart '{name}'. Available: {', '.join(CHARTS)}.")
    f = parse_filters()
    key = ("chart", name, id(_db()), f["start"], f["end"], f["region"], f["category"])
    png = _cached(key, lambda: render_png(name, _data(), current_app.config["CURRENCY_SYMBOL"]))
    return Response(png, mimetype="image/png", headers={"Cache-Control": "no-cache"})
