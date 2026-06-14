"""監視・アラート。失敗時のみ通知（成功時は無通知）。"""
from __future__ import annotations

import json

import requests

from src.common.config import env
from src.common.log import get_logger

log = get_logger("ops.monitor")


def alert(message: str) -> None:
    """ALERT_WEBHOOK_URL があればPOST（Discord/Slack/汎用）。無ければログのみ。"""
    url = env("ALERT_WEBHOOK_URL")
    log.error("ALERT: %s", message)
    if not url:
        return
    try:
        requests.post(url, data=json.dumps({"content": message, "text": message}),
                      headers={"Content-Type": "application/json"}, timeout=10)
    except requests.RequestException as exc:
        log.warning("通知送信失敗: %s", exc)


def guard(name: str):
    """ジョブを包んで失敗時に通知するデコレータ。"""
    def deco(fn):
        def wrapper(*args, **kwargs):
            try:
                return fn(*args, **kwargs)
            except Exception as exc:  # noqa: BLE001
                alert(f"[{name}] 失敗: {exc}")
                raise
        return wrapper
    return deco
