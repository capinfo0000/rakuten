"""M2（学習・運用）の検証。鍵無し環境でフェイルソフトに動くこと。"""
from src.common.config import load_config
from src.ops import dashboard
from src.pdca import optimizer, scorer
from src.pdca.store import Store
from src.pipeline import run_cycle
from src.rakuten.mock import MockRakutenClient
from src.tracking import clicks, ga4, gsc, x_metrics


def _seed(store: Store) -> None:
    run_cycle(MockRakutenClient(), store, load_config(), dry_run=True)
    # クリックを一部のリンクに付与
    link_ids = list(clicks.clickouts_by_link(store).keys())
    with store.conn() as con:
        links = con.execute("SELECT link_id FROM links LIMIT 2").fetchall()
        for r in links:
            con.execute("INSERT INTO clicks (link_id, src, ua, ts) "
                        "VALUES (?, 'x', 'ua', datetime('now'))", (r["link_id"],))


def test_tracking_failsoft(store: Store):
    # 鍵が無くても例外を出さず空/Noneで返る
    assert gsc.fetch(store) == []
    assert ga4.fetch(store) == []
    assert x_metrics.record(store)["followers"] is None


def test_scorer_and_optimizer(store: Store, monkeypatch):
    monkeypatch.setenv("SITE_BASE_URL", "https://example.com")
    _seed(store)
    updated = scorer.update_arms(store)
    assert updated  # ジャンルarmが更新される
    focus = optimizer.select_focus_genres(store, epsilon=0.2, k=2)
    assert isinstance(focus, list) and len(focus) >= 1


def test_dashboard_and_gates(store: Store, monkeypatch):
    monkeypatch.setenv("SITE_BASE_URL", "https://example.com")
    _seed(store)
    html = dashboard.render(store, load_config())
    assert "PDCA" in html
    kpis = dashboard.collect_kpis(store)
    assert kpis["clickouts_total"] >= 1
    gates = dashboard.evaluate_gates(kpis, load_config())
    assert any(g["gate"] == "week4" for g in gates)
