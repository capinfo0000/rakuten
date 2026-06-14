"""戦略の自動調整（PDCAの"Act"）。

ε-greedy で次サイクルに注力するジャンル(arm)を選ぶ:
  確率εで探索（穴場ニッチ/未試行）、1-εで活用（reward上位）。
人手で止めず「題材を自動ローテーション」する中核。
"""
from __future__ import annotations

import random

from src.common.log import get_logger
from src.pdca.store import Store

log = get_logger("pdca.optimizer")


def select_focus_genres(store: Store, epsilon: float = 0.2, k: int = 3) -> list[str]:
    """次に注力するジャンルIDを返す（活用＋探索）。"""
    with store.conn() as con:
        arms = [dict(r) for r in con.execute(
            "SELECT name, reward, pulls FROM arms WHERE kind='genre'").fetchall()]

    exploit = sorted(arms, key=lambda a: a["reward"], reverse=True)
    chosen: list[str] = []

    # 活用: reward上位
    for a in exploit:
        if len(chosen) >= k:
            break
        if random.random() > epsilon:
            chosen.append(a["name"])

    # 探索: 穴場ニッチ（market_map）や未試行armから補充
    explore_pool = [n["genre_id"] for n in store.best_niches(limit=10)]
    random.shuffle(explore_pool)
    for gid in explore_pool:
        if len(chosen) >= k:
            break
        if gid not in chosen:
            chosen.append(gid)

    # それでも足りなければ reward順で埋める
    for a in exploit:
        if len(chosen) >= k:
            break
        if a["name"] not in chosen:
            chosen.append(a["name"])

    log.info("注力ジャンル選定(ε=%.2f): %s", epsilon, chosen)
    return chosen[:k]
