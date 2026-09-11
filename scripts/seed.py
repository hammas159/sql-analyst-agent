"""Generate the demo dataset.

Deterministic and offline: a fixed seed, no Faker, no download. A reviewer gets
byte-identical data to the one the README's numbers were measured on, and the repo
works on a machine with no internet.

The data is shaped to make text-to-SQL interesting rather than uniform: sales are
seasonal, one region underperforms, a handful of orders are delivered-but-refunded,
and some customers have no region at all.
"""

from __future__ import annotations

import datetime as dt
import random
import sys
from pathlib import Path

import psycopg

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from sqlanalyst.config import get_settings  # noqa: E402

RNG = random.Random(20260911)

REGIONS = [
    ("Punjab", "Pakistan"), ("Sindh", "Pakistan"), ("KPK", "Pakistan"),
    ("Balochistan", "Pakistan"), ("Online", "Pakistan"),
]
CATEGORIES = [
    ("Electronics", None), ("Phones", "Electronics"), ("Laptops", "Electronics"),
    ("Home", None), ("Kitchen", "Home"), ("Furniture", "Home"),
    ("Apparel", None), ("Footwear", "Apparel"),
]
FIRST = "Ali Fatima Hassan Ayesha Bilal Zainab Omar Hira Usman Sana Tariq Nadia Imran Mariam Kashif".split()
LAST = "Khan Ahmed Sheikh Malik Butt Qureshi Siddiqui Chaudhry Baig Abbasi".split()
PRODUCTS = [
    ("Galaxy A54", "Phones", 210, 299), ("Pixel 8a", "Phones", 320, 449),
    ("iPhone SE", "Phones", 340, 479), ("ThinkPad E14", "Laptops", 540, 749),
    ("MacBook Air M2", "Laptops", 820, 1099), ("Aspire 5", "Laptops", 380, 529),
    ("Air Fryer 5L", "Kitchen", 55, 89), ("Blender Pro", "Kitchen", 32, 59),
    ("Rice Cooker", "Kitchen", 28, 45), ("Office Chair", "Furniture", 90, 159),
    ("Standing Desk", "Furniture", 180, 299), ("Bookshelf", "Furniture", 60, 99),
    ("Running Shoes", "Footwear", 38, 79), ("Leather Boots", "Footwear", 62, 129),
    ("Sandals", "Footwear", 15, 29),
]


def _name() -> str:
    return f"{RNG.choice(FIRST)} {RNG.choice(LAST)}"


