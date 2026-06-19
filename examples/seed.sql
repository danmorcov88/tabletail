-- Demo schema for tabletail. Loaded automatically when the container starts.
-- An `orders` table with a primary key and an updated_at column — exactly the
-- shape the polling tail relies on.

CREATE TABLE IF NOT EXISTS orders (
    id          SERIAL PRIMARY KEY,
    customer    TEXT          NOT NULL,
    status      TEXT          NOT NULL DEFAULT 'pending',
    amount      NUMERIC(10, 2) NOT NULL,
    updated_at  TIMESTAMPTZ   NOT NULL DEFAULT now()
);

INSERT INTO orders (customer, status, amount) VALUES
    ('Ana Pop',        'paid',     120.00),
    ('Mihai Ionescu',  'pending',   45.50),
    ('Elena Radu',     'paid',     310.75),
    ('George Stan',    'shipped',   89.99),
    ('Ioana Dumitru',  'pending',  150.00);
