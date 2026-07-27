#!/usr/bin/env python3
"""任意: 楽天アフィリエイト成果CSVを取り込み、真の成約を記録。

楽天に成果APIが無いため、管理画面からDLしたCSVを手動/半自動で取り込み、
代理指標(PV/クリック)と"円"の乖離を照合する。
列名はCSV書式に依存するため、--col で実列名を指定可能。
"""
import argparse
import csv

import _bootstrap  # noqa: F401

from src.common.log import get_logger
from src.pdca.store import Store, now_iso

log = get_logger("import_report")


def main() -> None:
    ap = argparse.ArgumentParser(description="楽天成果CSV取込")
    ap.add_argument("csv_path")
    ap.add_argument("--reward-col", default="報酬額")
    ap.add_argument("--count-col", default="件数")
    args = ap.parse_args()

    store = Store()
    with store.conn() as con:
        con.execute("CREATE TABLE IF NOT EXISTS report_imports "
                    "(id INTEGER PRIMARY KEY AUTOINCREMENT, reward INTEGER, "
                    "conversions INTEGER, imported_at TEXT)")

    total_reward = 0
    total_conv = 0
    with open(args.csv_path, encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            try:
                total_reward += int(str(row.get(args.reward_col, "0")).replace(",", "") or 0)
                total_conv += int(str(row.get(args.count_col, "0")).replace(",", "") or 0)
            except ValueError:
                continue

    with store.conn() as con:
        con.execute("INSERT INTO report_imports (reward, conversions, imported_at) "
                    "VALUES (?,?,?)", (total_reward, total_conv, now_iso()))
    print(f"取込完了: 報酬合計 {total_reward:,}円 / 成約 {total_conv}件")


if __name__ == "__main__":
    main()
