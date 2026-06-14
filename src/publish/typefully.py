"""Typefully API 連携 — 下書き保存・予約投稿。

Typefullyは X / Bluesky / Threads / LinkedIn / Mastodon へ API1本で
下書き作成・予約・公開できる。無料枠は月15投稿・予約1件までと小さいので、
主に「下書き保存（人の最終確認）」用途。鍵未設定/失敗時はスキップ（フェイルソフト）。

投稿IFは他ポスターと同じ post(text, slug, image_path)。schedule は config で指定。
"""
from __future__ import annotations

from pathlib import Path

import requests

from src.common.config import env
from src.common.log import get_logger
from src.pdca.store import Store

log = get_logger("publish.typefully")

# v1は2026/6/15まで有効。シンプルなのでv1のdrafts作成を使用。
DRAFTS_URL = "https://api.typefully.com/v1/drafts/"
PLATFORM = "typefully"


class TypefullyPoster:
    def __init__(self, store: Store, config: dict, dry_run: bool = False) -> None:
        self.store = store
        self.dry_run = dry_run
        tcfg = config.get("typefully", {})
        # "next-free-slot"=自動で次の空き枠に予約 / ""=下書き保存のみ
        self.schedule = tcfg.get("schedule", "")
        self.max_per_day = tcfg.get("max_posts_per_day", 10)
        self.max_per_month = tcfg.get("max_posts_per_month", 15)  # 無料枠の月上限

    def available(self) -> bool:
        return bool(env("TYPEFULLY_API_KEY"))

    def _within_limits(self) -> bool:
        if self.store.social_posts_today(PLATFORM) >= self.max_per_day:
            log.info("本日のTypefully上限(%s)に達したためスキップ", self.max_per_day)
            return False
        if self.store.social_posts_this_month(PLATFORM) >= self.max_per_month:
            log.info("今月のTypefully上限(%s)に達したためスキップ（無料枠）", self.max_per_month)
            return False
        return True

    def post(self, text: str, slug: str, image_path: str | Path | None = None) -> str | None:
        """下書き作成（schedule設定時は予約）。draft idを返す。"""
        if not self.available():
            log.info("Typefully未設定のためスキップ: %s", text[:30])
            return None
        if not self._within_limits():
            return None

        # Typefully API は画像添付に未対応のためテキスト中心（URLのOGPでカード表示）
        if self.dry_run:
            log.info("[dry-run] Typefully下書き%s: %s",
                     f"(予約:{self.schedule})" if self.schedule else "",
                     text.replace("\n", " "))
            self.store.record_social_post(PLATFORM, "dry-run", text, slug)
            return "dry-run"

        payload: dict = {"content": text}
        if self.schedule:
            payload["schedule-date"] = self.schedule  # "next-free-slot" など
        try:
            r = requests.post(DRAFTS_URL, json=payload,
                              headers={"X-API-KEY": env("TYPEFULLY_API_KEY")}, timeout=15)
            r.raise_for_status()
            draft_id = str(r.json().get("id", ""))
            self.store.record_social_post(PLATFORM, draft_id or "ok", text, slug)
            log.info("Typefully下書き作成 id=%s %s", draft_id,
                     f"(予約:{self.schedule})" if self.schedule else "")
            return draft_id or "ok"
        except (requests.RequestException, ValueError) as exc:
            log.warning("Typefully下書き作成失敗: %s", exc)
            return None
