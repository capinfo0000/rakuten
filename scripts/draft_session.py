#!/usr/bin/env python3
"""下書きフィードバック・ハーネス（メタ学習ループ）。

「トレンド/ネタ → 未来予測で下書き量産 → あなたが意見 → 修正＆学習」を回す。
生成時に注入するもの:
  - 学習した編集方針(style_directives) と 好みの切り口順(angle_prefs)
  - 伸びた/採用した過去ドラフト(exemplar) と いまバズってる外部文脈(Yahoo)

使い方:
  # 生成してレビュー用mdを出力（人はここに意見を書く／Xに投稿）
  python scripts/draft_session.py --topic "甲子園で高校生が156km/h・無失点" --opinion "高校生でヤバい"

  # 意見を反映（採用/却下/評価/編集方針を記録して学習）
  python scripts/draft_session.py --feedback 12 --verdict keep --rating 5 --directive "もっと短く"

  # 既存ドラフトを指示どおり修正
  python scripts/draft_session.py --revise 12 --instruction "バカバカしく尖らせて"
"""
import argparse
from pathlib import Path

import _bootstrap  # noqa: F401

from src.common.config import REPO_ROOT
from src.content import feedback, reference, xdraft
from src.pdca.store import Store

DRAFT_DIR = REPO_ROOT / "data" / "drafts"


def cmd_generate(store: Store, topic: str, opinion: str, use_buzz: bool) -> None:
    directives = feedback.learned_directives(store)
    angles = feedback.order_angles(store, xdraft.FUTURE_ANGLES)
    exemplars = reference.winning_examples(store)  # 伸びた投稿ファースト
    buzz = reference.buzz_context(topic) if use_buzz else ""

    drafts = xdraft.draft_future(topic, opinion, n=len(angles), angles=angles,
                                 directives=directives, exemplars=exemplars, buzz=buzz)

    lines = [f"# 下書きレビュー: {topic}", ""]
    if directives:
        lines.append(f"_学習済みの編集方針: {', '.join(directives)}_")
    if exemplars:
        lines.append(f"_お手本(過去の勝ち): {len(exemplars)}件を反映_")
    if buzz:
        lines.append(f"_いまバズ: {buzz[:80]}…_")
    lines.append("")
    for d in drafts:
        did = store.add_draft(topic, d["angle"], d["text"])
        lines.append(f"## [{did}] {d['angle_name']}")
        lines.append(d["text"])
        lines.append("")
        lines.append(f"→ 意見: `python scripts/draft_session.py --feedback {did} "
                     f"--verdict keep|reject|revise --rating 1-5 --directive \"...\"`")
        lines.append("")

    DRAFT_DIR.mkdir(parents=True, exist_ok=True)
    out = DRAFT_DIR / f"session-{store.recent_drafts(1)[0]['id']}.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"下書き{len(drafts)}件を生成 → {out}")
    for line in lines:
        print(line)


def cmd_feedback(store: Store, draft_id: int, verdict: str, rating, directive) -> None:
    row = next((d for d in store.recent_drafts(500) if d["id"] == draft_id), None)
    if not row:
        print(f"draft {draft_id} が見つかりません")
        return
    feedback.record(store, draft_id, row["angle"], verdict, rating, directive)
    print(f"記録: draft {draft_id} verdict={verdict} rating={rating} directive={directive!r}")
    print(f"学習: 好みの切り口 {store.angle_pref_scores()} / 編集方針 {store.top_style_directives()}")


def cmd_add_exemplar(store: Store, text: str, source: str, impressions: int) -> None:
    eid = store.add_exemplar(text, source, impressions)
    print(f"スワイプ登録 [{eid}] imp={impressions} src={source!r}: {text[:40]}")
    print(f"現在の手本(上位): {[e['text'][:24] for e in store.top_exemplars()]}")


def cmd_revise(store: Store, draft_id: int, instruction: str) -> None:
    row = next((d for d in store.recent_drafts(500) if d["id"] == draft_id), None)
    if not row:
        print(f"draft {draft_id} が見つかりません")
        return
    directives = feedback.learned_directives(store)
    revised = xdraft.revise(row["text"], instruction, directives)
    new_id = store.add_draft(row["topic"], row["angle"], revised)
    feedback.record(store, draft_id, row["angle"], "revise", None, instruction)
    print(f"修正版 [{new_id}]:\n{revised}")


def main() -> None:
    ap = argparse.ArgumentParser(description="下書きフィードバック・ハーネス")
    ap.add_argument("--topic", help="ネタ（未指定なら意見反映/修正モード）")
    ap.add_argument("--opinion", default="", help="あなたの一言（任意）")
    ap.add_argument("--no-buzz", action="store_true", help="外部バズ参照をしない")
    ap.add_argument("--feedback", type=int, metavar="ID", help="意見を反映するdraft ID")
    ap.add_argument("--verdict", default="keep", choices=["keep", "post", "revise", "reject", "skip"])
    ap.add_argument("--rating", type=int)
    ap.add_argument("--directive", help="恒常化したい編集方針（例: もっと短く）")
    ap.add_argument("--revise", type=int, metavar="ID", help="修正するdraft ID")
    ap.add_argument("--instruction", default="", help="修正指示")
    ap.add_argument("--add-exemplar", metavar="TEXT",
                    help="伸びた投稿をスワイプファイルに登録（生成の軸にする）")
    ap.add_argument("--source", default="", help="出典（例 @account）")
    ap.add_argument("--impressions", type=int, default=0, help="その投稿のインプ（分かれば）")
    args = ap.parse_args()

    store = Store()
    if args.add_exemplar:
        cmd_add_exemplar(store, args.add_exemplar, args.source, args.impressions)
    elif args.revise:
        cmd_revise(store, args.revise, args.instruction)
    elif args.feedback:
        cmd_feedback(store, args.feedback, args.verdict, args.rating, args.directive)
    elif args.topic:
        cmd_generate(store, args.topic, args.opinion, use_buzz=not args.no_buzz)
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
