#!/usr/bin/env python3
"""SNS投稿の疎通確認（X / Bluesky など、鍵が設定された全先へ1件投稿）。

ブランドカード画像を1枚生成し、画像付きで各配信先へ実投稿する。
鍵未設定の先は自動スキップ。--dry-run で記録のみ。

使い方:
    python scripts/social_test.py            # 実投稿（鍵がある先のみ）
    python scripts/social_test.py --dry-run  # 記録のみ
    python scripts/social_test.py --text "テスト" --no-image
"""
import argparse

import _bootstrap  # noqa: F401

from src.common.config import REPO_ROOT, load_config
from src.content import image as imgmod
from src.pdca.store import Store
from src.publish.social import broadcast, build_posters


def main() -> None:
    ap = argparse.ArgumentParser(description="SNS投稿の疎通確認")
    ap.add_argument("--text", default="【テスト】トレンド価格ウォッチ 稼働確認 https://example.com #楽天")
    ap.add_argument("--no-image", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    config = load_config()
    image_path = None
    if not args.no_image:
        out = REPO_ROOT / "data" / "site" / "img" / "_social_test.png"
        image_path = imgmod.make_card("稼働確認カード", out, price=4980, old_price=6980,
                                      badge="TEST", site_name=config["site"]["name"])

    posters = build_posters(Store(), config, dry_run=args.dry_run)
    results = broadcast(posters, args.text, "test", image_path=image_path)

    print("投稿結果:")
    for platform, res in results.items():
        if res:
            print(f"  {platform}: 成功 ({res})")
        else:
            print(f"  {platform}: スキップ/未設定/失敗")
    if not any(results.values()):
        print("→ どの先にも投稿されていません。.env に X_* または BLUESKY_* を設定してください。")


if __name__ == "__main__":
    main()
