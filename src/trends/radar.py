"""トレンド集約・スパイク検知・優先度付け。

複数ソースの RawSignal を term 単位で集約し、楽天(購買需要)を重く評価。
上位を採用して store に記録し、Planステージへ高優先アームとして渡す。
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from src.common.log import get_logger
from src.pdca.store import Store
from src.trends.sources import RawSignal

log = get_logger("trends.radar")

# ソース別の信頼度（楽天=購買直結で最重要）
SOURCE_WEIGHT = {"rakuten": 1.0, "google": 0.6, "yahoo": 0.4}


@dataclass
class TrendHit:
    term: str
    score: float
    sources: list[str]


def aggregate(signals: list[RawSignal], max_items: int = 10) -> list[TrendHit]:
    bucket: dict[str, list[RawSignal]] = defaultdict(list)
    for s in signals:
        bucket[s.term].append(s)

    hits: list[TrendHit] = []
    for term, sigs in bucket.items():
        score = sum(s.weight * SOURCE_WEIGHT.get(s.source, 0.3) for s in sigs)
        srcs = sorted({s.source for s in sigs})
        # 複数ソースで言及された語はブースト
        if len(srcs) > 1:
            score *= 1.3
        hits.append(TrendHit(term=term, score=round(score, 4), sources=srcs))

    hits.sort(key=lambda h: h.score, reverse=True)
    return hits[:max_items]


def detect(store: Store, signals: list[RawSignal], max_items: int = 10) -> list[TrendHit]:
    """集約→記録して返す。"""
    hits = aggregate(signals, max_items=max_items)
    for h in hits:
        store.add_trend(h.term, "+".join(h.sources), h.score)
    log.info("トレンド検知 %s件: %s", len(hits), [h.term for h in hits[:5]])
    return hits
