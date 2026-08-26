"""見出しA/Bテスト・リスト化・FV強化の検証。"""
from src.content import headlines
from src.pdca.store import Store


def test_headline_render():
    s = headlines.render("【{pct}%OFF】{name}", name="ワイヤレスイヤホン", pct=20.0, price=4980)
    assert "20%OFF" in s and "ワイヤレスイヤホン" in s


def test_headline_pick_returns_valid_template(store: Store):
    tid, tmpl = headlines.pick(store, "price_drop", epsilon=0.2)
    ids = {v[0] for v in headlines.variants("price_drop")}
    assert tid in ids and "{name}" in tmpl


def test_headline_bandit_prefers_winner(store: Store, monkeypatch):
    # pd_low に報酬を厚く積むと、活用時に選ばれやすくなる
    store.bump_headline_pull("pd_low", "price_drop")
    store.bump_headline_pull("pd_pct", "price_drop")
    with store.conn() as con:
        con.execute("UPDATE headline_arms SET reward=10 WHERE template_id='pd_low'")
        con.execute("UPDATE headline_arms SET reward=0 WHERE template_id='pd_pct'")
    monkeypatch.setattr(headlines.random, "random", lambda: 0.99)  # 活用モード
    picks = [headlines.pick(store, "price_drop", epsilon=0.2)[0] for _ in range(5)]
    assert picks.count("pd_low") >= 3


def test_headline_reward_from_clickouts(store: Store):
    # page(template_id) と link(item_code) と click を紐付け → reward反映
    store.upsert_product({"item_code": "x:1", "name": "商品", "url": "", "affiliate_url": "",
                          "price": 1000, "shop_name": "", "genre_id": "1", "review_count": 0,
                          "review_average": 0, "affiliate_rate": 0, "point_rate": 1,
                          "postage_flag": 0, "availability": 1, "image_url": "", "score": 0})
    store.upsert_page("deal/x-1", "deal", "見出し", "x:1", template_id="pd_low")
    store.bump_headline_pull("pd_low", "price_drop")
    store.register_link("lid1", "https://item.rakuten.co.jp/x/1/", "x:1")
    with store.conn() as con:
        con.execute("INSERT INTO clicks (link_id, src, ua, ts) VALUES ('lid1','x','ua','t')")
    store.update_headline_rewards()
    arms = {a["template_id"]: a for a in store.headline_arms("price_drop")}
    assert arms["pd_low"]["reward"] == 1.0


def test_subscribe_dedup(store: Store):
    assert store.add_subscriber("a@example.com", "web") is True
    assert store.add_subscriber("a@example.com", "web") is False  # 重複
    assert store.subscriber_count() == 1


def test_deal_page_has_fv_and_cta(store: Store, monkeypatch):
    from src.common.config import load_config
    from src.pipeline import run_cycle
    from src.publish.site_builder import SITE_DIR
    from src.rakuten.mock import MockRakutenClient
    monkeypatch.setenv("SITE_BASE_URL", "https://example.com")
    run_cycle(MockRakutenClient(), store, load_config(), dry_run=True)
    deal = next((SITE_DIR / "deal").glob("*.html")).read_text(encoding="utf-8")
    assert 'class="fv"' in deal                    # FV強化
    assert "subscribe.php" in deal                 # リスト化導線(メール)
    assert "btn-hero" in deal                      # 主CTA
