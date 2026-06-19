# tabletail

[![CI](https://github.com/danmorcov/tabletail/actions/workflows/ci.yml/badge.svg)](https://github.com/danmorcov/tabletail/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)

**`tail -f` and `git diff`, but for PostgreSQL tables.** See what changes in a
table — live (`tail`) or as the difference between two points in time (`diff`).
Read-only on your data, one command, instant result.

![tabletail demo](docs/demo.gif)

## 30-second tour

```bash
pip install tabletail

# Watch a table change live (polling — works on any PostgreSQL, zero setup)
tabletail tail --dsn postgres://user:pass@host/db --table orders
```

```text
watching orders (5 rows)  every 2s  ·  Ctrl-C to stop
12:01:03 + INSERT id=6   customer=Vlad Nour  status=pending  amount=75.25
12:01:05 ~ UPDATE id=2   status: pending → paid
12:01:07 - DELETE id=5   customer=Ioana Dumitru  status=pending  amount=150.00
```

`INSERT` is green, `UPDATE` is yellow (with `old → new` per column), `DELETE` is
red. That's the whole idea.

## Why this exists

"What changed in this table in the last five minutes?" is a question data
engineers answer constantly — and usually by hand-writing ad-hoc queries or
waiting on a batch job. Full observability stacks are heavy and need real setup.
tabletail is the opposite: a connection string and a table name, and you are
watching changes in seconds. Small, sharp, and read-only.

## Usage

The DSN can come from `--dsn` or the `DATABASE_URL` environment variable, so it
never lands in your shell history.

```bash
export DATABASE_URL=postgres://user:pass@host/db
```

### `tail` — follow a table live

```bash
# Polling (default). Re-reads every --interval seconds.
tabletail tail --table orders --interval 2

# Only the rows you care about
tabletail tail --table orders --where "status = 'paid'"

# WAL mode: capture *every* change, including DELETEs (see Design decisions)
tabletail tail --table orders --mode wal
```

### `diff` — compare two points in time

```bash
# Snapshot now, change things, snapshot again, then diff the files
tabletail snapshot --table orders --out before.json
# ... time passes, data changes ...
tabletail snapshot --table orders --out after.json
tabletail diff before.json after.json

# Or do it in one shot: snapshot, wait 30s, re-snapshot, show the difference
tabletail diff --table orders --wait 30
```

```text
orders: +1 added  ~2 changed  -1 removed

           Changed (2)
┌──────┬────────┬──────────────────┐
│ row  │ column │ old → new        │
├──────┼────────┼──────────────────┤
│ id=2 │ status │ pending → paid   │
│ id=3 │ amount │ 310.75 → 500.00  │
└──────┴────────┴──────────────────┘
```

## Design decisions

These are the trade-offs worth understanding before you rely on it.

**Read-only on your data, always.** tabletail opens its connections in
session-level read-only mode — it is structurally incapable of modifying the
data it watches. WAL mode is the one place that needs a writable session
(consuming a replication slot advances server-side replication state), but even
there it never touches a user table: no writes, no `ALTER`, nothing.

**Two tail modes, one honest trade-off.**

| | `--mode poll` (default) | `--mode wal` |
|---|---|---|
| Setup | none — any PostgreSQL | needs `wal_level=logical` + `REPLICATION` |
| Catches DELETEs | yes (key disappears) | yes |
| Misses fast intra-interval changes | yes (sees net change per poll) | **no** — every change is captured |
| How | re-read + diff on primary key | temporary logical replication slot |

Polling is dead simple and works everywhere, at the cost of only seeing the net
change between two reads. WAL decoding is complete — PostgreSQL buffers every
change in a replication slot until tabletail reads it — at the cost of server
configuration. Offering both, and being clear about why, is the point.

**Replication slots are cleaned up, hard.** An orphaned logical slot makes a
server retain WAL forever. tabletail's slot is created `TEMPORARY` (PostgreSQL
drops it automatically when the session ends, even on a crash) **and** dropped
explicitly on exit. Both paths are tested.

**Snapshots are plain, readable JSON.** Values are stored as JSON primitives, so
a snapshot file is human-readable and an in-memory snapshot compares identically
to one round-tripped through disk.

## Requirements

- Python 3.11+
- PostgreSQL (any reasonably recent version)
- For `--mode wal`: `wal_level = logical`, the `REPLICATION` privilege (or
  superuser), and the `wal2json` output plugin if installed — otherwise tabletail
  falls back to `test_decoding`, which ships with stock PostgreSQL.

## Limitations

- Both tail modes match rows by **primary key**; a table without one can't be
  tailed or diffed.
- Polling sees the **net change per interval** — a row inserted and deleted
  between two polls is missed. Use `--mode wal` when you need every change.
- `--where` is not supported in `--mode wal`.

## Try it locally

A demo PostgreSQL with a seeded `orders` table is included:

```bash
docker compose -f examples/docker-compose.yml up -d
export DATABASE_URL=postgres://demo:demo@localhost:5433/demo

tabletail tail --table orders --interval 1
# In another terminal, drive some changes:
bash examples/demo.sh
```

## Development

```bash
pip install -e ".[dev]"
ruff check .
pytest                    # set TABLETAIL_TEST_DSN, or rely on the demo above
```

## License

MIT © Dan Morcov
