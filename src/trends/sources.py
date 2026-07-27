"""トレンドのデータ源（多重化・全フェイルソフト・ブラウザ不要）。

- rakuten_rising : 楽天ランキング上位＝購買需要そのもの（公式API・最重要）
- google_trends  : pytrends（2025/4アーカイブ＝不安定なので補助）
- yahoo_realtime : Yahoo!リアルタイム検索のHTTP取得（取れなければ[]）
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from src.common.http import ThrottledClient
from src.common.log import get_logger
from src.rakuten.client import Item, RakutenClient

log = get_logger("trends.sources")


@dataclass
class RawSignal:
    term: str
    source: str
    weight: float          # 0〜1 の生の強さ
    item: Item | None = None


def rakuten_rising(client: RakutenClient, genre_ids: list[str],
                   top_n: int = 10) -> list[RawSignal]:
    """ジャンル別ランキング上位を購買トレンドとして拾う。"""
    signals: list[RawSignal] = []
    for gid in genre_ids:
        for it in client.ranking(genre_id=gid)[:top_n]:
            rank = it.rank or top_n
            weight = max(0.1, 1.0 - (rank - 1) / top_n)
            signals.append(RawSignal(term=_main_keyword(it.name), source="rakuten",
                                     weight=weight, item=it))
    return signals


def google_trends(keywords: list[str]) -> list[RawSignal]:
    """pytrends。import/通信失敗は握りつぶして[]（全自動を止めない）。"""
    if not keywords:
        return []
    try:
        from pytrends.request import TrendReq  # type: ignore

        pytrends = TrendReq(hl="ja-JP", tz=540)
        pytrends.build_payload(keywords[:5], timeframe="now 7-d", geo="JP")
        df = pytrends.interest_over_time()
        out: list[RawSignal] = []
        for kw in keywords[:5]:
            if kw in df:
                series = df[kw].tolist()
                if len(series) >= 2 and max(series) > 0:
                    spike = (series[-1] - (sum(series) / len(series))) / (max(series) or 1)
                    out.append(RawSignal(term=kw, source="google",
                                         weight=max(0.0, min(1.0, spike + 0.5))))
        return out
    except Exception as exc:  # noqa: BLE001 — フェイルソフト
        log.warning("Googleトレンド取得スキップ: %s", exc)
        return []


def yahoo_realtime(http: ThrottledClient | None = None) -> list[RawSignal]:
    """Yahoo!リアルタイム検索の急上昇ワードをHTTPで best-effort 取得。"""
    http = http or ThrottledClient(min_interval=2.0)
    html = http.get_text("https://search.yahoo.co.jp/realtime")
    if not html:
        return []
    try:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "lxml")
        terms: list[str] = []
        for a in soup.select("a"):
            txt = (a.get_text() or "").strip()
            if txt and 1 < len(txt) <= 20 and not re.search(r"https?://", txt):
                terms.append(txt)
        # 上位ユニークのみ
        seen: list[str] = []
        for t in terms:
            if t not in seen:
                seen.append(t)
            if len(seen) >= 10:
                break
        return [RawSignal(term=t, source="yahoo", weight=0.4) for t in seen]
    except Exception as exc:  # noqa: BLE001
        log.warning("Yahoo!リアルタイム取得スキップ: %s", exc)
        return []


def _main_keyword(name: str) -> str:
    """商品名から主要キーワードを粗く抽出（記号・容量等を削る）。"""
    name = re.sub(r"[【】\[\]（）()『』「」/|,，.。]", " ", name)
    tokens = [t for t in name.split() if len(t) >= 2][:2]
    return " ".join(tokens) if tokens else name[:20]
