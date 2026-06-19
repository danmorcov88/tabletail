"""CLI wiring: help, version, argument validation, and command invocation."""

from __future__ import annotations

from typer.testing import CliRunner

from tabletail.cli import app

runner = CliRunner()


# --- no database needed ----------------------------------------------------- #


def test_help_lists_commands():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for command in ("tail", "diff", "snapshot"):
        assert command in result.output


def test_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "tabletail" in result.output


def test_snapshot_requires_dsn(monkeypatch, tmp_path):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    result = runner.invoke(app, ["snapshot", "--table", "x", "--out", str(tmp_path / "x.json")])
    assert result.exit_code == 1
    assert "connection string" in result.output.lower()


def test_diff_requires_two_files():
    result = runner.invoke(app, ["diff", "only-one.json"])
    assert result.exit_code == 1
    assert "two snapshot" in result.output.lower()


def test_tail_rejects_unknown_mode(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgres://x/y")
    result = runner.invoke(app, ["tail", "--table", "x", "--mode", "bogus"])
    assert result.exit_code == 1
    assert "mode" in result.output.lower()


def test_tail_wal_rejects_where(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgres://x/y")
    result = runner.invoke(app, ["tail", "--table", "x", "--mode", "wal", "--where", "id=1"])
    assert result.exit_code == 1
    assert "where" in result.output.lower()


# --- database-backed -------------------------------------------------------- #


def test_snapshot_and_diff_roundtrip(dsn, orders, writer, tmp_path):
    s1, s2 = tmp_path / "s1.json", tmp_path / "s2.json"

    r1 = runner.invoke(app, ["snapshot", "--dsn", dsn, "--table", orders, "--out", str(s1)])
    assert r1.exit_code == 0, r1.output
    assert s1.exists()

    writer.execute(f"UPDATE {orders} SET status = 'paid' WHERE id = 2")

    r2 = runner.invoke(app, ["snapshot", "--dsn", dsn, "--table", orders, "--out", str(s2)])
    assert r2.exit_code == 0, r2.output

    r3 = runner.invoke(app, ["diff", str(s1), str(s2)])
    assert r3.exit_code == 0, r3.output
    assert "changed" in r3.output.lower()
