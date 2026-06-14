"""複数SNSへの同報（X / Bluesky / …）。

差し替え可能なポスター群をまとめ、有効なものすべてに同じ速報を投げる。
各ポスターは鍵未設定なら自前でスキップ（フェイルソフト）。
"""
from __future__ import annotations

from pathlib import Path

from src.common.log import get_logger
from src.pdca.store import Store
from src.publish.bluesky import BlueskyPoster
from src.publish.typefully import TypefullyPoster
from src.publish.x_poster import XPoster

log = get_logger("publish.social")


def build_posters(store: Store, config: dict, dry_run: bool = False) -> list:
    """設定で有効化されたポスターを返す。

    Typefullyを使う場合、Typefully側からX/Bluesky等へ公開するため、
    直接投稿(x/bluesky)と二重にならないよう config で使い分ける。
    """
    social = config.get("social", {})
    posters: list = []
    if social.get("typefully", False):
        posters.append(TypefullyPoster(store, config, dry_run=dry_run))
    if social.get("x", True):
        posters.append(XPoster(store, config, dry_run=dry_run))
    if social.get("bluesky", True):
        posters.append(BlueskyPoster(store, config, dry_run=dry_run))
    return posters


def broadcast(posters: list, text: str, slug: str,
              image_path: str | Path | None = None) -> dict:
    """全ポスターへ投稿。{platform名: 結果} を返す。"""
    results: dict[str, str | None] = {}
    for p in posters:
        name = type(p).__name__.replace("Poster", "").lower()
        try:
            results[name] = p.post(text, slug, image_path=image_path)
        except Exception as exc:  # noqa: BLE001 — 1つの失敗で全体を止めない
            log.warning("%s 投稿で例外: %s", name, exc)
            results[name] = None
    return results
