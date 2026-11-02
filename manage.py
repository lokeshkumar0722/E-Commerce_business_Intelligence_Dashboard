"""Command-line helper.

    python manage.py init-db                  create tables
    python manage.py seed [--reset] [--orders N]   load sample data
    python manage.py export-report [--out DIR]     save KPI CSV + chart PNGs
"""
import argparse
import csv
from datetime import date, timedelta
from pathlib import Path

import analytics
from charts import CHARTS, render_png
from config import Config
from db import Database
from kpi_definitions import KPI_DEFINITIONS
from seed_data import seed


def _db() -> Database:
    db = Database.from_config({k: getattr(Config, k) for k in dir(Config) if k.isupper()})
    db.init_schema()
    return db


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init-db")
    p_seed = sub.add_parser("seed")
    p_seed.add_argument("--reset", action="store_true", help="delete existing rows first")
    p_seed.add_argument("--orders", type=int, default=7000)
    p_rep = sub.add_parser("export-report")
    p_rep.add_argument("--out", default="reports")
    p_rep.add_argument("--start")
    p_rep.add_argument("--end")
    args = parser.parse_args()

    db = _db()
    if args.cmd == "init-db":
        print("Tables are ready.")
    elif args.cmd == "seed":
        if args.reset:
            db.reset_data()
        elif db.scalar("SELECT COUNT(*) FROM orders"):
            raise SystemExit("Database already has data. Use --reset to replace it.")
        print("Loaded:", seed(db, n_orders=args.orders))
    elif args.cmd == "export-report":
        lo, hi = db.scalar("SELECT MIN(order_date) FROM orders"), db.scalar("SELECT MAX(order_date) FROM orders")
        if lo is None:
            raise SystemExit("No data. Run 'python manage.py seed' first.")
        end = date.fromisoformat(args.end or str(hi)[:10])
        # default: last 12 months, so a full previous period exists for growth figures
        start = date.fromisoformat(args.start) if args.start else max(date.fromisoformat(str(lo)[:10]), end - timedelta(days=364))
        data = analytics.DashboardData(db, start, end)
        out = Path(args.out)
        (out / "charts").mkdir(parents=True, exist_ok=True)
        rows = data.report_rows()
        with open(out / "kpi_report.csv", "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
        with open(out / "kpi_definitions.csv", "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=["name", "formula", "notes"], extrasaction="ignore")
            w.writeheader()
            w.writerows(KPI_DEFINITIONS)
        for name in CHARTS:
            (out / "charts" / f"{name}.png").write_bytes(render_png(name, data, Config.CURRENCY_SYMBOL))
        print(f"Report written to {out.resolve()}")


if __name__ == "__main__":
    main()
