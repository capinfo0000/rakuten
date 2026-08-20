"""PDCAダッシュボード（静的HTML）とKPIゲート判定。

人間の可視性のためローカルHTMLを生成。任意でNotionへもpush。
"""
from __future__ import annotations

from datetime import date, timedelta

from src.common.config import REPO_ROOT, load_config
from src.common.log import get_logger
from src.pdca.store import Store
from src.tracking import clicks

log = get_logger("ops.dashboard")

REPORT_PATH = REPO_ROOT / "data" / "site" / "_dashboard.html"


def collect_kpis(store: Store) -> dict:
    co = clicks.clickouts_by_source(store)
    with store.conn() as con:
        impr = con.execute("SELECT COALESCE(SUM(impressions),0) s FROM gsc_metrics").fetchone()["s"]
        gsc_clicks = con.execute("SELECT COALESCE(SUM(clicks),0) s FROM gsc_metrics").fetchone()["s"]
        pages = con.execute("SELECT COUNT(*) n FROM pages").fetchone()["n"]
        events = con.execute("SELECT COUNT(*) n FROM events").fetchone()["n"]
        posts = con.execute("SELECT COUNT(*) n FROM x_posts").fetchone()["n"]
    return {
        "pages": pages, "events": events, "x_posts": posts,
        "gsc_impressions": impr, "gsc_clicks": gsc_clicks,
        "clickouts_total": sum(co.values()), "clickouts_by_src": co,
        "subscribers": store.subscriber_count(),
    }


def evaluate_gates(kpis: dict, config: dict | None = None) -> list[dict]:
    """KPIゲートの達成判定（人手で止めず、未達は題材ローテへの信号）。"""
    cfg = (config or load_config()).get("kpi_gates", {})
    results = []
    w4 = cfg.get("week4", {})
    results.append({
        "gate": "week4",
        "ok": (kpis["gsc_impressions"] >= w4.get("gsc_impressions_min", 100)
               and kpis["clickouts_total"] >= w4.get("clickouts_min", 1)),
        "detail": f"表示{kpis['gsc_impressions']}/クリックアウト{kpis['clickouts_total']}",
    })
    w12 = cfg.get("week12", {})
    results.append({
        "gate": "week12",
        "ok": kpis["gsc_clicks"] >= w12.get("clicks_min", 20),
        "detail": f"GSCクリック{kpis['gsc_clicks']}",
    })
    return results


def render(store: Store, config: dict | None = None) -> str:
    kpis = collect_kpis(store)
    gates = evaluate_gates(kpis, config)
    rows = "".join(
        f"<tr><td>{k}</td><td>{v}</td></tr>" for k, v in kpis.items()
        if k != "clickouts_by_src")
    gate_rows = "".join(
        f"<li>{g['gate']}: {'✅' if g['ok'] else '⚠️未達'} ({g['detail']})</li>" for g in gates)
    html = (
        f"<!doctype html><meta charset='utf-8'><title>PDCA Dashboard</title>"
        f"<h1>PDCA ダッシュボード（{date.today()}）</h1>"
        f"<h2>KPI</h2><table border=1 cellpadding=6>{rows}</table>"
        f"<h2>KPIゲート</h2><ul>{gate_rows}</ul>"
        f"<p>流入元別クリックアウト: {kpis['clickouts_by_src']}</p>"
    )
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(html, encoding="utf-8")
    log.info("ダッシュボード生成 %s", REPORT_PATH)
    return html
