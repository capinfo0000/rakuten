"""見出し(FV)のA/Bテスト。

「ファーストビュー＝見出しが9割」に基づき、見出しの"型(テンプレート)"を
バンディットで選ぶ。各型のクリックアウトを reward として、勝ち型に寄せていく。
テキスト自体は毎回変わっても、型ごとに成績を貯めるので統計が効く。
"""
from __future__ import annotations

import random

from src.pdca.store import Store

# kind ごとの見出しテンプレート（{name} {pct} {price} を後で埋める）
TEMPLATES: dict[str, list[tuple[str, str]]] = {
    "price_drop": [
        ("pd_pct", "【{pct}%OFF】{name}"),
        ("pd_low", "【底値更新】{name}が過去最安"),
        ("pd_miss", "見逃し注意：{name}が値下げ中"),
        ("pd_price", "{name} がいま{price}円"),
    ],
    "restock": [
        ("rs_back", "【再入荷】{name}が在庫復活"),
        ("rs_now", "今すぐ確保：{name}が入荷"),
    ],
    "trend": [
        ("tr_now", "いま話題：{name}"),
        ("tr_rank", "急上昇ランクイン：{name}"),
        ("tr_check", "要チェック：{name}が急上昇"),
    ],
    "generic": [
        ("ge_price", "{name}の価格・在庫・買い時"),
        ("ge_watch", "{name} 価格ウォッチ"),
    ],
}


def variants(kind: str) -> list[tuple[str, str]]:
    return TEMPLATES.get(kind, TEMPLATES["generic"])


def pick(store: Store, kind: str, epsilon: float = 0.2) -> tuple[str, str]:
    """ε-greedyで見出しテンプレを選ぶ。(template_id, template_str) を返す。"""
    vs = variants(kind)
    arms = {a["template_id"]: a for a in store.headline_arms(kind)}

    # 探索: εの確率、または未試行の型があればそれを優先
    untried = [v for v in vs if v[0] not in arms or arms[v[0]]["pulls"] == 0]
    if untried and random.random() < max(epsilon, 0.34):
        return random.choice(untried)
    if random.random() < epsilon:
        return random.choice(vs)

    # 活用: reward/pull が最大の型（データが無ければ先頭）
    def rate(v: tuple[str, str]) -> float:
        a = arms.get(v[0])
        if not a or a["pulls"] == 0:
            return 0.0
        return a["reward"] / a["pulls"]

    return max(vs, key=rate)


def render(template: str, *, name: str, pct: float | None = None,
           price: int | None = None) -> str:
    """テンプレを埋めて見出し文字列にする。"""
    short = name if len(name) <= 26 else name[:25] + "…"
    return template.format(
        name=short,
        pct=f"{pct:.0f}" if pct is not None else "",
        price=f"{price:,}" if price is not None else "",
    )
