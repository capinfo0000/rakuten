#!/usr/bin/env python3
"""X投稿の疎通確認（実鍵が必要）。

ブランドカード画像を1枚生成し、画像付きで1件だけ実投稿する。
鍵未設定なら投稿せず案内のみ。--no-image でテキストのみ。

使い方:
    python scripts/x_test.py
    python scripts/x_test.py --text "テスト投稿です" --no-image
"""
import argparse
from pathlib import Path

import _bootstrap  # noqa: F401

from src.common.config import REPO_ROOT, env, load_config
from src.content import image as imgmod
from src.pdca.store import Store
from src.publish.x_poster import XPoster


def main() -> None:
    ap = argparse.ArgumentParser(description="X投稿の疎通確認")
    ap.add_argument("--text", default="【テスト】トレンド価格ウォッチ 稼働確認 #楽天")
    ap.add_argument("--no-image", action="store_true")
    args = ap.parse_args()

    if not all(env(k) for k in ("X_API_KEY", "X_API_SECRET",
                                 "X_ACCESS_TOKEN", "X_ACCESS_SECRET")):
        print("X_* の鍵が未設定です。.env に投稿用の4つの鍵を設定してください"
              "（X Developer Portal、書き込み権限/OAuth1.0aユーザー文脈）。")
        return

    image_path = None
    if not args.no_image:
        out = REPO_ROOT / "data" / "site" / "img" / "_x_test.png"
        image_path = imgmod.make_card("稼働確認カード", out, price=4980, old_price=6980,
                                      badge="TEST",
                                      site_name=load_config()["site"]["name"])

    poster = XPoster(Store(), load_config(), dry_run=False)
    tweet_id = poster.post(args.text, "test", image_path=image_path)
    if tweet_id:
        print(f"投稿成功: tweet_id={tweet_id}"
              f"{' (画像付)' if image_path else ''}")
    else:
        print("投稿されませんでした（上限/権限/エラー）。ログを確認してください。")


if __name__ == "__main__":
    main()
