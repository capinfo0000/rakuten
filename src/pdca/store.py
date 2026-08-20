"""SQLite スキーマ + DAO。

Python(バッチ) と PHP(go.php) が同一DBファイルを共有する。
低同時実行なので SQLite で十分。clicks は go.php からも追記される。
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from src.common.config import REPO_ROOT

DB_PATH = REPO_ROOT / "data" / "app.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS products (
    item_code TEXT PRIMARY KEY,
    name TEXT, url TEXT, affiliate_url TEXT,
    price INTEGER, shop_name TEXT, genre_id TEXT,
    review_count INTEGER, review_average REAL,
    affiliate_rate REAL, point_rate REAL,
    postage_flag INTEGER, availability INTEGER,
    image_url TEXT, score REAL DEFAULT 0,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS price_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_code TEXT, price INTEGER, availability INTEGER, rank INTEGER,
    observed_at TEXT,
    FOREIGN KEY(item_code) REFERENCES products(item_code)
);
CREATE INDEX IF NOT EXISTS idx_price_item ON price_history(item_code, observed_at);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_code TEXT, kind TEXT,            -- price_drop|restock|rank_up
    detail TEXT, observed_at TEXT
);

CREATE TABLE IF NOT EXISTS pages (
    slug TEXT PRIMARY KEY,
    kind TEXT, title TEXT, item_code TEXT,
    template_id TEXT,
    created_at TEXT, updated_at TEXT
);

CREATE TABLE IF NOT EXISTS headline_arms (
    template_id TEXT PRIMARY KEY,
    kind TEXT, reward REAL DEFAULT 0, pulls INTEGER DEFAULT 0,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS subscribers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE, source TEXT, created_at TEXT
);

CREATE TABLE IF NOT EXISTS drafts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic TEXT, angle TEXT, text TEXT,
    verdict TEXT, feedback TEXT, rating INTEGER,
    posted INTEGER DEFAULT 0, impressions INTEGER DEFAULT 0,
    created_at TEXT
);

-- メタ学習: 切り口の好み（意見の蓄積で次回生成に反映）
CREATE TABLE IF NOT EXISTS angle_prefs (
    angle TEXT PRIMARY KEY, score REAL DEFAULT 0, count INTEGER DEFAULT 0
);

-- メタ学習: 恒常的な編集方針（例「短く」「バカバカしく」）を蓄積し全生成に注入
CREATE TABLE IF NOT EXISTS style_directives (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    text TEXT UNIQUE, weight INTEGER DEFAULT 1, created_at TEXT
);

CREATE TABLE IF NOT EXISTS x_posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tweet_id TEXT, text TEXT, slug TEXT,
    posted_at TEXT
);

CREATE TABLE IF NOT EXISTS clicks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    link_id TEXT, src TEXT, ua TEXT, ts TEXT
);

CREATE TABLE IF NOT EXISTS links (
    link_id TEXT PRIMARY KEY,
    dest_url TEXT, item_code TEXT, created_at TEXT
);

CREATE TABLE IF NOT EXISTS arms (
    name TEXT PRIMARY KEY,
    kind TEXT,                            -- keyword|genre|niche
    reward REAL DEFAULT 0, pulls INTEGER DEFAULT 0,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS gsc_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query TEXT, page TEXT, impressions INTEGER, clicks INTEGER,
    ctr REAL, position REAL, day TEXT
);

CREATE TABLE IF NOT EXISTS ga4_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    page TEXT, sessions INTEGER, avg_engagement REAL, bounce_rate REAL, day TEXT
);

CREATE TABLE IF NOT EXISTS market_map (
    genre_id TEXT PRIMARY KEY,
    name TEXT, demand REAL, competition REAL, commission REAL,
    niche_score REAL, updated_at TEXT
);

CREATE TABLE IF NOT EXISTS trends (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    term TEXT, source TEXT, spike REAL, observed_at TEXT
);

CREATE TABLE IF NOT EXISTS x_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    reposts INTEGER, followers INTEGER, ts TEXT
);

CREATE TABLE IF NOT EXISTS social_posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    platform TEXT, post_id TEXT, text TEXT, slug TEXT, posted_at TEXT
);
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, db_path: Path | str | None = None) -> None:
        self.db_path = Path(db_path) if db_path else DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    @contextmanager
    def conn(self) -> Iterator[sqlite3.Connection]:
        con = sqlite3.connect(self.db_path)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA journal_mode=WAL")
        try:
            yield con
            con.commit()
        finally:
            con.close()

    def _init_schema(self) -> None:
        with self.conn() as con:
            con.executescript(SCHEMA)
            # 既存DBへの軽量マイグレーション（列が無ければ追加）
            cols = [r["name"] for r in con.execute("PRAGMA table_info(pages)").fetchall()]
            if "template_id" not in cols:
                con.execute("ALTER TABLE pages ADD COLUMN template_id TEXT")
            dcols = [r["name"] for r in con.execute("PRAGMA table_info(drafts)").fetchall()]
            for col in ("verdict", "feedback"):
                if dcols and col not in dcols:
                    con.execute(f"ALTER TABLE drafts ADD COLUMN {col} TEXT")
            if dcols and "rating" not in dcols:
                con.execute("ALTER TABLE drafts ADD COLUMN rating INTEGER")

    # ── products ───────────────────────────────────────
    def upsert_product(self, row: dict[str, Any]) -> None:
        row = {**row, "updated_at": now_iso()}
        cols = ("item_code", "name", "url", "affiliate_url", "price", "shop_name",
                "genre_id", "review_count", "review_average", "affiliate_rate",
                "point_rate", "postage_flag", "availability", "image_url",
                "score", "updated_at")
        values = [row.get(c) for c in cols]
        placeholders = ",".join("?" * len(cols))
        updates = ",".join(f"{c}=excluded.{c}" for c in cols if c != "item_code")
        with self.conn() as con:
            con.execute(
                f"INSERT INTO products ({','.join(cols)}) VALUES ({placeholders}) "
                f"ON CONFLICT(item_code) DO UPDATE SET {updates}",
                values,
            )

    def get_product(self, item_code: str) -> dict[str, Any] | None:
        with self.conn() as con:
            r = con.execute("SELECT * FROM products WHERE item_code=?", (item_code,)).fetchone()
            return dict(r) if r else None

    def top_products(self, limit: int = 50) -> list[dict[str, Any]]:
        with self.conn() as con:
            rows = con.execute(
                "SELECT * FROM products ORDER BY score DESC LIMIT ?", (limit,)).fetchall()
            return [dict(r) for r in rows]

    # ── price history / events ─────────────────────────
    def last_price(self, item_code: str) -> int | None:
        with self.conn() as con:
            r = con.execute(
                "SELECT price FROM price_history WHERE item_code=? "
                "ORDER BY observed_at DESC LIMIT 1", (item_code,)).fetchone()
            return r["price"] if r else None

    def add_price_point(self, item_code: str, price: int, availability: int,
                        rank: int | None = None) -> None:
        with self.conn() as con:
            con.execute(
                "INSERT INTO price_history (item_code, price, availability, rank, observed_at) "
                "VALUES (?,?,?,?,?)", (item_code, price, availability, rank, now_iso()))

    def price_series(self, item_code: str, limit: int = 60) -> list[dict[str, Any]]:
        with self.conn() as con:
            rows = con.execute(
                "SELECT price, availability, observed_at FROM price_history "
                "WHERE item_code=? ORDER BY observed_at DESC LIMIT ?",
                (item_code, limit)).fetchall()
            return [dict(r) for r in reversed(rows)]

    def add_event(self, item_code: str, kind: str, detail: str) -> None:
        with self.conn() as con:
            con.execute(
                "INSERT INTO events (item_code, kind, detail, observed_at) VALUES (?,?,?,?)",
                (item_code, kind, detail, now_iso()))

    def recent_events(self, limit: int = 50) -> list[dict[str, Any]]:
        with self.conn() as con:
            rows = con.execute(
                "SELECT * FROM events ORDER BY observed_at DESC LIMIT ?", (limit,)).fetchall()
            return [dict(r) for r in rows]

    # ── links / clicks ─────────────────────────────────
    def register_link(self, link_id: str, dest_url: str, item_code: str) -> None:
        with self.conn() as con:
            con.execute(
                "INSERT INTO links (link_id, dest_url, item_code, created_at) VALUES (?,?,?,?) "
                "ON CONFLICT(link_id) DO UPDATE SET dest_url=excluded.dest_url",
                (link_id, dest_url, item_code, now_iso()))

    def click_counts_by_src(self) -> dict[str, int]:
        with self.conn() as con:
            rows = con.execute(
                "SELECT src, COUNT(*) n FROM clicks GROUP BY src").fetchall()
            return {r["src"] or "web": r["n"] for r in rows}

    # ── pages / x_posts ────────────────────────────────
    def upsert_page(self, slug: str, kind: str, title: str, item_code: str | None,
                    template_id: str | None = None) -> None:
        with self.conn() as con:
            con.execute(
                "INSERT INTO pages (slug, kind, title, item_code, template_id, "
                "created_at, updated_at) VALUES (?,?,?,?,?,?,?) ON CONFLICT(slug) DO UPDATE SET "
                "title=excluded.title, template_id=excluded.template_id, "
                "updated_at=excluded.updated_at",
                (slug, kind, title, item_code, template_id, now_iso(), now_iso()))

    # ── 見出しA/Bテスト（バンディット） ───────────────
    def bump_headline_pull(self, template_id: str, kind: str) -> None:
        with self.conn() as con:
            con.execute(
                "INSERT INTO headline_arms (template_id, kind, reward, pulls, updated_at) "
                "VALUES (?,?,0,1,?) ON CONFLICT(template_id) DO UPDATE SET "
                "pulls=pulls+1, updated_at=excluded.updated_at",
                (template_id, kind, now_iso()))

    def headline_arms(self, kind: str) -> list[dict[str, Any]]:
        with self.conn() as con:
            rows = con.execute(
                "SELECT template_id, reward, pulls FROM headline_arms WHERE kind=?",
                (kind,)).fetchall()
            return [dict(r) for r in rows]

    def update_headline_rewards(self) -> None:
        """template別のクリックアウト数を reward に反映（clicks→links→pages）。"""
        with self.conn() as con:
            rows = con.execute(
                "SELECT p.template_id tid, COUNT(c.id) n FROM clicks c "
                "JOIN links l ON c.link_id=l.link_id "
                "JOIN pages p ON p.item_code=l.item_code "
                "WHERE p.template_id IS NOT NULL GROUP BY p.template_id").fetchall()
            for r in rows:
                con.execute("UPDATE headline_arms SET reward=? WHERE template_id=?",
                            (float(r["n"]), r["tid"]))

    # ── リスト化（購読者） ─────────────────────────────
    def add_subscriber(self, email: str, source: str = "web") -> bool:
        try:
            with self.conn() as con:
                con.execute(
                    "INSERT INTO subscribers (email, source, created_at) VALUES (?,?,?)",
                    (email, source, now_iso()))
            return True
        except sqlite3.IntegrityError:
            return False  # 既登録

    def subscriber_count(self) -> int:
        with self.conn() as con:
            return con.execute("SELECT COUNT(*) n FROM subscribers").fetchone()["n"]

    # ── X下書き（AI下書き→人が投稿） ───────────────────
    def add_draft(self, topic: str, angle: str, text: str) -> int:
        with self.conn() as con:
            cur = con.execute(
                "INSERT INTO drafts (topic, angle, text, created_at) VALUES (?,?,?,?)",
                (topic, angle, text, now_iso()))
            return cur.lastrowid

    def recent_drafts(self, limit: int = 50) -> list[dict[str, Any]]:
        with self.conn() as con:
            rows = con.execute(
                "SELECT * FROM drafts ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
            return [dict(r) for r in rows]

    def mark_draft_posted(self, draft_id: int, impressions: int = 0) -> None:
        with self.conn() as con:
            con.execute("UPDATE drafts SET posted=1, impressions=? WHERE id=?",
                        (impressions, draft_id))

    def angle_performance(self) -> list[dict[str, Any]]:
        """angle別の平均インプ（人が入力した実績から学習の素）。"""
        with self.conn() as con:
            rows = con.execute(
                "SELECT angle, COUNT(*) posted, AVG(impressions) avg_imp "
                "FROM drafts WHERE posted=1 GROUP BY angle ORDER BY avg_imp DESC").fetchall()
            return [dict(r) for r in rows]

    # ── メタ学習: 意見を蓄積して次回生成に反映 ─────────
    def set_draft_feedback(self, draft_id: int, verdict: str,
                           feedback: str | None = None, rating: int | None = None) -> None:
        with self.conn() as con:
            con.execute("UPDATE drafts SET verdict=?, feedback=?, rating=? WHERE id=?",
                        (verdict, feedback, rating, draft_id))

    def bump_angle_pref(self, angle: str, delta: float) -> None:
        with self.conn() as con:
            con.execute(
                "INSERT INTO angle_prefs (angle, score, count) VALUES (?,?,1) "
                "ON CONFLICT(angle) DO UPDATE SET score=score+?, count=count+1",
                (angle, delta, delta))

    def angle_pref_scores(self) -> dict[str, float]:
        with self.conn() as con:
            rows = con.execute("SELECT angle, score, count FROM angle_prefs").fetchall()
            return {r["angle"]: (r["score"] / r["count"] if r["count"] else 0.0) for r in rows}

    def add_style_directive(self, text: str) -> None:
        text = text.strip()
        if not text:
            return
        with self.conn() as con:
            con.execute(
                "INSERT INTO style_directives (text, weight, created_at) VALUES (?,1,?) "
                "ON CONFLICT(text) DO UPDATE SET weight=weight+1",
                (text, now_iso()))

    def top_style_directives(self, limit: int = 5) -> list[str]:
        with self.conn() as con:
            rows = con.execute(
                "SELECT text FROM style_directives ORDER BY weight DESC, created_at DESC "
                "LIMIT ?", (limit,)).fetchall()
            return [r["text"] for r in rows]

    def exemplar_drafts(self, limit: int = 3) -> list[str]:
        """伸びた/採用した過去ドラフトを手本として返す（few-shot用）。"""
        with self.conn() as con:
            rows = con.execute(
                "SELECT text FROM drafts "
                "WHERE verdict IN ('keep','post') OR rating>=4 OR impressions>0 "
                "ORDER BY impressions DESC, rating DESC, id DESC LIMIT ?", (limit,)).fetchall()
            return [r["text"] for r in rows]

    def record_x_post(self, tweet_id: str, text: str, slug: str) -> None:
        with self.conn() as con:
            con.execute(
                "INSERT INTO x_posts (tweet_id, text, slug, posted_at) VALUES (?,?,?,?)",
                (tweet_id, text, slug, now_iso()))

    def x_posts_today(self) -> int:
        today = datetime.now(timezone.utc).date().isoformat()
        with self.conn() as con:
            r = con.execute(
                "SELECT COUNT(*) n FROM x_posts WHERE posted_at LIKE ?",
                (f"{today}%",)).fetchone()
            return r["n"]

    def x_posts_this_month(self) -> int:
        month = datetime.now(timezone.utc).strftime("%Y-%m")
        with self.conn() as con:
            r = con.execute(
                "SELECT COUNT(*) n FROM x_posts WHERE posted_at LIKE ?",
                (f"{month}%",)).fetchone()
            return r["n"]

    # ── social posts（X以外の無料SNS: Bluesky/Mastodon/Webhook等）──
    def record_social_post(self, platform: str, post_id: str, text: str, slug: str) -> None:
        with self.conn() as con:
            con.execute(
                "INSERT INTO social_posts (platform, post_id, text, slug, posted_at) "
                "VALUES (?,?,?,?,?)", (platform, post_id, text, slug, now_iso()))

    def social_posts_today(self, platform: str) -> int:
        today = datetime.now(timezone.utc).date().isoformat()
        with self.conn() as con:
            r = con.execute(
                "SELECT COUNT(*) n FROM social_posts WHERE platform=? AND posted_at LIKE ?",
                (platform, f"{today}%")).fetchone()
            return r["n"]

    def social_posts_this_month(self, platform: str) -> int:
        month = datetime.now(timezone.utc).strftime("%Y-%m")
        with self.conn() as con:
            r = con.execute(
                "SELECT COUNT(*) n FROM social_posts WHERE platform=? AND posted_at LIKE ?",
                (platform, f"{month}%")).fetchone()
            return r["n"]

    # ── market map / trends / arms ─────────────────────
    def upsert_market(self, genre_id: str, name: str, demand: float,
                      competition: float, commission: float, niche_score: float) -> None:
        with self.conn() as con:
            con.execute(
                "INSERT INTO market_map (genre_id, name, demand, competition, commission, "
                "niche_score, updated_at) VALUES (?,?,?,?,?,?,?) "
                "ON CONFLICT(genre_id) DO UPDATE SET name=excluded.name, demand=excluded.demand, "
                "competition=excluded.competition, commission=excluded.commission, "
                "niche_score=excluded.niche_score, updated_at=excluded.updated_at",
                (genre_id, name, demand, competition, commission, niche_score, now_iso()))

    def best_niches(self, limit: int = 5) -> list[dict[str, Any]]:
        with self.conn() as con:
            rows = con.execute(
                "SELECT * FROM market_map ORDER BY niche_score DESC LIMIT ?", (limit,)).fetchall()
            return [dict(r) for r in rows]

    def add_trend(self, term: str, source: str, spike: float) -> None:
        with self.conn() as con:
            con.execute(
                "INSERT INTO trends (term, source, spike, observed_at) VALUES (?,?,?,?)",
                (term, source, spike, now_iso()))
