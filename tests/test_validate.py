"""The validator is the layer that has to be right, so it is tested adversarially.

Everything here is a real technique for getting a write past a naive guard.
"""

import pytest

from sqlanalyst.sql.validate import validate

TABLES = {"orders", "customers", "products", "order_items", "regions", "stores"}


def ok(sql):
    return validate(sql, max_rows=100, known_tables=TABLES)


class TestRejectsWrites:
    @pytest.mark.parametrize(
        "sql",
        [
            "DELETE FROM orders",
            "UPDATE products SET list_price = 0",
            "INSERT INTO customers(name) VALUES ('x')",
            "DROP TABLE customers",
            "TRUNCATE orders",
            "ALTER TABLE orders ADD COLUMN x int",
            "CREATE TABLE evil (x int)",
            "GRANT ALL ON orders TO public",
        ],
    )
    def test_plain_write_statements(self, sql):
        assert not ok(sql).ok

    def test_stacked_statements(self):
        """The classic: a valid SELECT followed by a write."""
        r = ok("SELECT 1 FROM orders; DROP TABLE customers")
        assert not r.ok
        assert "one statement" in r.reason

    def test_write_hidden_in_a_cte(self):
        r = ok(
            "WITH gone AS (DELETE FROM orders WHERE order_id = 1 RETURNING *) SELECT * FROM gone"
        )
        assert not r.ok

    def test_comment_cannot_hide_a_write(self):
        assert not ok("SELECT 1 FROM orders /* comment */ ; DELETE FROM orders").ok

    def test_case_does_not_matter(self):
        assert not ok("dElEtE FrOm orders").ok


class TestRejectsDangerousReads:
    def test_sleep_would_burn_the_timeout(self):
        assert not ok("SELECT pg_sleep(30) FROM orders").ok

    def test_file_read(self):
        assert not ok("SELECT pg_read_file('/etc/passwd') FROM orders").ok

    def test_system_catalog(self):
        assert not ok("SELECT * FROM pg_catalog.pg_shadow").ok

    def test_information_schema(self):
        assert not ok("SELECT * FROM information_schema.tables").ok


class TestAcceptsRealQueries:
    def test_simple_select(self):
        assert ok("SELECT name FROM customers").ok

    def test_join_and_aggregate(self):
        assert ok(
            "SELECT r.name, sum(oi.quantity) FROM order_items oi "
            "JOIN orders o ON o.order_id = oi.order_id "
            "JOIN stores s ON s.store_id = o.store_id "
            "JOIN regions r ON r.region_id = s.region_id GROUP BY r.name"
        ).ok

    def test_cte_is_not_mistaken_for_an_unknown_table(self):
        r = ok("WITH totals AS (SELECT 1 AS n FROM orders) SELECT * FROM totals")
        assert r.ok, r.reason

    def test_string_literal_containing_a_keyword(self):
        """A regex guard fails this one; a parser does not."""
        assert ok("SELECT name FROM customers WHERE name = 'delete from orders'").ok


class TestLimitInjection:
    def test_limit_is_added_when_missing(self):
        assert "LIMIT 100" in ok("SELECT name FROM customers").rewritten

    def test_oversized_limit_is_clamped(self):
        assert "LIMIT 100" in ok("SELECT name FROM customers LIMIT 100000").rewritten

    def test_smaller_limit_is_respected(self):
        assert "LIMIT 5" in ok("SELECT name FROM customers LIMIT 5").rewritten


class TestUnknownTables:
    def test_hallucinated_table_is_caught_before_the_database_sees_it(self):
        r = ok("SELECT * FROM sales_summary")
        assert not r.ok
        assert "sales_summary" in r.reason
        # The reason lists real tables, which makes the repair prompt far stronger.
        assert "customers" in r.reason


class TestMalformed:
    def test_garbage(self):
        assert not ok("this is not sql at all ((").ok

    def test_empty(self):
        assert not ok("").ok
