"""伸びた投稿ファースト（スワイプファイル）の検証。"""
from src.content import reference, xdraft
from src.pdca.store import Store


def test_add_and_rank_exemplars_by_impressions(store: Store):
    store.add_exemplar("バズA（中）", "@x", 10000)
    store.add_exemplar("バズB（最大）", "@y", 90000)
    store.add_exemplar("バズC（小）", "@z", 500)
    top = store.top_exemplars(3)
    assert [e["text"] for e in top] == ["バズB（最大）", "バズA（中）", "バズC（小）"]


def test_winning_examples_prioritizes_curated_then_own(store: Store):
    store.add_exemplar("外部のバズ投稿", "@viral", 50000)
    did = store.add_draft("t", "future_bet", "自分の勝ちドラフト")
    store.set_draft_feedback(did, "keep")
    ex = reference.winning_examples(store, n_curated=4, n_own=2)
    assert ex[0] == "外部のバズ投稿"          # 伸びた投稿が最優先
    assert "自分の勝ちドラフト" in ex          # 自分の勝ちも補完


def test_reference_block_marks_exemplars_as_top_priority(store: Store):
    prompt = xdraft._future_prompt("topic", "", xdraft.FUTURE_ANGLES[0],
                                   None, ["伸びた投稿の例"], "")
    assert "最優先" in prompt and "伸びた投稿の例" in prompt
