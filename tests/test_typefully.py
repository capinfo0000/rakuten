"""Typefully(下書き/予約)とbuild_postersのテスト。実鍵不要。"""
from src.pdca.store import Store
from src.publish.social import build_posters
from src.publish.typefully import TypefullyPoster

CFG = {"typefully": {"schedule": "", "max_posts_per_day": 10, "max_posts_per_month": 15}}


def test_skip_when_no_key(store: Store, monkeypatch):
    monkeypatch.delenv("TYPEFULLY_API_KEY", raising=False)
    p = TypefullyPoster(store, CFG, dry_run=False)
    assert not p.available()
    assert p.post("テスト", "s1") is None


def test_dry_run_records(store: Store, monkeypatch):
    monkeypatch.setenv("TYPEFULLY_API_KEY", "tk_123")
    p = TypefullyPoster(store, CFG, dry_run=True)
    assert p.post("下書きテスト https://example.com", "s2") == "dry-run"
    assert store.social_posts_today("typefully") == 1


def test_free_tier_monthly_cap(store: Store, monkeypatch):
    monkeypatch.setenv("TYPEFULLY_API_KEY", "tk_123")
    cfg = {"typefully": {"schedule": "", "max_posts_per_day": 99, "max_posts_per_month": 2}}
    p = TypefullyPoster(store, cfg, dry_run=True)
    assert p.post("1", "a") == "dry-run"
    assert p.post("2", "b") == "dry-run"
    assert p.post("3", "c") is None  # 無料枠の月上限で停止


def test_build_posters_includes_typefully(store: Store):
    cfg = {"social": {"typefully": True, "x": False, "bluesky": False}}
    posters = build_posters(store, cfg, dry_run=True)
    assert any(type(p).__name__ == "TypefullyPoster" for p in posters)
    assert not any(type(p).__name__ == "XPoster" for p in posters)
