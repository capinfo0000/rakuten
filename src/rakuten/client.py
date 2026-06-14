"""楽天ウェブサービス APIクライアント。

- Ichiba Item Search API (2026-04-01)
- Ichiba Item Ranking API (2022-06-01)
- Ichiba Genre Search API (2014-02-22)

affiliateId を渡すとレスポンスにアフィリエイトURLが含まれる。
全リクエストは ThrottledClient 経由で 1req/s を順守。
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Iterable

from src.common.http import ThrottledClient
from src.common.log import get_logger

log = get_logger("rakuten")

SEARCH_URL = "https://app.rakuten.co.jp/services/api/IchibaItem/Search/20220601"
RANKING_URL = "https://app.rakuten.co.jp/services/api/IchibaItem/Ranking/20220601"
GENRE_URL = "https://app.rakuten.co.jp/services/api/IchibaItem/GenreSearch/20120723"


@dataclass
class Item:
    """正規化した商品データ（DB保存・スコアリングの素）。"""

    item_code: str
    name: str
    url: str
    affiliate_url: str
    price: int
    shop_name: str
    genre_id: str
    review_count: int
    review_average: float
    affiliate_rate: float       # 料率(%)。取れない場合0
    point_rate: float           # ポイント倍率
    postage_flag: int           # 0=送料込/別記載, 1=送料別
    availability: int           # 1=在庫あり
    image_url: str
    rank: int | None = None     # ランキング由来のとき順位

    def to_row(self) -> dict[str, Any]:
        return asdict(self)


def _parse_item(node: dict[str, Any]) -> Item | None:
    """APIの item ノードを Item へ正規化。"""
    it = node.get("Item", node)
    code = it.get("itemCode")
    if not code:
        return None
    images = it.get("mediumImageUrls") or it.get("smallImageUrls") or []
    image_url = ""
    if images:
        first = images[0]
        image_url = first.get("imageUrl", "") if isinstance(first, dict) else str(first)
    return Item(
        item_code=code,
        name=it.get("itemName", ""),
        url=it.get("itemUrl", ""),
        affiliate_url=it.get("affiliateUrl") or it.get("itemUrl", ""),
        price=int(it.get("itemPrice", 0) or 0),
        shop_name=it.get("shopName", ""),
        genre_id=str(it.get("genreId", "")),
        review_count=int(it.get("reviewCount", 0) or 0),
        review_average=float(it.get("reviewAverage", 0) or 0),
        affiliate_rate=float(it.get("affiliateRate", 0) or 0),
        point_rate=float(it.get("pointRate", 1) or 1),
        postage_flag=int(it.get("postageFlag", 0) or 0),
        availability=int(it.get("availability", 1) or 0),
        image_url=image_url,
        rank=it.get("rank"),
    )


class RakutenClient:
    def __init__(self, app_id: str, affiliate_id: str | None = None,
                 http: ThrottledClient | None = None) -> None:
        if not app_id:
            raise ValueError("RAKUTEN_APP_ID が未設定です")
        self.app_id = app_id
        self.affiliate_id = affiliate_id
        self.http = http or ThrottledClient(min_interval=1.0)

    def _base_params(self) -> dict[str, Any]:
        params = {"applicationId": self.app_id, "format": "json"}
        if self.affiliate_id:
            params["affiliateId"] = self.affiliate_id
        return params

    def search(self, keyword: str | None = None, genre_id: str | None = None,
               hits: int = 30, sort: str = "-reviewCount") -> list[Item]:
        """商品検索。keyword か genre_id のいずれか必須。"""
        params = self._base_params()
        params.update({"hits": min(hits, 30), "sort": sort})
        if keyword:
            params["keyword"] = keyword
        if genre_id:
            params["genreId"] = genre_id
        data = self.http.get_json(SEARCH_URL, params)
        if not data:
            return []
        return [it for it in (_parse_item(n) for n in data.get("Items", [])) if it]

    def ranking(self, genre_id: str | None = None, age: str | None = None,
                sex: str | None = None) -> list[Item]:
        """ジャンル別ランキング（トレンド/需要シグナル）。"""
        params = self._base_params()
        if genre_id:
            params["genreId"] = genre_id
        if age:
            params["age"] = age
        if sex:
            params["sex"] = sex
        data = self.http.get_json(RANKING_URL, params)
        if not data:
            return []
        return [it for it in (_parse_item(n) for n in data.get("Items", [])) if it]

    def genres(self, genre_id: str = "0") -> list[dict[str, Any]]:
        """ジャンルツリー（市場リサーチ用）。genre_id=0 でルート直下。"""
        params = {"applicationId": self.app_id, "format": "json", "genreId": genre_id}
        data = self.http.get_json(GENRE_URL, params)
        if not data:
            return []
        children = data.get("children", [])
        out: list[dict[str, Any]] = []
        for c in children:
            node = c.get("child", c)
            out.append({
                "genre_id": str(node.get("genreId", "")),
                "name": node.get("genreName", ""),
                "level": node.get("genreLevel", 0),
            })
        return out


def items_to_rows(items: Iterable[Item]) -> list[dict[str, Any]]:
    return [it.to_row() for it in items]
