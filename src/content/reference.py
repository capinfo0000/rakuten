"""「伸びている投稿」を参考にする仕組み。

1) 外部バズ参照: Yahoo!リアルタイム検索から、話題の言い回し/文脈を取得（無料・ベストエフォート）。
   他人の正確なインプ取得は有料APIのため行わない。取れなければ空文字（フェイルソフト）。
2) 自分の勝ち投稿: 採用/高評価/高インプの過去ドラフトを手本として返す（store側 exemplar_drafts）。

いずれも生成プロンプトに"お手本/文脈"として注入し、伸びる型を踏襲する。
"""
from __future__ import annotations

import re

from src.common.http import ThrottledClient
from src.common.log import get_logger

log = get_logger("content.reference")


def buzz_context(topic: str, http: ThrottledClient | None = None, max_len: int = 280) -> str:
    """トピックについて今バズっている文脈をHTTPで best-effort 取得。失敗時は空。"""
    if not topic:
        return ""
    http = http or ThrottledClient(min_interval=2.0)
    url = "https://search.yahoo.co.jp/realtime/search"
    html = http.get_text(url, params={"p": topic})
    if not html:
        log.info("バズ参照: 取得不可のためスキップ")
        return ""
    try:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "lxml")
        texts: list[str] = []
        for tag in soup.find_all(["p", "span", "div"]):
            t = (tag.get_text() or "").strip()
            if 8 <= len(t) <= 120 and topic[:4] in t and not re.search(r"https?://", t):
                if t not in texts:
                    texts.append(t)
            if len(texts) >= 5:
                break
        return " / ".join(texts)[:max_len]
    except Exception as exc:  # noqa: BLE001
        log.warning("バズ参照パース失敗: %s", exc)
        return ""
