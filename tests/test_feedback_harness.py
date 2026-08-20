"""メタ学習ハーネス（意見の蓄積→次回生成へ反映／手本参照）の検証。"""
from src.content import feedback, xdraft
from src.pdca.store import Store


def test_feedback_updates_angle_pref_and_directives(store: Store):
    did = store.add_draft("topicA", "future_bet", "本文")
    feedback.record(store, did, "future_bet", "keep", rating=5, directive="もっと短く")
    # angle加点 + 編集方針蓄積
    assert store.angle_pref_scores().get("future_bet", 0) > 0
    assert "もっと短く" in store.top_style_directives()
    # rejectは減点
    did2 = store.add_draft("topicA", "future_absurd", "本文2")
    feedback.record(store, did2, "future_absurd", "reject")
    assert store.angle_pref_scores().get("future_absurd", 0) < 0


def test_order_angles_prefers_learned(store: Store, monkeypatch):
    store.bump_angle_pref("future_bet", 3.0)
    store.bump_angle_pref("future_absurd", -2.0)
    monkeypatch.setattr(feedback.random, "random", lambda: 0.99)  # 活用モード
    ordered = feedback.order_angles(store, xdraft.FUTURE_ANGLES)
    assert ordered[0].id == "future_bet"
    assert ordered[-1].id == "future_absurd"


def test_learned_directives_injected_into_prompt(store: Store):
    store.add_style_directive("もっとバカバカしく")
    directives = feedback.learned_directives(store)
    prompt = xdraft._future_prompt("topic", "", xdraft.FUTURE_ANGLES[0], directives)
    assert "もっとバカバカしく" in prompt


def test_exemplars_from_winners(store: Store):
    a = store.add_draft("t", "future_bet", "勝ちドラフト")
    store.set_draft_feedback(a, "keep")
    store.add_draft("t", "future_absurd", "普通のドラフト")
    ex = store.exemplar_drafts()
    assert "勝ちドラフト" in ex
    # 生成プロンプトに手本が入る
    prompt = xdraft._future_prompt("topic", "", xdraft.FUTURE_ANGLES[0], None, ex, "")
    assert "勝ちドラフト" in prompt


def test_revise_fallback_returns_text(store: Store):
    # Gemini鍵無し → 元テキストを返す（フェイルソフト）
    out = xdraft.revise("元の投稿", "短くして")
    assert out == "元の投稿"
