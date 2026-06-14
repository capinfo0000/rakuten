"""急上昇ワード → 楽天商品(アフィリンク)変換。

換金可能なトレンドだけ採用する: 検索で関連商品が取れたものに限る。
"""
from __future__ import annotations

from src.common.log import get_logger
from src.rakuten.client import Item, RakutenClient
from src.trends.radar import TrendHit

log = get_logger("trends.mapper")


def map_to_products(client: RakutenClient, hits: list[TrendHit],
                    per_term: int = 3, min_review: int = 5) -> list[tuple[TrendHit, list[Item]]]:
    """各トレンド語で商品検索し、(hit, items) を返す。商品0件の語は除外。"""
    results: list[tuple[TrendHit, list[Item]]] = []
    for hit in hits:
        items = client.search(keyword=hit.term, hits=per_term, sort="-reviewCount")
        items = [it for it in items if it.review_count >= min_review and it.price > 0]
        if items:
            results.append((hit, items[:per_term]))
        else:
            log.info("換金不可トレンドを除外: %s", hit.term)
    return results
