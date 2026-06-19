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

# ...every second, only paid orders
tabletail tail --dsn postgres://user:pass@host/db --table orders --interval 1 --where "status='paid'"

# Compare two snapshots taken over time
tabletail snapshot --dsn postgres://user:pass@host/db --table orders --out snap1.json
tabletail snapshot --dsn postgres://user:pass@host/db --table orders --out snap2.json
tabletail diff snap1.json snap2.json
```

The DSN can also come from the `DATABASE_URL` environment variable, so it never
appears in your shell history.

### How `tail` works

The default mode is **polling**: the table is re-read every `--interval` seconds
and compared to the previous read, streaming each change as a colored line —
`INSERT` green, `UPDATE` yellow (with `old → new` per column), `DELETE` red.

Polling needs only a primary key and works on any PostgreSQL server, with zero
setup. Its honest trade-off: it sees the **net change per interval**, so a row
that is inserted and deleted between two polls is missed. For complete,
every-change capture (including transient rows), the WAL mode is on the way.

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
