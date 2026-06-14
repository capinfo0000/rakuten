"""SQLite の日次バックアップ。"""
from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path

from src.common.config import REPO_ROOT
from src.common.log import get_logger
from src.pdca.store import DB_PATH

log = get_logger("ops.backup")

BACKUP_DIR = REPO_ROOT / "data" / "backups"


def backup_db(keep: int = 7) -> Path | None:
    if not DB_PATH.exists():
        log.info("DB未作成のためバックアップなし")
        return None
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    dest = BACKUP_DIR / f"app-{stamp}.db"
    shutil.copy2(DB_PATH, dest)

    # 世代管理: 古いものを削除
    backups = sorted(BACKUP_DIR.glob("app-*.db"))
    for old in backups[:-keep]:
        old.unlink(missing_ok=True)
    log.info("バックアップ作成 %s", dest.name)
    return dest
