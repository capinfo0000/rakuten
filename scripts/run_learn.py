#!/usr/bin/env python3
"""cron: Check+Act（GSC/GA4/クリック/X集計→学習→ダッシュボード→ゲート判定）。"""
import argparse

import _bootstrap  # noqa: F401

from src.common.config import load_config
from src.common.log import get_logger
from src.integrations import github, notion
from src.ops import backup, dashboard
from src.pdca import optimizer, scorer
from src.pdca.store import Store
from src.tracking import ga4, gsc, x_metrics

log = get_logger("run_learn")


def main() -> None:
    ap = argparse.ArgumentParser(description="Check+Act 学習サイクル")
    ap.add_argument("--no-backup", action="store_true")
    args = ap.parse_args()

    config = load_config()
    store = Store()

    # Check: 計測（すべてフェイルソフト）
    gsc.fetch(store)
    ga4.fetch(store)
    x_metrics.record(store)

    # Act: 報酬更新 → 次の注力ジャンル選定
    scorer.update_arms(store)
    store.update_headline_rewards()  # 見出しA/Bの勝ち型を学習
    epsilon = config.get("optimizer", {}).get("epsilon", 0.2)
    focus = optimizer.select_focus_genres(store, epsilon=epsilon)

    # 可視化 + ゲート判定
    dashboard.render(store, config)
    kpis = dashboard.collect_kpis(store)
    gates = dashboard.evaluate_gates(kpis, config)
    notion.push_kpis(kpis)

    near = gsc.near_miss_queries(store)
    for g in gates:
        if not g["ok"]:
            github.create_issue(
                f"[KPIゲート未達] {g['gate']}",
                f"{g['detail']}\n次の注力ジャンル: {focus}\n強化候補クエリ: {near[:5]}",
                labels=["kpi"])

    print(f"learn done: focus={focus} kpis={kpis} gates={[g['gate'] for g in gates if g['ok']]}")
    if not args.no_backup:
        backup.backup_db()


if __name__ == "__main__":
    main()
