"""GA4 Data API（無料）で維持率・来場数を取得。

鍵/プロパティ未設定・失敗時は [] を返す（フェイルソフト）。
"""
from __future__ import annotations

from src.common.config import REPO_ROOT, env
from src.common.log import get_logger
from src.pdca.store import Store

log = get_logger("tracking.ga4")


def fetch(store: Store, days: int = 7) -> list[dict]:
    prop = env("GA4_PROPERTY_ID")
    sa_path = env("GOOGLE_SERVICE_ACCOUNT_JSON", "secrets/service_account.json")
    key_path = (REPO_ROOT / sa_path) if sa_path else None
    if not prop or not key_path or not key_path.exists():
        log.info("GA4: 設定/鍵が無いためスキップ")
        return []
    try:
        from google.analytics.data_v1beta import BetaAnalyticsDataClient
        from google.analytics.data_v1beta.types import (
            DateRange, Dimension, Metric, RunReportRequest)
        from google.oauth2 import service_account

        creds = service_account.Credentials.from_service_account_file(str(key_path))
        client = BetaAnalyticsDataClient(credentials=creds)
        req = RunReportRequest(
            property=f"properties/{prop}",
            dimensions=[Dimension(name="pagePath")],
            metrics=[Metric(name="sessions"),
                     Metric(name="averageSessionDuration"),
                     Metric(name="bounceRate")],
            date_ranges=[DateRange(start_date=f"{days}daysAgo", end_date="today")],
            limit=200,
        )
        resp = client.run_report(req)
    except Exception as exc:  # noqa: BLE001
        log.warning("GA4取得スキップ: %s", exc)
        return []

    out = []
    with store.conn() as con:
        for row in resp.rows:
            page = row.dimension_values[0].value
            sessions = int(float(row.metric_values[0].value or 0))
            engagement = float(row.metric_values[1].value or 0)
            bounce = float(row.metric_values[2].value or 0)
            con.execute(
                "INSERT INTO ga4_metrics (page, sessions, avg_engagement, bounce_rate, day) "
                "VALUES (?,?,?,?,date('now'))", (page, sessions, engagement, bounce))
            out.append({"page": page, "sessions": sessions,
                        "engagement": engagement, "bounce": bounce})
    log.info("GA4取得 %s行", len(out))
    return out
