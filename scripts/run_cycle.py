#!/usr/bin/env python3
"""cron: Plan+Do（収集→価格記録→生成→公開→X投稿）。"""
import argparse

import _bootstrap  # noqa: F401

from src.common.config import load_config
from src.pdca.store import Store
from src.pipeline import build_client, run_cycle


def main() -> None:
    ap = argparse.ArgumentParser(description="1サイクル実行")
    ap.add_argument("--mock", action="store_true", help="モックAPIで実行（鍵不要）")
    ap.add_argument("--dry-run", action="store_true", help="X投稿は記録のみ")
    args = ap.parse_args()

    config = load_config()
    store = Store()
    client = build_client(mock=args.mock)
    result = run_cycle(client, store, config, dry_run=args.dry_run)
    print(f"done: {result}")


if __name__ == "__main__":
    main()
