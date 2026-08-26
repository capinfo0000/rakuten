"""X下書き生成（意見ドリブン・フォールバック）とドラフトDAOの検証。実鍵不要。"""
from src.content import xdraft
from src.pdca.store import Store


def test_generate_drafts_fallback():
    # Gemini鍵無し → テンプレフォールバックで角度分の案が返る
    drafts = xdraft.generate_drafts("甲子園の速球投手")
    assert len(drafts) == len(xdraft.ANGLES)
    assert all(d["text"] and "甲子園の速球投手" in d["text"] for d in drafts)


def test_draft_from_opinion_fallback():
    drafts = xdraft.draft_from_opinion("甲子園の速球投手", "高校生で156km/hは異次元だと思う", n=3)
    assert len(drafts) == 3
    # フォールバックでも意見が本文に反映される
    assert all(d["text"] for d in drafts)
    assert any("異次元" in d["text"] for d in drafts)


def test_draft_dao(store: Store):
    did = store.add_draft("トピックA", "hot_take", "本文テキスト")
    assert did > 0
    assert store.recent_drafts()[0]["text"] == "本文テキスト"
    store.mark_draft_posted(did, impressions=1200)
    perf = store.angle_performance()
    assert perf and perf[0]["angle"] == "hot_take" and perf[0]["avg_imp"] == 1200
