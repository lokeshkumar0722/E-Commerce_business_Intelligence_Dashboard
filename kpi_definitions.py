"""Single source of truth for KPI formulas and treatment rules.

Rendered on the /kpi-definitions page, exported by ``manage.py export-report``
and mirrored in the README, so documentation can never drift from the code.
"""

KPI_DEFINITIONS = [
    {
        "name": "Gross Sales",
        "key": "gross_sales",
        "formula": "Σ (quantity × unit_price)",
        "notes": "Counted orders only. Before discounts and returns.",
    },
    {
        "name": "Discounts",
        "key": "discounts",
        "formula": "Σ discount",
        "notes": "Absolute amount per order line, in currency units (not a percentage).",
    },
    {
        "name": "Returns",
        "key": "returns",
        "formula": "Σ return_amount",
        "notes": "Value refunded for returned goods, attributed to the original order date.",
    },
    {
        "name": "Net Sales",
        "key": "net_sales",
        "formula": "Gross Sales − Discounts − Returns",
        "notes": "The headline revenue figure used for all trends and comparisons.",
    },
    {
        "name": "Orders",
        "key": "orders",
        "formula": "COUNT(DISTINCT order_id)",
        "notes": "Counted orders only. With a category filter: orders containing at least one item of that category.",
    },
    {
        "name": "Average Order Value (AOV)",
        "key": "aov",
        "formula": "Net Sales ÷ Orders",
        "notes": "0 when there are no orders. With a category filter it is net sales of that category per order containing it.",
    },
    {
        "name": "Units Sold",
        "key": "units_sold",
        "formula": "Σ quantity",
        "notes": "Counted orders only. Returned units are not deducted (only the returned value is).",
    },
    {
        "name": "Discount Rate",
        "key": "discount_rate",
        "formula": "Discounts ÷ Gross Sales × 100",
        "notes": "Percentage of gross sales given away as discounts.",
    },
    {
        "name": "Return Rate",
        "key": "return_rate",
        "formula": "Returns ÷ Gross Sales × 100",
        "notes": "Percentage of gross sales refunded.",
    },
    {
        "name": "Cancellation Rate",
        "key": "cancellation_rate",
        "formula": "Cancelled orders ÷ All orders placed × 100",
        "notes": "Reported separately because cancelled orders are excluded from every other KPI.",
    },
    {
        "name": "Growth vs previous period",
        "key": "growth",
        "formula": "(Current − Previous) ÷ |Previous| × 100",
        "notes": "The previous period is the window of equal length ending the day before the selected start date. Shown as n/a when the previous value is 0.",
    },
    {
        "name": "Month-over-month growth",
        "key": "mom",
        "formula": "(Net Sales this month − Net Sales last month) ÷ Net Sales last month × 100",
        "notes": "First month in the range has no value. Months at the edges of a custom range may be partial.",
    },
]

TREATMENT_RULES = [
    "Cancelled orders are excluded from gross sales, discounts, returns, net sales, orders, AOV and units sold.",
    "Orders with status Delivered, Shipped or Processing are all counted (revenue is recognised when the order is placed).",
    "Discounts and returns are subtracted on the same order line they belong to, so category and product views reconcile exactly with totals.",
    "Order status is a property of the order; every line of a cancelled order is excluded together.",
    "Region is an order attribute; category is a product attribute.",
    "No customer-level analysis or segmentation is performed (aggregated business performance only).",
]
