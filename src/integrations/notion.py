"""Notion REST API へ KPI/リサーチ/トレンドを push（任意・フェイルソフト）。

NOTION_API_KEY / NOTION_DASHBOARD_DB 未設定なら何もしない。
"""
from __future__ import annotations

import requests

from src.common.config import env
from src.common.log import get_logger

log = get_logger("integrations.notion")

API = "https://api.notion.com/v1/pages"
VERSION = "2022-06-28"


def push_kpis(kpis: dict) -> bool:
    key = env("NOTION_API_KEY")
    db = env("NOTION_DASHBOARD_DB")
    if not (key and db):
        return False
    headers = {
        "Authorization": f"Bearer {key}",
        "Notion-Version": VERSION,
        "Content-Type": "application/json",
    }
    payload = {
        "parent": {"database_id": db},
        "properties": {
            "Name": {"title": [{"text": {"content": "PDCA KPI"}}]},
            "Pages": {"number": kpis.get("pages", 0)},
            "Clickouts": {"number": kpis.get("clickouts_total", 0)},
            "GSC impressions": {"number": kpis.get("gsc_impressions", 0)},
        },
    }
    try:
        r = requests.post(API, headers=headers, json=payload, timeout=15)
        ok = r.status_code < 300
        if not ok:
            log.warning("Notion push 失敗: %s %s", r.status_code, r.text[:200])
        return ok
    except requests.RequestException as exc:
        log.warning("Notion push スキップ: %s", exc)
        return False
