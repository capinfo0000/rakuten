"""統合スコア算出（PDCAの"Check"）。

SEO(表示/CTR/順位) + 維持率 + クリックアウト + X指標 をニッチ/ジャンル単位の
報酬(reward)に変換し、arms に蓄積する。optimizer がこの reward を使う。
"""
from __future__ import annotations

from src.common.log import get_logger
from src.pdca.store import Store, now_iso
from src.tracking import clicks

log = get_logger("pdca.scorer")


def _genre_clickouts(store: Store) -> dict[str, int]:
    """ジャンル(=arm)別のクリックアウト数を links→products から集計。"""
    with store.conn() as con:
        rows = con.execute(
            "SELECT p.genre_id gid, COUNT(c.id) n FROM clicks c "
            "JOIN links l ON c.link_id = l.link_id "
            "JOIN products p ON l.item_code = p.item_code "
            "GROUP BY p.genre_id").fetchall()
        return {r["gid"]: r["n"] for r in rows}


def update_arms(store: Store) -> list[dict]:
    """各ジャンルarmの reward を更新（クリックアウト＋GSC表示の合成）。"""
    clickouts = _genre_clickouts(store)

    # GSCのジャンル紐付けは難しいので、全体表示数を需要係数として薄く加味
    total_impr = 0
    with store.conn() as con:
        r = con.execute("SELECT COALESCE(SUM(impressions),0) s FROM gsc_metrics").fetchone()
        total_impr = r["s"]

    updated = []
    with store.conn() as con:
        genres = con.execute("SELECT DISTINCT genre_id FROM products").fetchall()
        for g in genres:
            gid = g["genre_id"]
            co = clickouts.get(gid, 0)
            reward = co * 1.0 + (total_impr * 0.001)
            con.execute(
                "INSERT INTO arms (name, kind, reward, pulls, updated_at) "
                "VALUES (?, 'genre', ?, 1, ?) "
                "ON CONFLICT(name) DO UPDATE SET reward=?, pulls=pulls+1, updated_at=?",
                (gid, reward, now_iso(), reward, now_iso()))
            updated.append({"genre_id": gid, "clickouts": co, "reward": round(reward, 3)})
    log.info("arm更新 %s件 / 総クリックアウト%s", len(updated), clicks.total_clickouts(store))
    return updated
