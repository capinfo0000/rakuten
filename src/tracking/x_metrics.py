"""X指標(リポスト/フォロワー)の非公式取得。

公式読み取りは有料のため、HTTPで取れる範囲のみ best-effort。
取れなければスキップ（フェイルソフト）。Xの主指標は ?src=x クリックアウトで代替。
将来 公式API実装へ差し替え可能なよう、この1ファイルに隔離。
"""
from __future__ import annotations

from src.common.config import env
from src.common.http import ThrottledClient
from src.common.log import get_logger
from src.pdca.store import Store

log = get_logger("tracking.x_metrics")


def fetch_follower_count(http: ThrottledClient | None = None) -> int | None:
    """自身の公開プロフィールからフォロワー数を best-effort 取得。"""
    username = env("X_USERNAME")
    if not username:
        return None
    http = http or ThrottledClient(min_interval=3.0)
    # Xは強い anti-bot のため取得できないことが多い。失敗は想定内。
    html = http.get_text(f"https://x.com/{username}")
    if not html:
        log.info("X指標: 取得不可のためスキップ（クリックアウトで代替）")
        return None
    try:
        import re
        m = re.search(r'([\d,]+)\s*Followers', html)
        return int(m.group(1).replace(",", "")) if m else None
    except Exception as exc:  # noqa: BLE001
        log.warning("X指標パース失敗: %s", exc)
        return None


def record(store: Store) -> dict:
    """フォロワー数を取得できたら x_stats に記録。取れなければ何もしない。"""
    followers = fetch_follower_count()
    if followers is not None:
        with store.conn() as con:
            con.execute(
                "INSERT INTO x_stats (reposts, followers, ts) "
                "VALUES (0, ?, datetime('now'))", (followers,))
    return {"followers": followers}
