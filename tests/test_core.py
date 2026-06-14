"""コアロジックのユニットテスト。"""
from datetime import date

from src.affiliate.links import affiliate_link, is_allowed_url
from src.eventcal.events import sale_status
from src.rakuten.client import Item
from src.rakuten.mock import MockRakutenClient
from src.rakuten.selector import rank_items, score_item


def _item(**kw) -> Item:
    base = dict(item_code="x:1", name="テスト商品", url="https://item.rakuten.co.jp/x/1/",
                affiliate_url="https://hb.afl.rakuten.co.jp/x/z", price=1000, shop_name="S",
                genre_id="1", review_count=100, review_average=4.5, affiliate_rate=4.0,
                point_rate=1.0, postage_flag=0, availability=1, image_url="", rank=1)
    base.update(kw)
    return Item(**base)


def test_sale_status_super_sale():
    s = sale_status(today=date(2026, 6, 5))  # 6月スーパーSALE期間
    assert s.is_super_sale and s.boost == 1.0


def test_sale_status_bargain_day():
    s = sale_status(today=date(2026, 7, 10))  # 10日=5と0の日
    assert s.is_bargain_day and not s.is_super_sale


def test_sale_status_normal():
    s = sale_status(today=date(2026, 7, 3))
    assert not s.active and s.label == "通常期"


def test_score_higher_for_higher_rate():
    sale = sale_status(today=date(2026, 7, 3))
    w = {"affiliate_rate": 0.35, "demand": 0.30, "review_trust": 0.20, "sale_boost": 0.15}
    low = score_item(_item(affiliate_rate=1.0), w, sale)
    high = score_item(_item(affiliate_rate=8.0), w, sale)
    assert high > low


def test_rank_items_orders_desc():
    sale = sale_status(today=date(2026, 7, 3))
    w = {"affiliate_rate": 0.35, "demand": 0.30, "review_trust": 0.20, "sale_boost": 0.15}
    items = [_item(item_code="a", affiliate_rate=1.0, review_count=5),
             _item(item_code="b", affiliate_rate=8.0, review_count=1000)]
    ranked = rank_items(items, w, sale)
    assert ranked[0][0].item_code == "b"
    assert ranked[0][1] >= ranked[1][1]


def test_affiliate_link_rakuten_direct(monkeypatch):
    monkeypatch.setenv("AFFILIATE_PROVIDER", "rakuten_direct")
    link = affiliate_link(rakuten_url="https://item.rakuten.co.jp/x/1/",
                          affiliate_url="https://hb.afl.rakuten.co.jp/x/z")
    assert link == "https://hb.afl.rakuten.co.jp/x/z"


def test_affiliate_link_moshimo(monkeypatch):
    monkeypatch.setenv("AFFILIATE_PROVIDER", "moshimo")
    monkeypatch.setenv("MOSHIMO_A_ID", "111")
    monkeypatch.setenv("MOSHIMO_RAKUTEN_P_ID", "222")
    monkeypatch.setenv("MOSHIMO_RAKUTEN_PC_ID", "333")
    monkeypatch.setenv("MOSHIMO_RAKUTEN_PL_ID", "444")
    link = affiliate_link(rakuten_url="https://item.rakuten.co.jp/x/1/", merchant="rakuten")
    assert "af.moshimo.com" in link and "a_id=111" in link and "url=" in link


def test_is_allowed_url():
    assert is_allowed_url("https://item.rakuten.co.jp/x/1/")
    assert is_allowed_url("https://af.moshimo.com/af/c/click?x=1")
    assert not is_allowed_url("https://evil.example.com/phish")


def test_mock_client_search():
    c = MockRakutenClient()
    assert c.search(keyword="イヤホン")
    assert c.ranking(genre_id="565004")
