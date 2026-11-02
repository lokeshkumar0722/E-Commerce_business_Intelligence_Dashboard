-- E-Commerce BI Dashboard : SQLite schema (zero-setup demo mode)

CREATE TABLE IF NOT EXISTS products (
    product_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    product_name  TEXT NOT NULL UNIQUE,
    category      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS orders (
    order_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    order_date    TEXT NOT NULL CHECK (order_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
    order_status  TEXT NOT NULL CHECK (order_status IN ('Delivered', 'Shipped', 'Processing', 'Cancelled')),
    region        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS order_items (
    item_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id       INTEGER NOT NULL REFERENCES orders(order_id) ON DELETE CASCADE,
    product_id     INTEGER NOT NULL REFERENCES products(product_id),
    quantity       INTEGER NOT NULL CHECK (quantity > 0),
    unit_price     REAL    NOT NULL CHECK (unit_price >= 0),
    discount       REAL    NOT NULL DEFAULT 0 CHECK (discount >= 0),
    return_amount  REAL    NOT NULL DEFAULT 0 CHECK (return_amount >= 0),
    CHECK (discount + return_amount <= quantity * unit_price + 0.005)
);

CREATE INDEX IF NOT EXISTS idx_orders_date ON orders(order_date);
CREATE INDEX IF NOT EXISTS idx_orders_region ON orders(region);
CREATE INDEX IF NOT EXISTS idx_items_order ON order_items(order_id);
CREATE INDEX IF NOT EXISTS idx_items_product ON order_items(product_id)
