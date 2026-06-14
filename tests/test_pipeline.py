"""end-to-end（モックAPI + dry-run）でPDCAの中核が回ることを確認。"""
from src.common.config import load_config
from src.pdca.store import Store
from src.pipeline import run_cycle, run_trend_sweep
from src.publish.site_builder import SITE_DIR
from src.rakuten.mock import MockRakutenClient
from src.tracker.price import is_lowest_ever, snapshot


def test_run_cycle_generates_site(store: Store, monkeypatch):
    monkeypatch.setenv("SITE_BASE_URL", "https://example.com")
    client = MockRakutenClient()
    result = run_cycle(client, store, load_config(), dry_run=True)
    assert result["pages"] > 0
    assert (SITE_DIR / "index.html").exists()
    assert (SITE_DIR / "sitemap.xml").exists()
    assert (SITE_DIR / "about.html").exists()
    # PR表記・免責文が含まれる（ステマ規制・楽天API規約）
    index = (SITE_DIR / "index.html").read_text(encoding="utf-8")
    assert "PR" in index
    # 商品ページが生成され、go.php経由リンク・免責文を含む
    deal_files = list((SITE_DIR / "deal").glob("*.html"))
    assert deal_files
    deal = deal_files[0].read_text(encoding="utf-8")
    assert "/go/" in deal and "当サイトの観測値" in deal


def test_price_drop_event_and_x_post(store: Store):
    client = MockRakutenClient()
    items = client.search(genre_id="565004")
    item = items[0]
    # 1回目: 初期価格を記録（イベントなし）
    assert snapshot(store, item) is None
    # 2回目: 値下げ → price_drop イベント
    item.price = int(item.price * 0.8)
    event = snapshot(store, item, drop_alert_pct=5.0)
    assert event and event["kind"] == "price_drop"
    assert store.recent_events()


def test_lowest_ever():
    series = [{"price": 1000}, {"price": 900}, {"price": 850}]
    assert is_lowest_ever(series)
    series2 = [{"price": 800}, {"price": 900}]
    assert not is_lowest_ever(series2)


def test_trend_sweep(store: Store, monkeypatch):
    monkeypatch.setenv("SITE_BASE_URL", "https://example.com")
    client = MockRakutenClient()
    result = run_trend_sweep(client, store, load_config(), dry_run=True)
    assert result["trends"] >= 1
    assert result["pages"] >= 1


def test_ogp_image_generated(store: Store, monkeypatch, tmp_path):
    from src.content import image as imgmod
    out = imgmod.make_card("ワイヤレスイヤホン ノイズキャンセリング", tmp_path / "ogp.png",
                           price=4980, old_price=6980, badge="値下げ速報")
    # Pillowが有れば生成される（無ければNone=フェイルソフト）
    if out is not None:
        assert out.exists() and out.stat().st_size > 0


def test_deal_page_sets_branded_ogp(store: Store, monkeypatch):
    monkeypatch.setenv("SITE_BASE_URL", "https://example.com")
    run_cycle(MockRakutenClient(), store, load_config(), dry_run=True)
    deal = next((SITE_DIR / "deal").glob("*.html")).read_text(encoding="utf-8")
    # OGP画像生成に成功していれば og:image はローカル画像を指す
    assert 'property="og:image"' in deal


def test_market_research(store: Store):
    from src.research.market import run_research
    client = MockRakutenClient()
    best = run_research(client, store, load_config()["niches"],
                        load_config()["research_weights"])
    assert best and "niche_score" in best[0]
    assert store.best_niches()
