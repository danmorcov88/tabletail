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

There are two modes, with a deliberate trade-off between them.

**`--mode poll` (default).** The table is re-read every `--interval` seconds and
compared to the previous read, streaming each change as a colored line —
`INSERT` green, `UPDATE` yellow (with `old → new` per column), `DELETE` red.
Polling needs only a primary key and works on any PostgreSQL server, with zero
setup. Its honest trade-off: it sees the **net change per interval**, so a row
inserted and deleted between two polls is missed.

```bash
tabletail tail --table orders --mode wal
```

**`--mode wal` (advanced).** Streams changes through a **temporary logical
replication slot**, capturing *every* change — including `DELETE`s and
short-lived rows — with no polling of the table. Requirements and notes:

- The server must run with `wal_level = logical` (the bundled demo already does);
  otherwise tabletail prints exactly what to set.
- The role needs the `REPLICATION` privilege (or superuser).
- Uses the `wal2json` output plugin when installed, otherwise `test_decoding`
  (which ships with stock PostgreSQL).
- The slot is **temporary** and is also dropped explicitly on exit — orphaned
  slots make a server retain WAL, so cleanup is treated as critical.
- `--where` is not supported in this mode.

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
