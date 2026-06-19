# tabletail

**`tail -f` and `git diff`, but for PostgreSQL tables.** See what changes in a
table — live (`tail`) or as the difference between two points in time (`diff`).

> _Demo GIF goes here (added in the final phase)._

Read-only on your data. One connection string and a table name is all it needs.

## Install

```bash
pip install tabletail
```

_(Not on PyPI yet — for now install from source, see below.)_

## Usage

```bash
# Follow changes live (polling, zero setup)
tabletail tail --dsn postgres://user:pass@host/db --table orders

# Compare two snapshots taken over time
tabletail snapshot --dsn postgres://user:pass@host/db --table orders --out snap1.json
tabletail snapshot --dsn postgres://user:pass@host/db --table orders --out snap2.json
tabletail diff snap1.json snap2.json
```

The DSN can also come from the `DATABASE_URL` environment variable, so it never
appears in your shell history.

## Development

```bash
pip install -e ".[dev]"
tabletail --help
```

A demo Postgres (with a seeded `orders` table) is available for local testing:

```bash
docker compose -f examples/docker-compose.yml up -d
# DSN: postgres://demo:demo@localhost:5433/demo
```

## License

MIT © Dan Morcov
