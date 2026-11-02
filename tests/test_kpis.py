"""KPI, period-comparison and API tests using a tiny dataset whose answers were
calculated by hand (see the comments next to each order).

Run with:  python -m unittest discover -s tests -v
"""
import os
import sys
import tempfile
import unittest
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import analytics  # noqa: E402
from app import create_app  # noqa: E402

PRODUCTS = [(1, "Phone", "Electronics"), (2, "Shirt", "Fashion")]
ORDERS = [
    (1, "2026-01-03", "Delivered", "North"),   # before the previous window -> must be ignored there
    (2, "2026-01-10", "Delivered", "North"),
    (3, "2026-01-20", "Cancelled", "South"),   # cancelled -> excluded from every revenue KPI
    (4, "2026-02-05", "Delivered", "North"),
    (5, "2026-02-10", "Delivered", "South"),
    (6, "2026-02-15", "Cancelled", "South"),
    (7, "2026-02-20", "Shipped", "North"),
]
# (order, product, qty, unit_price, discount, return_amount)
ITEMS = [
    (1, 1, 1, 1000, 0, 0),
    (2, 1, 2, 1000, 100, 0),      # gross 2000, net 1900
    (3, 2, 5, 200, 0, 0),
    (4, 1, 1, 1000, 50, 0),       # gross 1000, net 950
    (4, 2, 2, 200, 0, 200),       # gross 400,  net 200
    (5, 2, 3, 200, 0, 0),         # gross 600,  net 600
    (6, 1, 1, 1000, 0, 0),
    (7, 1, 1, 1000, 100, 0),      # gross 1000, net 900
]
# February (1-28): orders 4,5,7 -> gross 3000, discounts 150, returns 200, net 2650, AOV 883.33
# Previous window (Jan 4-31):    order 2 only -> gross 2000, discounts 100, net 1900


class AnalyticsAndApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.app = create_app({"DB_ENGINE": "sqlite", "SQLITE_PATH": os.path.join(cls.tmp.name, "t.db"),
                              "AUTO_SEED": False, "TESTING": True})
        db = cls.app.extensions["db"]
        db.execute_many("INSERT INTO products VALUES (%s, %s, %s)", PRODUCTS)
        db.execute_many("INSERT INTO orders VALUES (%s, %s, %s, %s)", ORDERS)
        db.execute_many("INSERT INTO order_items (order_id, product_id, quantity, unit_price, discount, return_amount) "
                        "VALUES (%s, %s, %s, %s, %s, %s)", ITEMS)
        cls.db = db
        cls.client = cls.app.test_client()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def feb(self, **kw):
        return analytics.DashboardData(self.db, date(2026, 2, 1), date(2026, 2, 28), **kw)

    # ---- KPI formulas
    def test_core_kpis_exclude_cancelled(self):
        k = self.feb().kpis()["current"]
        self.assertEqual(k["gross_sales"], 3000.0)
        self.assertEqual(k["discounts"], 150.0)
        self.assertEqual(k["returns"], 200.0)
        self.assertEqual(k["net_sales"], 2650.0)
        self.assertEqual(k["orders"], 3)
        self.assertEqual(k["aov"], 883.33)
        self.assertEqual(k["units_sold"], 7)

    def test_rates(self):
        k = self.feb().kpis()["current"]
        self.assertEqual(k["cancelled_orders"], 1)
        self.assertEqual(k["cancellation_rate"], 25.0)   # 1 of 4 orders placed
        self.assertEqual(k["return_rate"], 6.67)         # 200 / 3000
        self.assertEqual(k["discount_rate"], 5.0)        # 150 / 3000

    def test_previous_period_window_and_growth(self):
        d = self.feb()
        self.assertEqual(d.prev_start, date(2026, 1, 4))
        self.assertEqual(d.prev_end, date(2026, 1, 31))
        k = d.kpis()
        self.assertEqual(k["previous"]["net_sales"], 1900.0)   # Jan 3 order correctly left out
        self.assertEqual(k["previous"]["orders"], 1)
        self.assertEqual(k["growth_pct"]["net_sales"], 39.47)
        self.assertEqual(k["growth_pct"]["gross_sales"], 50.0)
        self.assertEqual(k["growth_pct"]["orders"], 200.0)
        self.assertEqual(k["growth_pct"]["aov"], -53.51)

    def test_growth_is_none_when_previous_is_zero(self):
        d = analytics.DashboardData(self.db, date(2025, 1, 1), date(2025, 1, 31))
        k = d.kpis()
        self.assertEqual(k["current"]["orders"], 0)
        self.assertEqual(k["current"]["aov"], 0.0)
        self.assertIsNone(k["growth_pct"]["net_sales"])

    # ---- breakdowns reconcile with totals
    def test_category_and_region_reconcile(self):
        d = self.feb()
        cat = d.by_category().set_index("category")
        self.assertEqual(cat.loc["Electronics", "net_sales"], 1850.0)
        self.assertEqual(cat.loc["Fashion", "net_sales"], 800.0)
        self.assertAlmostEqual(cat["net_sales"].sum(), d.kpis()["current"]["net_sales"])
        reg = d.by_region().set_index("region")
        self.assertEqual(reg.loc["North", "net_sales"], 2050.0)
        self.assertEqual(reg.loc["South", "net_sales"], 600.0)
        self.assertAlmostEqual(reg["net_sales"].sum(), d.kpis()["current"]["net_sales"])
        self.assertAlmostEqual(cat["share_pct"].sum(), 100.0, places=1)

    def test_filters(self):
        south = self.feb(region="South").kpis()["current"]
        self.assertEqual((south["net_sales"], south["orders"]), (600.0, 1))
        fashion = self.feb(category="Fashion").kpis()["current"]
        self.assertEqual((fashion["net_sales"], fashion["orders"]), (800.0, 2))

    def test_monthly_trend_and_mom(self):
        d = analytics.DashboardData(self.db, date(2026, 1, 1), date(2026, 2, 28))
        m = d.monthly().set_index("month")
        self.assertEqual(m.loc["2026-01", "net_sales"], 2900.0)
        self.assertEqual(m.loc["2026-02", "net_sales"], 2650.0)
        self.assertEqual(m.loc["2026-02", "mom_growth_pct"], -8.62)

    # ---- API behaviour
    def test_api_kpis_ok(self):
        r = self.client.get("/api/kpis?start=2026-02-01&end=2026-02-28")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["current"]["net_sales"], 2650.0)

    def test_api_validation_errors(self):
        for qs in ("start=bad", "start=2026-03-01&end=2026-02-01", "region=Mars", "category=Nope"):
            r = self.client.get(f"/api/kpis?{qs}")
            self.assertEqual(r.status_code, 400, qs)
            self.assertIn("error", r.get_json())

    def test_other_endpoints(self):
        for url in ("/api/filters", "/api/revenue/monthly", "/api/revenue/category",
                    "/api/revenue/region", "/api/products/top", "/api/kpi-definitions",
                    "/api/health", "/", "/kpi-definitions"):
            self.assertEqual(self.client.get(url).status_code, 200, url)
        csv = self.client.get("/api/report.csv?start=2026-02-01&end=2026-02-28")
        self.assertEqual(csv.status_code, 200)
        self.assertIn("Net Sales", csv.get_data(as_text=True))

    def test_every_chart_renders_png(self):
        from charts import CHARTS
        for name in CHARTS:
            r = self.client.get(f"/charts/{name}.png?start=2026-01-01&end=2026-02-28")
            self.assertEqual(r.status_code, 200, name)
            self.assertTrue(r.data.startswith(b"\x89PNG"), name)
        # empty selection still renders ("No data" chart) instead of crashing
        r = self.client.get("/charts/category_comparison.png?start=2020-01-01&end=2020-01-31")
        self.assertEqual(r.status_code, 200)

    def test_unknown_chart_404(self):
        self.assertEqual(self.client.get("/charts/nope.png").status_code, 404)

    # ---- database constraints
    def test_database_rejects_invalid_rows(self):
        import sqlite3
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute_many("INSERT INTO order_items (order_id, product_id, quantity, unit_price, discount, return_amount) "
                                 "VALUES (%s, %s, %s, %s, %s, %s)", [(2, 1, 0, 100, 0, 0)])   # quantity 0
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute_many("INSERT INTO order_items (order_id, product_id, quantity, unit_price, discount, return_amount) "
                                 "VALUES (%s, %s, %s, %s, %s, %s)", [(2, 1, 1, 100, 80, 80)])  # discount+return > gross
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute_many("INSERT INTO orders VALUES (%s, %s, %s, %s)", [(99, "2026-01-01", "Lost", "North")])
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute_many("INSERT INTO order_items (order_id, product_id, quantity, unit_price, discount, return_amount) "
                                 "VALUES (%s, %s, %s, %s, %s, %s)", [(12345, 1, 1, 100, 0, 0)])  # FK violation


if __name__ == "__main__":
    unittest.main()
