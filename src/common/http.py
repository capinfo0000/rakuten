"""スロットル付きHTTPクライアント（楽天API 1req/s 順守・指数バックオフ）。

ブラウザは使わず requests のみ。最安共有サーバでも動く。
"""
from __future__ import annotations

import time
from typing import Any

import requests

from src.common.log import get_logger

log = get_logger("http")


class ThrottledClient:
    """最低リクエスト間隔を保証し、失敗時に指数バックオフで再試行する。"""

    def __init__(
        self,
        min_interval: float = 1.0,
        max_retries: int = 4,
        timeout: float = 15.0,
        user_agent: str = "TrendPriceWatch/1.0 (+https://example.com)",
    ) -> None:
        self.min_interval = min_interval
        self.max_retries = max_retries
        self.timeout = timeout
        self._last_call = 0.0
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": user_agent})

    def _wait(self) -> None:
        elapsed = time.monotonic() - self._last_call
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)

    def get_json(self, url: str, params: dict[str, Any] | None = None) -> dict[str, Any] | None:
        """JSONを取得。全リトライ失敗時は None（呼び出し側でフェイルソフト）。"""
        for attempt in range(self.max_retries):
            self._wait()
            try:
                resp = self._session.get(url, params=params, timeout=self.timeout)
                self._last_call = time.monotonic()
                if resp.status_code == 429 or resp.status_code >= 500:
                    raise requests.HTTPError(f"status {resp.status_code}")
                resp.raise_for_status()
                return resp.json()
            except (requests.RequestException, ValueError) as exc:
                self._last_call = time.monotonic()
                backoff = 2 ** attempt
                log.warning("GET失敗(%s/%s) %s: %s — %ss後に再試行",
                            attempt + 1, self.max_retries, url, exc, backoff)
                if attempt + 1 < self.max_retries:
                    time.sleep(backoff)
        log.error("GET最終失敗: %s", url)
        return None

    def get_text(self, url: str, params: dict[str, Any] | None = None) -> str | None:
        """HTML等のテキストを取得（非公式ソース用・フェイルソフト）。"""
        self._wait()
        try:
            resp = self._session.get(url, params=params, timeout=self.timeout)
            self._last_call = time.monotonic()
            resp.raise_for_status()
            return resp.text
        except requests.RequestException as exc:
            self._last_call = time.monotonic()
            log.warning("GET(text)失敗 %s: %s", url, exc)
            return None
