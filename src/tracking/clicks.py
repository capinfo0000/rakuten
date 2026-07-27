"""go.php が書いたクリックログ(SQLite)の集計。"""
from __future__ import annotations

from datetime import datetime, timezone

from src.pdca.store import Store


def clickouts_by_source(store: Store) -> dict[str, int]:
    """流入元別クリックアウト数（web/x）。"""
    return store.click_counts_by_src()


def total_clickouts(store: Store) -> int:
    return sum(store.click_counts_by_src().values())


def clickouts_by_link(store: Store) -> dict[str, int]:
    with store.conn() as con:
        rows = con.execute(
            "SELECT link_id, COUNT(*) n FROM clicks GROUP BY link_id").fetchall()
        return {r["link_id"]: r["n"] for r in rows}


def clickouts_since(store: Store, iso_day: str) -> int:
    with store.conn() as con:
        r = con.execute("SELECT COUNT(*) n FROM clicks WHERE ts >= ?", (iso_day,)).fetchone()
        return r["n"]


def today_iso() -> str:
    return datetime.now(timezone.utc).date().isoformat()
