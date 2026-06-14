#!/usr/bin/env python3
"""cron(週次): 楽天APIで市場リサーチ→穴場ニッチ/市場マップ更新。"""
import argparse

import _bootstrap  # noqa: F401

from src.common.config import load_config
from src.pdca.store import Store
from src.pipeline import build_client
from src.research.market import run_research


def main() -> None:
    ap = argparse.ArgumentParser(description="市場リサーチ")
    ap.add_argument("--mock", action="store_true")
    args = ap.parse_args()

    config = load_config()
    store = Store()
    client = build_client(mock=args.mock)
    best = run_research(client, store, config.get("niches", []),
                        config.get("research_weights", {}))
    print("穴場ニッチ上位:")
    for m in best[:5]:
        print(f"  {m['name']}({m['genre_id']}): 穴場スコア {m['niche_score']:.3f} "
              f"[需要{m['demand']:.2f} 競合{m['competition']:.2f} 料率{m['commission']:.2f}]")


if __name__ == "__main__":
    main()
