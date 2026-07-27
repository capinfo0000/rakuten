"""売れやすさスコアで商品を選定。

スコア = w1·料率 + w2·需要 + w3·レビュー信頼 + w4·セール連動
各因子は 0〜1 に正規化してから重み付け。
"""
from __future__ import annotations

import math

from src.eventcal.events import SaleStatus
from src.rakuten.client import Item


def _norm(value: float, scale: float) -> float:
    """0〜1へ。scaleで頭打ち。"""
    if scale <= 0:
        return 0.0
    return max(0.0, min(1.0, value / scale))


def score_item(item: Item, weights: dict[str, float], sale: SaleStatus,
               trend_boost: float = 0.0) -> float:
    """1商品の売れやすさスコア(0〜1目安)。trend_boost は radar 由来(0〜1)。"""
    rate = _norm(item.affiliate_rate, 10.0)             # 10%で頭打ち
    # 需要: レビュー件数(対数)＋ランキング上位＋トレンド
    review_demand = _norm(math.log10(item.review_count + 1), 3.0)  # ~1000件で1.0
    rank_demand = 0.0
    if item.rank:
        rank_demand = max(0.0, 1.0 - (item.rank - 1) / 30.0)
    demand = min(1.0, 0.5 * review_demand + 0.3 * rank_demand + 0.2 * trend_boost)
    # レビュー信頼: 平均(5点満点)×件数の確からしさ
    review_trust = _norm(item.review_average, 5.0) * _norm(item.review_count, 50.0)
    sale_boost = sale.boost

    return (
        weights.get("affiliate_rate", 0.35) * rate
        + weights.get("demand", 0.30) * demand
        + weights.get("review_trust", 0.20) * review_trust
        + weights.get("sale_boost", 0.15) * sale_boost
    )


def rank_items(items: list[Item], weights: dict[str, float], sale: SaleStatus,
               trend_terms: set[str] | None = None) -> list[tuple[Item, float]]:
    """スコア降順に (item, score) を返す。"""
    trend_terms = trend_terms or set()
    scored: list[tuple[Item, float]] = []
    for it in items:
        boost = 1.0 if any(t in it.name for t in trend_terms) else 0.0
        scored.append((it, score_item(it, weights, sale, boost)))
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored
