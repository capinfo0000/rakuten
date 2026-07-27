"""シンプルなロギング。data/logs/ にも残す。"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

from src.common.config import REPO_ROOT

_LOG_DIR = REPO_ROOT / "data" / "logs"


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")

    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    logger.addHandler(sh)

    try:
        _LOG_DIR.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(_LOG_DIR / "app.log", encoding="utf-8")
        fh.setFormatter(fmt)
        logger.addHandler(fh)
    except OSError:
        # ログファイルが作れなくても標準出力には出す（全自動を止めない）
        pass
    return logger
