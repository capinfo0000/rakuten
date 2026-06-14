"""価格/在庫/順位スナップショットと差分検知。

楽天API規約: 価格は24h以内に更新し、表示には取得日時＋免責文＋
「当サイトの観測値」を必ず添える（テンプレ側で担保）。
"""
from __future__ import annotations

from src.common.log import get_logger
from src.pdca.store import Store
from src.rakuten.client import Item

log = get_logger("tracker")

DISCLAIMER = (
    "※価格・在庫は変更される場合があります。購入時に楽天市場店舗に表示されている"
    "価格が適用されます。本ページの価格推移は当サイトの観測値です。"
)


def snapshot(store: Store, item: Item, drop_alert_pct: float = 5.0) -> dict | None:
    """1商品のスナップショットを記録し、差分イベントがあれば返す。"""
    prev_price = store.last_price(item.item_code)
    prev = store.get_product(item.item_code)

    store.add_price_point(item.item_code, item.price, item.availability, item.rank)

    event = None
    # 値下げ検知
    if prev_price and item.price and item.price < prev_price:
        drop_pct = (prev_price - item.price) / prev_price * 100
        if drop_pct >= drop_alert_pct:
            detail = f"{prev_price:,}円 → {item.price:,}円 ({drop_pct:.1f}%OFF)"
            store.add_event(item.item_code, "price_drop", detail)
            event = {"kind": "price_drop", "item": item, "detail": detail,
                     "drop_pct": drop_pct, "prev_price": prev_price}
            log.info("値下げ検知 %s %s", item.item_code, detail)
    # 在庫復活検知
    if prev and prev.get("availability") == 0 and item.availability == 1:
        store.add_event(item.item_code, "restock", "在庫復活")
        event = event or {"kind": "restock", "item": item, "detail": "在庫が復活しました"}
        log.info("在庫復活 %s", item.item_code)

    return event


def lowest_price(series: list[dict]) -> int | None:
    prices = [p["price"] for p in series if p.get("price")]
    return min(prices) if prices else None


def is_lowest_ever(series: list[dict]) -> bool:
    """直近系列で最新価格が最安値か（"底値"判定）。"""
    prices = [p["price"] for p in series if p.get("price")]
    if len(prices) < 2:
        return False
    return prices[-1] <= min(prices)
