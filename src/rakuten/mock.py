"""オフライン検証用のモッククライアント（鍵不要でend-to-end確認）。"""
from __future__ import annotations

from src.rakuten.client import Item

_SAMPLE = [
    Item("shopA:1001", "ワイヤレスイヤホン Bluetooth 高音質 ノイズキャンセリング",
         "https://item.rakuten.co.jp/shopA/1001/", "https://hb.afl.rakuten.co.jp/x/aaa",
         4980, "ShopA", "565004", 1280, 4.5, 4.0, 1.0, 0, 1,
         "https://example.com/img/1001.jpg", rank=1),
    Item("shopB:1002", "モバイルバッテリー 10000mAh 軽量 PD対応",
         "https://item.rakuten.co.jp/shopB/1002/", "https://hb.afl.rakuten.co.jp/x/bbb",
         2980, "ShopB", "565004", 860, 4.3, 3.0, 1.0, 0, 1,
         "https://example.com/img/1002.jpg", rank=2),
    Item("shopC:1003", "スマートウォッチ 大画面 血中酸素 防水",
         "https://item.rakuten.co.jp/shopC/1003/", "https://hb.afl.rakuten.co.jp/x/ccc",
         6480, "ShopC", "565004", 430, 4.1, 6.0, 1.0, 1, 1,
         "https://example.com/img/1003.jpg", rank=3),
    Item("shopD:2001", "電気ケトル 1.0L 温度調整 おしゃれ",
         "https://item.rakuten.co.jp/shopD/2001/", "https://hb.afl.rakuten.co.jp/x/ddd",
         3580, "ShopD", "558944", 220, 4.4, 4.0, 1.0, 0, 1,
         "https://example.com/img/2001.jpg", rank=1),
]


class MockRakutenClient:
    def __init__(self, *_, **__) -> None:
        self.app_id = "mock"
        self.affiliate_id = "mock"

    def search(self, keyword=None, genre_id=None, hits=30, sort="-reviewCount"):
        items = _SAMPLE
        if genre_id:
            items = [i for i in items if i.genre_id == genre_id]
        if keyword:
            items = [i for i in _SAMPLE if any(k in i.name for k in keyword.split())] or _SAMPLE
        return items[:hits]

    def ranking(self, genre_id=None, age=None, sex=None):
        items = [i for i in _SAMPLE if not genre_id or i.genre_id == genre_id]
        return items

    def genres(self, genre_id="0"):
        return [{"genre_id": "565004", "name": "家電", "level": 1},
                {"genre_id": "558944", "name": "キッチン家電", "level": 1}]
