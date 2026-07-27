"""かんたんリンク型 3社比較ボックスのデータ生成。

もしも経由で Amazon/楽天/Yahoo! のリンクを並べ取りこぼしを回収。
楽天は商品URL確定、Amazon/Yahoo!は検索URLで対応（PA-API無しでも成立）。
実リンクは links provider 経由で go.php に載せる。
"""
from __future__ import annotations

from urllib.parse import quote

from src.affiliate.links import affiliate_link
from src.rakuten.client import Item

AMAZON_SEARCH = "https://www.amazon.co.jp/s?k={q}"
YAHOO_SEARCH = "https://shopping.yahoo.co.jp/search?p={q}"


def compare_box(item: Item) -> list[dict]:
    """[{merchant, label, url}] を返す。url は provider 適用後の最終リンク。"""
    q = quote(item.name)
    rows = [
        {
            "merchant": "rakuten",
            "label": "楽天市場で見る",
            "url": affiliate_link(rakuten_url=item.url, affiliate_url=item.affiliate_url,
                                  merchant="rakuten"),
        },
        {
            "merchant": "amazon",
            "label": "Amazonで探す",
            "url": affiliate_link(rakuten_url=AMAZON_SEARCH.format(q=q),
                                  merchant="amazon"),
        },
        {
            "merchant": "yahoo",
            "label": "Yahoo!で探す",
            "url": affiliate_link(rakuten_url=YAHOO_SEARCH.format(q=q),
                                  merchant="yahoo"),
        },
    ]
    return rows
