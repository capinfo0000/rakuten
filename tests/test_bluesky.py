"""Bluesky投稿（無料）のロジック検証。実鍵不要・内部メソッドをfake化。"""
from src.pdca.store import Store
from src.publish.bluesky import BlueskyPoster, build_link_facets

CFG = {"bluesky": {"max_posts_per_day": 20, "max_posts_per_month": 600}}


def test_link_facets_byte_offsets():
    text = "値下げ速報 https://example.com/deal/x .png #楽天"
    facets = build_link_facets(text)
    assert facets and facets[0]["features"][0]["uri"].startswith("https://example.com")
    # 日本語があってもUTF-8バイト基準で算出される
    bs = facets[0]["index"]["byteStart"]
    assert text.encode("utf-8")[bs:bs + 5] == b"https"


def test_skip_when_no_creds(store: Store, monkeypatch):
    monkeypatch.delenv("BLUESKY_HANDLE", raising=False)
    monkeypatch.delenv("BLUESKY_APP_PASSWORD", raising=False)
    poster = BlueskyPoster(store, CFG, dry_run=False)
    assert not poster.available()
    assert poster.post("テスト", "deal/b-1") is None


def test_dry_run_records(store: Store, monkeypatch):
    monkeypatch.setenv("BLUESKY_HANDLE", "me.bsky.social")
    monkeypatch.setenv("BLUESKY_APP_PASSWORD", "app-pass")
    poster = BlueskyPoster(store, CFG, dry_run=True)
    assert poster.post("テスト投稿 https://example.com/x", "deal/b-2") == "dry-run"
    assert store.social_posts_today("bluesky") == 1


def test_post_with_image(store: Store, monkeypatch, tmp_path):
    monkeypatch.setenv("BLUESKY_HANDLE", "me.bsky.social")
    monkeypatch.setenv("BLUESKY_APP_PASSWORD", "app-pass")
    poster = BlueskyPoster(store, CFG, dry_run=False)

    captured = {}
    monkeypatch.setattr(poster, "_login", lambda: ("jwt-x", "did:plc:abc"))
    monkeypatch.setattr(poster, "_upload_blob", lambda jwt, p: {"$type": "blob", "ref": "r"})

    def fake_create(jwt, did, record):
        captured["record"] = record
        return "at://did:plc:abc/app.bsky.feed.post/123"
    monkeypatch.setattr(poster, "_create_record", fake_create)

    img = tmp_path / "card.png"
    img.write_bytes(b"\x89PNG")
    uri = poster.post("値下げ速報 https://example.com/deal/x", "deal/b-3", image_path=img)

    assert uri and uri.startswith("at://")
    rec = captured["record"]
    assert rec["embed"]["$type"] == "app.bsky.embed.images"     # 画像添付
    assert rec.get("facets")                                    # リンクfacet
    assert store.social_posts_today("bluesky") == 1


def test_daily_limit(store: Store, monkeypatch):
    monkeypatch.setenv("BLUESKY_HANDLE", "me.bsky.social")
    monkeypatch.setenv("BLUESKY_APP_PASSWORD", "app-pass")
    cfg = {"bluesky": {"max_posts_per_day": 1, "max_posts_per_month": 600}}
    poster = BlueskyPoster(store, cfg, dry_run=True)
    assert poster.post("1件目", "s1") == "dry-run"
    assert poster.post("2件目", "s2") is None  # 上限で停止
