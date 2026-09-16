"""Eight statements at the validator. Three are questions; five are attacks.

    python demo.py

This is the second of three safety layers, and the one that does not depend
on a language model behaving. The prompt is the weakest layer, so nothing
here relies on it: these statements are handed straight to the validator as
if the model had emitted them.

The third layer is the database role itself, which CI exercises on every push
by attempting real writes as the agent user.
"""

import sys

sys.path.insert(0, "src")

from sqlanalyst.sql.validate import validate

KNOWN = {"orders", "customers", "products"}

STATEMENTS = [
    ("SELECT customer_id, SUM(total) FROM orders GROUP BY 1 ORDER BY 2 DESC", "a question"),
    ("SELECT * FROM customers WHERE country = 'PK'", "a question"),
    ("WITH t AS (SELECT * FROM orders) SELECT count(*) FROM t", "a question, via CTE"),
    ("DELETE FROM orders WHERE 1=1", "destroys data"),
    ("DROP TABLE customers", "destroys a table"),
    ("UPDATE products SET price = 0", "silent corruption"),
    ("SELECT * FROM orders; DROP TABLE orders", "stacked statement"),
    ("SELECT * FROM pg_shadow", "a table nobody declared"),
]

print("INPUT")
for sql, note in STATEMENTS:
    print(f"   {sql[:62]:62} ({note})")
print()

print("OUTPUT")
allowed = blocked = 0
for sql, _note in STATEMENTS:
    v = validate(sql, max_rows=1000, known_tables=KNOWN)
    if v.ok:
        allowed += 1
        print(f"   ALLOWED   {sql[:58]}")
        flat = " ".join(v.rewritten.split())
        print(f"             rewritten: {flat[:74]}")
    else:
        blocked += 1
        print(f"   BLOCKED   {sql[:58]}")
        print(f"             {v.reason}")
print()
print(f"   {allowed} allowed, {blocked} blocked")
print("   Every allowed statement came back rewritten with a LIMIT it did")
print("   not ask for. A question that would return the whole table is not")
print("   dangerous, but it is not a good idea either.")
