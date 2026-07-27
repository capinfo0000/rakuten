"""楽天セールイベント判定。

スーパーSALE/お買い物マラソン期は購入直前層が増えCVRが上がるため、
buy-now訴求ページの優先・X投稿頻度の引き上げに使う。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from src.common.config import load_config


@dataclass
class SaleStatus:
    is_super_sale: bool
    is_bargain_day: bool      # 5と0のつく日（ポイントUP）
    label: str

    @property
    def active(self) -> bool:
        return self.is_super_sale or self.is_bargain_day

    @property
    def boost(self) -> float:
        """セール連動スコアの係数(0〜1)。"""
        if self.is_super_sale:
            return 1.0
        if self.is_bargain_day:
            return 0.5
        return 0.0


def sale_status(today: date | None = None, config: dict | None = None) -> SaleStatus:
    today = today or date.today()
    cfg = (config or load_config()).get("sales_calendar", {})
    ss = cfg.get("super_sale", {})

    in_super = (
        today.month in ss.get("months", [])
        and ss.get("start_day", 4) <= today.day <= ss.get("end_day", 11)
    )
    is_bargain = today.day in cfg.get("bargain_days", [5, 10, 15, 20, 25, 30])

    if in_super:
        label = "楽天スーパーSALE開催中"
    elif is_bargain:
        label = "ポイントアップ（5と0のつく日）"
    else:
        label = "通常期"
    return SaleStatus(is_super_sale=in_super, is_bargain_day=is_bargain, label=label)
