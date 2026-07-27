#!/usr/bin/env python3
"""生成物(data/site/)を public_html へ配置。

コアサーバーでは cron がサーバ内で走るため、既定はローカルコピー（rsync的）。
SFTP配置が必要な場合は環境変数 DEPLOY_DEST にローカルの公開ディレクトリを指定。
"""
import argparse
import os
import shutil
from pathlib import Path

import _bootstrap  # noqa: F401

from src.common.config import REPO_ROOT

SITE_DIR = REPO_ROOT / "data" / "site"


def main() -> None:
    ap = argparse.ArgumentParser(description="サイト配置")
    ap.add_argument("--dest", default=os.environ.get("DEPLOY_DEST", ""),
                    help="公開ディレクトリ(public_html)の絶対パス")
    args = ap.parse_args()
    if not args.dest:
        print("DEPLOY_DEST 未指定。data/site/ をそのまま配信するか、--dest を指定してください。")
        return
    dest = Path(args.dest)
    dest.mkdir(parents=True, exist_ok=True)
    # go.php / .htaccess も配置
    for src in (SITE_DIR, REPO_ROOT / "public"):
        for path in src.rglob("*"):
            if path.is_file():
                rel = path.relative_to(src)
                target = dest / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, target)
    print(f"deployed to {dest}")


if __name__ == "__main__":
    main()
