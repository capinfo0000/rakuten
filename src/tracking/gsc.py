"""Google Search Console API（公式・無料）。

クエリ別 表示/クリック/CTR/平均掲載順位を取得して store に保存。
鍵未設定・失敗時は [] を返す（フェイルソフト）。
"""
from __future__ import annotations

from datetime import date, timedelta

from src.common.config import REPO_ROOT, env
from src.common.log import get_logger
from src.pdca.store import Store

log = get_logger("tracking.gsc")


def _service():
    site = env("GSC_SITE_URL")
    sa_path = env("GOOGLE_SERVICE_ACCOUNT_JSON", "secrets/service_account.json")
    if not site:
        return None, None
    key_path = (REPO_ROOT / sa_path) if sa_path else None
    if not key_path or not key_path.exists():
        log.info("GSC: サービスアカウント鍵が無いためスキップ")
        return None, None
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        creds = service_account.Credentials.from_service_account_file(
            str(key_path), scopes=["https://www.googleapis.com/auth/webmasters.readonly"])
        return build("searchconsole", "v1", credentials=creds), site
    except Exception as exc:  # noqa: BLE001
        log.warning("GSC初期化スキップ: %s", exc)
        return None, None


def fetch(store: Store, days: int = 3) -> list[dict]:
    """直近days日のクエリ別指標を取得・保存。"""
    service, site = _service()
    if not service:
        return []
    end = date.today()
    start = end - timedelta(days=days)
    try:
        resp = service.searchanalytics().query(siteUrl=site, body={
            "startDate": start.isoformat(), "endDate": end.isoformat(),
            "dimensions": ["query", "page"], "rowLimit": 500,
        }).execute()
    except Exception as exc:  # noqa: BLE001
        log.warning("GSC取得スキップ: %s", exc)
        return []

    rows = resp.get("rows", [])
    out = []
    with store.conn() as con:
        for r in rows:
            keys = r.get("keys", ["", ""])
            rec = (keys[0], keys[1] if len(keys) > 1 else "",
                   int(r.get("impressions", 0)), int(r.get("clicks", 0)),
                   float(r.get("ctr", 0)), float(r.get("position", 0)), end.isoformat())
            con.execute(
                "INSERT INTO gsc_metrics (query, page, impressions, clicks, ctr, position, day) "
                "VALUES (?,?,?,?,?,?,?)", rec)
            out.append({"query": rec[0], "impressions": rec[2], "position": rec[5]})
    log.info("GSC取得 %s行", len(out))
    return out


def near_miss_queries(store: Store, pos_min: float = 5.0, pos_max: float = 20.0,
                      min_impressions: int = 20) -> list[dict]:
    """「表示あるが順位が惜しい(5〜20位)」=強化候補クエリ。"""
    with store.conn() as con:
        rows = con.execute(
            "SELECT query, AVG(position) pos, SUM(impressions) impr FROM gsc_metrics "
            "GROUP BY query HAVING pos BETWEEN ? AND ? AND impr >= ? "
            "ORDER BY impr DESC LIMIT 20", (pos_min, pos_max, min_impressions)).fetchall()
        return [dict(r) for r in rows]
