-- E-Commerce BI Dashboard : MySQL 8.0.16+ schema
-- (the app runs this automatically on start-up; every statement is idempotent)

CREATE TABLE IF NOT EXISTS products (
    product_id    INT AUTO_INCREMENT PRIMARY KEY,
    product_name  VARCHAR(120) NOT NULL,
    category      VARCHAR(60)  NOT NULL,
    CONSTRAINT uq_products_name UNIQUE (product_name),
    INDEX idx_products_category (category)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS orders (
    order_id      INT AUTO_INCREMENT PRIMARY KEY,
    order_date    DATE        NOT NULL,
    order_status  VARCHAR(20) NOT NULL,
    region        VARCHAR(40) NOT NULL,
    CONSTRAINT chk_orders_status CHECK (order_status IN ('Delivered', 'Shipped', 'Processing', 'Cancelled')),
    INDEX idx_orders_date (order_date),
    INDEX idx_orders_region (region)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS order_items (
    item_id        INT AUTO_INCREMENT PRIMARY KEY,
    order_id       INT           NOT NULL,
    product_id     INT           NOT NULL,
    quantity       INT           NOT NULL,
    unit_price     DECIMAL(10,2) NOT NULL,
    discount       DECIMAL(10,2) NOT NULL DEFAULT 0,
    return_amount  DECIMAL(10,2) NOT NULL DEFAULT 0,
    CONSTRAINT fk_items_order   FOREIGN KEY (order_id)   REFERENCES orders(order_id) ON DELETE CASCADE,
    CONSTRAINT fk_items_product FOREIGN KEY (product_id) REFERENCES products(product_id),
    CONSTRAINT chk_items_qty      CHECK (quantity > 0),
    CONSTRAINT chk_items_price    CHECK (unit_price >= 0),
    CONSTRAINT chk_items_discount CHECK (discount >= 0),
    CONSTRAINT chk_items_return   CHECK (return_amount >= 0),
    CONSTRAINT chk_items_total    CHECK (discount + return_amount <= quantity * unit_price),
    INDEX idx_items_order (order_id),
    INDEX idx_items_product (product_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
