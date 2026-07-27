"""楽天APIで市場リサーチ＝穴場ニッチの自動発見。

ジャンル別に Ranking/Item Search を集計し:
  需要(レビュー数・流通) × 競合(寡占度) × 報酬(料率) × 価格帯
を算出。niche_score = w_d·需要 + w_c·競合(負) + w_m·料率 を market_map に保存。
"""
from __future__ import annotations

import math
import statistics

from src.common.log import get_logger
from src.pdca.store import Store
from src.rakuten.client import RakutenClient

log = get_logger("research")


def _normalize(value: float, scale: float) -> float:
    if scale <= 0:
        return 0.0
    return max(0.0, min(1.0, value / scale))


def analyze_genre(client: RakutenClient, genre_id: str, name: str = "") -> dict:
    """1ジャンルの需要/競合/報酬指標を算出。"""
    items = client.ranking(genre_id=genre_id)
    if not items:
        items = client.search(genre_id=genre_id, hits=30, sort="-reviewCount")
    if not items:
        return {}

    review_counts = [it.review_count for it in items]
    rates = [it.affiliate_rate for it in items if it.affiliate_rate > 0]
    prices = [it.price for it in items if it.price > 0]
    shops = {it.shop_name for it in items if it.shop_name}

    demand = _normalize(math.log10((sum(review_counts) / len(review_counts)) + 1), 3.0)
    # 競合(寡占度): ショップ多様性が低い=寡占=競合強い とみなす
    diversity = len(shops) / max(1, len(items))
    competition = 1.0 - diversity                       # 0(分散)〜1(寡占)
    commission = _normalize(statistics.mean(rates) if rates else 0.0, 8.0)
    median_price = statistics.median(prices) if prices else 0

    return {
        "genre_id": genre_id,
        "name": name,
        "demand": round(demand, 4),
        "competition": round(competition, 4),
        "commission": round(commission, 4),
        "median_price": median_price,
    }


def niche_score(metrics: dict, weights: dict[str, float]) -> float:
    return (
        weights.get("demand", 0.40) * metrics.get("demand", 0)
        + weights.get("competition", -0.35) * metrics.get("competition", 0)
        + weights.get("commission", 0.25) * metrics.get("commission", 0)
    )


def run_research(client: RakutenClient, store: Store, niches: list[dict],
                 weights: dict[str, float]) -> list[dict]:
    """設定ニッチ＋子ジャンルを分析し market_map を更新。穴場上位を返す。"""
    analyzed: list[dict] = []
    for niche in niches:
        gid = niche.get("genre_id")
        if not gid:
            continue
        m = analyze_genre(client, gid, niche.get("name", ""))
        if not m:
            continue
        score = round(niche_score(m, weights), 4)
        store.upsert_market(m["genre_id"], m["name"], m["demand"],
                            m["competition"], m["commission"], score)
        m["niche_score"] = score
        analyzed.append(m)
        log.info("ジャンル分析 %s(%s): 需要%.2f 競合%.2f 料率%.2f → 穴場%.3f",
                 m["name"], gid, m["demand"], m["competition"], m["commission"], score)

    analyzed.sort(key=lambda x: x["niche_score"], reverse=True)
    return analyzed
