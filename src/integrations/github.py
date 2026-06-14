"""GitHub REST API で KPIゲート未達/ジョブ失敗を Issue 化（任意・フェイルソフト）。

GITHUB_TOKEN / GITHUB_REPO(owner/repo) 未設定なら何もしない。
"""
from __future__ import annotations

import requests

from src.common.config import env
from src.common.log import get_logger

log = get_logger("integrations.github")


def create_issue(title: str, body: str, labels: list[str] | None = None) -> bool:
    token = env("GITHUB_TOKEN")
    repo = env("GITHUB_REPO")
    if not (token and repo):
        return False
    url = f"https://api.github.com/repos/{repo}/issues"
    headers = {"Authorization": f"Bearer {token}",
               "Accept": "application/vnd.github+json"}
    payload = {"title": title, "body": body, "labels": labels or ["auto"]}
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=15)
        ok = r.status_code < 300
        if not ok:
            log.warning("Issue作成失敗: %s %s", r.status_code, r.text[:200])
        return ok
    except requests.RequestException as exc:
        log.warning("Issue作成スキップ: %s", exc)
        return False
