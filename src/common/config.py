"""設定(YAML)と環境変数(.env)の読み込み。

依存を増やさないため .env は自前の軽量パーサで読む（python-dotenv不要）。
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = REPO_ROOT / "config" / "config.yaml"
ENV_PATH = REPO_ROOT / ".env"


def _load_env_file(path: Path) -> None:
    """.env を環境変数へ流し込む（既存の環境変数は上書きしない）。"""
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


@lru_cache(maxsize=1)
def load_config(path: str | None = None) -> dict[str, Any]:
    """config.yaml を辞書で返す。"""
    p = Path(path) if path else CONFIG_PATH
    with p.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def env(key: str, default: str | None = None) -> str | None:
    """環境変数取得（初回呼び出し時に .env を読み込む）。"""
    _load_env_file(ENV_PATH)
    return os.environ.get(key, default)


def env_bool(key: str, default: bool = False) -> bool:
    val = env(key)
    if val is None:
        return default
    return val.lower() in ("1", "true", "yes", "on")