def seed(conn: psycopg.Connection) -> None:
    cur = conn.cursor()

    cur.execute("TRUNCATE order_items, orders, customers, products, categories, "
                "employees, stores, regions RESTART IDENTITY CASCADE")

    cur.executemany("INSERT INTO regions(name, country) VALUES (%s, %s)", REGIONS)

    for name, parent in CATEGORIES:
        if parent is None:
            cur.execute("INSERT INTO categories(name) VALUES (%s)", (name,))
        else:
            cur.execute(
                "INSERT INTO categories(name, parent_id) VALUES "
                "(%s, (SELECT category_id FROM categories WHERE name = %s))",
                (name, parent),
            )

    for name, cat, cost, price in PRODUCTS:
        cur.execute(
            "INSERT INTO products(name, category_id, unit_cost, list_price, discontinued) "
            "VALUES (%s, (SELECT category_id FROM categories WHERE name = %s), %s, %s, %s)",
            (name, cat, cost, price, RNG.random() < 0.08),
        )

    # Four physical stores; region 5 ("Online") deliberately has none.
    for i, region in enumerate([1, 1, 2, 3], start=1):
        cur.execute(
            "INSERT INTO stores(name, region_id, opened_on) VALUES (%s, %s, %s)",
            (f"Store {i}", region, dt.date(2019 + i % 3, 1 + (i * 3) % 12, 10)),
        )

    # One manager per store, then staff reporting to them - a hierarchy that needs a
    # recursive CTE to walk.
    managers = []
    for store in range(1, 5):
        cur.execute(
            "INSERT INTO employees(name, store_id, hired_on, salary) "
            "VALUES (%s, %s, %s, %s) RETURNING employee_id",
            (_name(), store, dt.date(2020, 3, 1), RNG.randrange(180, 260) * 1000),
        )
        managers.append(cur.fetchone()[0])
    for store in range(1, 5):
        for _ in range(RNG.randrange(3, 6)):
            cur.execute(
                "INSERT INTO employees(name, store_id, manager_id, hired_on, salary) "
                "VALUES (%s, %s, %s, %s, %s)",
                (_name(), store, managers[store - 1],
                 dt.date(RNG.randrange(2021, 2026), RNG.randrange(1, 13), RNG.randrange(1, 28)),
                 RNG.randrange(60, 140) * 1000),
            )

    for _ in range(400):
        # ~15% of customers are online-only and have no region: the nullable FK is
        # there so a question about "sales by region" has to decide what to do.
        region = None if RNG.random() < 0.15 else RNG.randrange(1, 5)
        cur.execute(
            "INSERT INTO customers(name, region_id, signed_up_on, segment) VALUES (%s,%s,%s,%s)",
            (_name(), region,
             dt.date(RNG.randrange(2021, 2026), RNG.randrange(1, 13), RNG.randrange(1, 28)),
             RNG.choices(["retail", "business", "wholesale"], weights=[70, 22, 8])[0]),
        )

    start = dt.datetime(2024, 1, 1, tzinfo=dt.UTC)
    for _ in range(3000):
        day = RNG.randrange(0, 620)
        when = start + dt.timedelta(days=day, hours=RNG.randrange(8, 21))
        # Seasonality: a December lift, so a time-series question has something to find.
        if when.month == 12 and RNG.random() < 0.5:
            when += dt.timedelta(days=0)
        elif RNG.random() < 0.25:
            continue

        store = RNG.randrange(1, 5)
        status = RNG.choices(
            ["delivered", "shipped", "placed", "cancelled"], weights=[68, 14, 12, 6]
        )[0]
        # Delivered-but-refunded exists on purpose: it is the case that breaks a
        # revenue query which filters on the wrong status column.
        payment = "refunded" if RNG.random() < 0.05 else (
            "pending" if status == "placed" else "paid"
        )

        cur.execute(
            "INSERT INTO orders(customer_id, store_id, employee_id, ordered_at, status, "
            "payment_status) VALUES (%s,%s,%s,%s,%s,%s) RETURNING order_id",
            (RNG.randrange(1, 401), store, RNG.randrange(1, 21), when, status, payment),
        )
        order_id = cur.fetchone()[0]

        for product_id in RNG.sample(range(1, len(PRODUCTS) + 1), RNG.randrange(1, 4)):
            list_price = PRODUCTS[product_id - 1][3]
            # Negotiated price differs from list price, so revenue must come from
            # order_items.unit_price - the mistake the column comment warns about.
            unit_price = round(list_price * RNG.uniform(0.85, 1.02), 2)
            cur.execute(
                "INSERT INTO order_items(order_id, product_id, quantity, unit_price, discount) "
                "VALUES (%s,%s,%s,%s,%s)",
                (order_id, product_id, RNG.randrange(1, 5), unit_price,
                 round(RNG.choice([0, 0, 0, 0.05, 0.1, 0.15]), 3)),
            )

    conn.commit()
    cur.execute("ANALYZE")   # row estimates feed the schema prompt
    conn.commit()

    for table in ("regions", "stores", "employees", "categories", "products",
                  "customers", "orders", "order_items"):
        n = cur.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        print(f"  {table:<12} {n:>6,}")


if __name__ == "__main__":
    with psycopg.connect(get_settings().admin_dsn) as conn:
        seed(conn)
    print("\nseeded")
