#!/usr/bin/env python3
"""cron(高頻度): トレンド検知→速報ページ/X投稿を即応。"""
import argparse

import _bootstrap  # noqa: F401

from src.common.config import load_config
from src.pdca.store import Store
from src.pipeline import build_client, run_trend_sweep


def main() -> None:
    ap = argparse.ArgumentParser(description="トレンドスイープ")
    ap.add_argument("--mock", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    store = Store()
    client = build_client(mock=args.mock)
    result = run_trend_sweep(client, store, load_config(), dry_run=args.dry_run)
    print(f"done: {result}")


if __name__ == "__main__":
    main()
