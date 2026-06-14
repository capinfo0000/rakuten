"""X(旧Twitter)自動投稿。

- 投稿のみ（無料枠）。読み取り・自動フォロー/いいねはしない（規約順守）。
- 月内/日次の投稿上限をローカル管理。同一文の反復を避ける（スパム回避）。
- 鍵未設定 or dry_run はログのみ（全自動を止めない）。
"""
from __future__ import annotations

from src.common.config import env
from src.common.log import get_logger
from src.pdca.store import Store

log = get_logger("publish.x")


class XPoster:
    def __init__(self, store: Store, config: dict, dry_run: bool = False) -> None:
        self.store = store
        self.dry_run = dry_run
        xcfg = config.get("x", {})
        self.max_per_day = xcfg.get("max_posts_per_day", 5)
        self.max_per_month = xcfg.get("max_posts_per_month", 400)

    def _within_limits(self) -> bool:
        if self.store.x_posts_today() >= self.max_per_day:
            log.info("本日のX投稿上限(%s)に達したためスキップ", self.max_per_day)
            return False
        if self.store.x_posts_this_month() >= self.max_per_month:
            log.info("今月のX投稿上限(%s)に達したためスキップ", self.max_per_month)
            return False
        return True

    def _client(self):
        key = env("X_API_KEY")
        secret = env("X_API_SECRET")
        token = env("X_ACCESS_TOKEN")
        token_secret = env("X_ACCESS_SECRET")
        if not all([key, secret, token, token_secret]):
            return None
        try:
            import tweepy  # type: ignore

            return tweepy.Client(consumer_key=key, consumer_secret=secret,
                                 access_token=token, access_token_secret=token_secret)
        except Exception as exc:  # noqa: BLE001
            log.warning("Xクライアント初期化スキップ: %s", exc)
            return None

    def post(self, text: str, slug: str, image_path=None) -> str | None:
        """投稿。tweet_id を返す。上限/失敗/dry_runでは None。"""
        if not self._within_limits():
            return None
        if self.dry_run:
            log.info("[dry-run] X投稿: %s", text.replace("\n", " "))
            self.store.record_x_post("dry-run", text, slug)
            return "dry-run"

        client = self._client()
        if client is None:
            log.info("X鍵未設定のため投稿スキップ（記録のみ）: %s", text[:40])
            return None
        try:
            resp = client.create_tweet(text=text)
            tweet_id = str(resp.data.get("id")) if resp and resp.data else None
            if tweet_id:
                self.store.record_x_post(tweet_id, text, slug)
                log.info("X投稿成功 id=%s", tweet_id)
            return tweet_id
        except Exception as exc:  # noqa: BLE001
            log.warning("X投稿失敗: %s", exc)
            return None
