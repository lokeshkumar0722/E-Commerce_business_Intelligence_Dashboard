"""Generate realistic, reproducible sample data (fictional store, no real customers)."""
from __future__ import annotations

from datetime import date, timedelta

import numpy as np

REGIONS = {"North": 0.24, "South": 0.28, "East": 0.16, "West": 0.22, "Central": 0.10}

# category -> [(product, base_price)]
CATALOGUE = {
    "Electronics": [("Wireless Earbuds", 2499), ("Smartphone 5G", 18999), ("Smart Watch", 5999),
                    ("Bluetooth Speaker", 3299), ("Power Bank 20000mAh", 1799), ("Laptop 14\"", 46999),
                    ("Gaming Mouse", 1499)],
    "Fashion": [("Cotton T-Shirt", 799), ("Slim Fit Jeans", 1999), ("Running Shoes", 3499),
                ("Leather Wallet", 1199), ("Summer Dress", 1799), ("Hooded Jacket", 2899),
                ("Sunglasses", 1599)],
    "Home & Kitchen": [("Air Fryer", 5499), ("Non-stick Cookware Set", 2799), ("Mixer Grinder", 3299),
                       ("Bedsheet Set", 1399), ("Table Lamp", 999), ("Vacuum Flask", 699),
                       ("Storage Organiser", 899)],
    "Beauty & Health": [("Face Serum", 899), ("Herbal Shampoo", 449), ("Electric Trimmer", 1699),
                        ("Protein Powder 1kg", 2499), ("Yoga Mat", 899), ("Sunscreen SPF50", 549)],
    "Books & Stationery": [("Bestseller Novel", 399), ("Notebook Pack (5)", 349), ("Fountain Pen", 799),
                           ("Study Planner", 499), ("Art Supplies Kit", 1299)],
    "Toys & Games": [("Building Blocks Set", 1599), ("Board Game", 1199), ("Remote Control Car", 2199),
                     ("Puzzle 1000pc", 799), ("Plush Toy", 599)],
}
CATEGORY_WEIGHTS = {"Electronics": 0.24, "Fashion": 0.26, "Home & Kitchen": 0.20,
                    "Beauty & Health": 0.13, "Books & Stationery": 0.08, "Toys & Games": 0.09}

DEFAULT_START = date(2024, 11, 1)
DEFAULT_END = date(2026, 10, 31)


def seed(db, n_orders: int = 7000, rng_seed: int = 42,
         start: date = DEFAULT_START, end: date = DEFAULT_END) -> dict:
    """Insert products, orders and order lines. Returns row counts."""
    rng = np.random.default_rng(rng_seed)

    # --- products
    products = []  # (id, name, category, price)
    pid = 1
    for category, items in CATALOGUE.items():
        for name, price in items:
            products.append((pid, name, category, float(price)))
            pid += 1
    db.execute_many("INSERT INTO products (product_id, product_name, category) VALUES (%s, %s, %s)",
                    [(p[0], p[1], p[2]) for p in products])
    by_category = {c: [p for p in products if p[2] == c] for c in CATALOGUE}

    # --- order dates: growth trend + seasonality (festive Oct-Nov, December peak)
    days = (end - start).days + 1
    day_index = np.arange(days)
    dates = [start + timedelta(days=int(i)) for i in day_index]
    season = {1: 0.9, 2: 0.85, 3: 0.95, 4: 0.95, 5: 1.0, 6: 0.95, 7: 1.0, 8: 1.05, 9: 1.0,
              10: 1.35, 11: 1.3, 12: 1.2}
    weights = np.array([season[d.month] * (1 + 0.9 * i / days) * (1.12 if d.weekday() >= 5 else 1.0)
                        for i, d in enumerate(dates)])
    weights /= weights.sum()
    order_days = rng.choice(days, size=n_orders, p=weights)
    order_days.sort()

    regions = rng.choice(list(REGIONS), size=n_orders, p=list(REGIONS.values()))
    cats = list(CATEGORY_WEIGHTS)
    cat_p = np.array(list(CATEGORY_WEIGHTS.values()))

    # cheaper products sell more often (weight ~ price^-0.9), like a real catalogue
    price_weights = {}
    for c, pool in by_category.items():
        w = np.array([p[3] ** -0.9 for p in pool])
        price_weights[c] = w / w.sum()

    orders, items = [], []
    for oid, (di, region) in enumerate(zip(order_days, regions), start=1):
        d = dates[int(di)]
        age = (end - d).days
        if age <= 10:
            status = rng.choice(["Processing", "Shipped", "Delivered", "Cancelled"], p=[0.40, 0.35, 0.15, 0.10])
        else:
            status = rng.choice(["Delivered", "Cancelled"], p=[0.92, 0.08])
        orders.append((oid, d.isoformat(), str(status), str(region)))

        n_lines = int(rng.choice([1, 2, 3, 4], p=[0.50, 0.30, 0.14, 0.06]))
        chosen = set()
        for _ in range(n_lines):
            category = cats[int(rng.choice(len(cats), p=cat_p))]
            pool = by_category[category]
            prod = pool[int(rng.choice(len(pool), p=price_weights[category]))]
            if prod[0] in chosen:
                continue
            chosen.add(prod[0])
            qty = int(rng.choice([1, 2, 3], p=[0.72, 0.21, 0.07])) if prod[3] < 5000 else 1
            unit_price = round(prod[3] * float(rng.uniform(0.95, 1.05)), 2)
            gross = round(qty * unit_price, 2)

            discount = 0.0
            if rng.random() < 0.38:
                discount = round(gross * float(rng.choice([0.05, 0.10, 0.15, 0.20, 0.25])), 2)
            returned = 0.0
            if status == "Delivered" and rng.random() < 0.065:
                share = float(rng.choice([0.5, 1.0]))
                returned = round(min((gross - discount) * share, gross - discount), 2)
            items.append((oid, prod[0], qty, unit_price, discount, returned))

    db.execute_many("INSERT INTO orders (order_id, order_date, order_status, region) VALUES (%s, %s, %s, %s)",
                    orders)
    db.execute_many("INSERT INTO order_items (order_id, product_id, quantity, unit_price, discount, return_amount) "
                    "VALUES (%s, %s, %s, %s, %s, %s)", items)
    return {"products": len(products), "orders": len(orders), "order_items": len(items)}
