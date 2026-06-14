"""Bluesky(AT Protocol)への自動投稿 — 完全無料・画像対応・審査不要。

Xの従量課金を避けつつ「速報の自動投稿」を実現する無料プロバイダ。
アプリパスワード（Bluesky設定で発行）だけで利用可。requestsのみ（追加SDK不要）。
鍵未設定/失敗時はスキップ（フェイルソフト）。投稿IFは XPoster と同じ post(text, slug, image_path)。
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import requests

from src.common.config import env
from src.common.log import get_logger
from src.pdca.store import Store

log = get_logger("publish.bluesky")

PDS = "https://bsky.social/xrpc"
PLATFORM = "bluesky"


class BlueskyPoster:
    def __init__(self, store: Store, config: dict, dry_run: bool = False) -> None:
        self.store = store
        self.dry_run = dry_run
        bcfg = config.get("bluesky", {})
        self.max_per_day = bcfg.get("max_posts_per_day", 20)
        self.max_per_month = bcfg.get("max_posts_per_month", 600)

    # ── 認証情報 ──────────────────────────────────────
    def _creds(self) -> tuple[str, str] | None:
        handle = env("BLUESKY_HANDLE")
        password = env("BLUESKY_APP_PASSWORD")
        if not (handle and password):
            return None
        return handle, password

    def available(self) -> bool:
        return self._creds() is not None

    def _within_limits(self) -> bool:
        if self.store.social_posts_today(PLATFORM) >= self.max_per_day:
            log.info("本日のBluesky投稿上限(%s)に達したためスキップ", self.max_per_day)
            return False
        if self.store.social_posts_this_month(PLATFORM) >= self.max_per_month:
            log.info("今月のBluesky投稿上限(%s)に達したためスキップ", self.max_per_month)
            return False
        return True

    # ── AT Protocol 呼び出し ──────────────────────────
    def _login(self) -> tuple[str, str] | None:
        creds = self._creds()
        if not creds:
            return None
        handle, password = creds
        try:
            r = requests.post(f"{PDS}/com.atproto.server.createSession",
                              json={"identifier": handle, "password": password}, timeout=15)
            r.raise_for_status()
            data = r.json()
            return data["accessJwt"], data["did"]
        except (requests.RequestException, KeyError, ValueError) as exc:
            log.warning("Blueskyログイン失敗: %s", exc)
            return None

    def _upload_blob(self, jwt: str, image_path: str | Path) -> dict | None:
        try:
            data = Path(image_path).read_bytes()
            r = requests.post(f"{PDS}/com.atproto.repo.uploadBlob", data=data,
                              headers={"Authorization": f"Bearer {jwt}",
                                       "Content-Type": "image/png"}, timeout=30)
            r.raise_for_status()
            return r.json().get("blob")
        except (requests.RequestException, ValueError, OSError) as exc:
            log.warning("Blueskyメディアupload失敗（テキストのみ）: %s", exc)
            return None

    def _create_record(self, jwt: str, did: str, record: dict) -> str | None:
        try:
            r = requests.post(f"{PDS}/com.atproto.repo.createRecord",
                              headers={"Authorization": f"Bearer {jwt}"},
                              json={"repo": did, "collection": "app.bsky.feed.post",
                                    "record": record}, timeout=15)
            r.raise_for_status()
            return r.json().get("uri")
        except (requests.RequestException, ValueError) as exc:
            log.warning("Bluesky投稿失敗: %s", exc)
            return None

    # ── 投稿 ──────────────────────────────────────────
    def post(self, text: str, slug: str, image_path: str | Path | None = None) -> str | None:
        if not self.available():
            log.info("Bluesky未設定のためスキップ: %s", text[:30])
            return None
        if not self._within_limits():
            return None

        has_img = bool(image_path and Path(image_path).exists())
        if self.dry_run:
            log.info("[dry-run] Bluesky投稿%s: %s", "(画像付)" if has_img else "",
                     text.replace("\n", " "))
            self.store.record_social_post(PLATFORM, "dry-run", text, slug)
            return "dry-run"

        session = self._login()
        if not session:
            return None
        jwt, did = session

        record = {
            "$type": "app.bsky.feed.post",
            "text": text,
            "createdAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "langs": ["ja"],
        }
        facets = build_link_facets(text)
        if facets:
            record["facets"] = facets
        if has_img:
            blob = self._upload_blob(jwt, image_path)
            if blob:
                record["embed"] = {"$type": "app.bsky.embed.images",
                                   "images": [{"alt": text[:120], "image": blob}]}

        uri = self._create_record(jwt, did, record)
        if uri:
            self.store.record_social_post(PLATFORM, uri, text, slug)
            log.info("Bluesky投稿成功 %s %s", uri, "(画像付)" if "embed" in record else "")
        return uri


def build_link_facets(text: str) -> list[dict]:
    """本文中のURLをクリック可能にする facet を生成（UTF-8バイトオフセット）。"""
    import re

    facets: list[dict] = []
    encoded = text.encode("utf-8")
    for m in re.finditer(rb"https?://[^\s]+", encoded):
        facets.append({
            "index": {"byteStart": m.start(), "byteEnd": m.end()},
            "features": [{"$type": "app.bsky.richtext.facet#link",
                          "uri": m.group().decode("utf-8")}],
        })
    return facets
