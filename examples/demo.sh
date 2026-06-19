#!/usr/bin/env bash
#
# Drives a lively stream of changes against the demo `orders` table so you can
# record a GIF of `tabletail tail` reacting live.
#
# Terminal 1 — the one you record:
#   export DATABASE_URL=postgres://demo:demo@localhost:5433/demo
#   tabletail tail --table orders --interval 1
#
# Terminal 2 — drive the changes:
#   bash examples/demo.sh
#
# Requires the demo database to be running:
#   docker compose -f examples/docker-compose.yml up -d
set -euo pipefail

psql() { docker exec -i tabletail-demo psql -U demo -d demo -q "$@" >/dev/null; }
step() { psql -c "$1"; sleep "${2:-1.3}"; }

# Reset to a clean baseline of five orders.
step "TRUNCATE orders RESTART IDENTITY;
      INSERT INTO orders (customer, status, amount) VALUES
        ('Ana Pop',       'paid',    120.00),
        ('Mihai Ionescu', 'pending',  45.50),
        ('Elena Radu',    'paid',    310.75),
        ('George Stan',   'shipped',  89.99),
        ('Ioana Dumitru', 'pending', 150.00);" 1.6

# A natural sequence of inserts, updates and deletes.
step "INSERT INTO orders (customer, status, amount) VALUES ('Vlad Nour', 'pending', 75.25);"
step "UPDATE orders SET status = 'paid' WHERE customer = 'Mihai Ionescu';"
step "UPDATE orders SET amount = 500.00, status = 'shipped' WHERE customer = 'Elena Radu';"
step "INSERT INTO orders (customer, status, amount) VALUES ('Diana Marin', 'new', 42.00);"
step "DELETE FROM orders WHERE customer = 'Ioana Dumitru';"
step "UPDATE orders SET status = 'delivered' WHERE customer = 'George Stan';"
step "INSERT INTO orders (customer, status, amount) VALUES ('Radu Ene', 'pending', 12.50);"
step "DELETE FROM orders WHERE customer = 'Vlad Nour';"

echo "demo complete"
