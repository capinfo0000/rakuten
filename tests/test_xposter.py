"""X投稿（画像添付）のロジック検証。実鍵不要・fakeクライアントで code path を確認。"""
from pathlib import Path

from src.publish.x_poster import XPoster
from src.pdca.store import Store

CFG = {"x": {"max_posts_per_day": 5, "max_posts_per_month": 400}}


class _FakeResp:
    def __init__(self):
        self.data = {"id": "1234567890"}


class _FakeClient:
    def __init__(self):
        self.calls = []

    def create_tweet(self, **kwargs):
        self.calls.append(kwargs)
        return _FakeResp()


def test_dry_run_records_without_keys(store: Store):
    poster = XPoster(store, CFG, dry_run=True)
    assert poster.post("テスト投稿", "deal/x-1") == "dry-run"
    assert store.x_posts_today() == 1


def test_no_keys_skips(store: Store, monkeypatch):
    # 鍵が無ければ実投稿はスキップ（None）
    monkeypatch.delenv("X_API_KEY", raising=False)
    poster = XPoster(store, CFG, dry_run=False)
    assert poster.post("テスト", "deal/x-2") is None


def test_post_attaches_media(store: Store, monkeypatch, tmp_path):
    """画像があれば media_ids 付きで create_tweet される。"""
    fake = _FakeClient()
    poster = XPoster(store, CFG, dry_run=False)
    monkeypatch.setattr(poster, "_client", lambda: fake)
    monkeypatch.setattr(poster, "_upload_media", lambda p: "media-999")

    img = tmp_path / "card.png"
    img.write_bytes(b"\x89PNG\r\n")  # ダミー（存在チェックのみ）
    tid = poster.post("値下げ速報", "deal/x-3", image_path=img)

    assert tid == "1234567890"
    assert fake.calls and fake.calls[0].get("media_ids") == ["media-999"]
    assert store.x_posts_today() == 1


def test_post_text_only_when_no_image(store: Store, monkeypatch):
    fake = _FakeClient()
    poster = XPoster(store, CFG, dry_run=False)
    monkeypatch.setattr(poster, "_client", lambda: fake)
    poster.post("テキストのみ", "deal/x-4", image_path=None)
    assert "media_ids" not in fake.calls[0]


def test_media_upload_failure_falls_back_to_text(store: Store, monkeypatch, tmp_path):
    """メディアupload失敗時はテキストのみで投稿（フェイルソフト）。"""
    fake = _FakeClient()
    poster = XPoster(store, CFG, dry_run=False)
    monkeypatch.setattr(poster, "_client", lambda: fake)
    monkeypatch.setattr(poster, "_upload_media", lambda p: None)  # upload失敗
    img = tmp_path / "card.png"
    img.write_bytes(b"\x89PNG")
    tid = poster.post("値下げ", "deal/x-5", image_path=img)
    assert tid == "1234567890"
    assert "media_ids" not in fake.calls[0]
