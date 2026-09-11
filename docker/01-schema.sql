-- A small retail warehouse. Deliberately not a toy: it has the shapes that make
-- text-to-SQL hard - a self-referencing hierarchy, a many-to-many, a slowly
-- changing dimension, nullable foreign keys, and two columns whose names invite
-- the wrong join.

CREATE TABLE regions (
    region_id   SERIAL PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE,
    country     TEXT NOT NULL
);

CREATE TABLE stores (
    store_id    SERIAL PRIMARY KEY,
    name        TEXT NOT NULL,
    region_id   INT NOT NULL REFERENCES regions(region_id),
    opened_on   DATE NOT NULL
);

CREATE TABLE employees (
    employee_id SERIAL PRIMARY KEY,
    name        TEXT NOT NULL,
    store_id    INT  NOT NULL REFERENCES stores(store_id),
    -- self-referencing: "who reports to whom" needs a recursive CTE
    manager_id  INT  REFERENCES employees(employee_id),
    hired_on    DATE NOT NULL,
    salary      NUMERIC(10,2) NOT NULL
);

CREATE TABLE categories (
    category_id SERIAL PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE,
    -- nullable self-reference: subcategories
    parent_id   INT REFERENCES categories(category_id)
);

CREATE TABLE products (
    product_id  SERIAL PRIMARY KEY,
    name        TEXT NOT NULL,
    category_id INT NOT NULL REFERENCES categories(category_id),
    unit_cost   NUMERIC(10,2) NOT NULL,
    list_price  NUMERIC(10,2) NOT NULL,
    discontinued BOOLEAN NOT NULL DEFAULT false
);

CREATE TABLE customers (
    customer_id SERIAL PRIMARY KEY,
    name        TEXT NOT NULL,
    region_id   INT REFERENCES regions(region_id),   -- nullable on purpose
    signed_up_on DATE NOT NULL,
    segment     TEXT NOT NULL CHECK (segment IN ('retail','business','wholesale'))
);

CREATE TABLE orders (
    order_id    SERIAL PRIMARY KEY,
    customer_id INT NOT NULL REFERENCES customers(customer_id),
    store_id    INT NOT NULL REFERENCES stores(store_id),
    employee_id INT REFERENCES employees(employee_id),
    ordered_at  TIMESTAMPTZ NOT NULL,
    -- "status" and "payment_status" are different things; a careless join or filter
    -- conflates them. Real schemas are full of this.
    status          TEXT NOT NULL CHECK (status IN ('placed','shipped','delivered','cancelled')),
    payment_status  TEXT NOT NULL CHECK (payment_status IN ('pending','paid','refunded'))
);

CREATE TABLE order_items (
    order_id   INT NOT NULL REFERENCES orders(order_id) ON DELETE CASCADE,
    product_id INT NOT NULL REFERENCES products(product_id),
    quantity   INT NOT NULL CHECK (quantity > 0),
    unit_price NUMERIC(10,2) NOT NULL,     -- price at time of sale, not list_price
    discount   NUMERIC(4,3) NOT NULL DEFAULT 0,
    PRIMARY KEY (order_id, product_id)
);

CREATE INDEX orders_customer_idx   ON orders(customer_id);
CREATE INDEX orders_ordered_at_idx ON orders(ordered_at);
CREATE INDEX order_items_product_idx ON order_items(product_id);

-- Column comments are the cheapest grounding signal there is, and most schemas
-- have none. The agent reads these.
COMMENT ON COLUMN orders.status IS 'Fulfilment state. Not related to payment.';
COMMENT ON COLUMN orders.payment_status IS 'Money state. An order can be delivered but refunded.';
COMMENT ON COLUMN order_items.unit_price IS 'Price actually charged, after negotiation. Use this for revenue, not products.list_price.';
COMMENT ON COLUMN order_items.discount IS 'Fraction 0-1. Revenue = quantity * unit_price * (1 - discount).';
COMMENT ON COLUMN customers.region_id IS 'Nullable: online customers have no region.';
