"""下書きフィードバックのメタ学習ハーネス。

「下書き→あなたの意見→修正→学習」を回す中核。
意見(採用/却下/評価/編集方針)を蓄積し、次回以降の生成に反映する:
- 切り口(angle)の好みを angle_prefs に加点/減点 → 生成の切り口選択を偏らせる
- 「短く」「バカバカしく」等の恒常的な編集方針を style_directives に蓄積 → 全プロンプトに注入
"""
from __future__ import annotations

import random

from src.content.xdraft import Angle
from src.pdca.store import Store

# 評価→angleスコアへの寄与（採用は強い加点、却下は減点）
VERDICT_DELTA = {"keep": 1.0, "post": 1.0, "revise": 0.2, "reject": -1.0, "skip": 0.0}


def record(store: Store, draft_id: int, angle: str, verdict: str,
           rating: int | None = None, directive: str | None = None) -> None:
    """1件のフィードバックを記録し、メタ学習へ反映する。

    - verdict: keep|post|revise|reject|skip
    - rating:  任意の5段階等（angleスコアに加味）
    - directive: 恒常化したい編集方針（例「もっと短く」）。あれば style_directives に蓄積
    """
    verdict = (verdict or "skip").lower()
    store.set_draft_feedback(draft_id, verdict, feedback=directive, rating=rating)

    delta = VERDICT_DELTA.get(verdict, 0.0)
    if rating is not None:
        delta += (rating - 3) * 0.3  # 3を中立に±
    if delta:
        store.bump_angle_pref(angle, delta)

    if directive and verdict != "reject":
        store.add_style_directive(directive)


def learned_directives(store: Store, limit: int = 5) -> list[str]:
    """全生成プロンプトに注入する恒常方針。"""
    return store.top_style_directives(limit)


def order_angles(store: Store, angles: list[Angle], epsilon: float = 0.25) -> list[Angle]:
    """学習した好みで切り口を並べ替え（ε-greedyで探索も残す）。"""
    if random.random() < epsilon:
        shuffled = list(angles)
        random.shuffle(shuffled)
        return shuffled
    scores = store.angle_pref_scores()
    return sorted(angles, key=lambda a: scores.get(a.id, 0.0), reverse=True)
