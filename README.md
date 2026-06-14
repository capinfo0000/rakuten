# 楽天 全自動・実用データ型アフィリエイト

楽天ウェブサービスAPIを使い、**AIの作文ではなく「ライブデータ」に価値を持たせる**実用データサイト
（値下げ速報・価格推移・ランキング変動・セール買い時）＋ X速報bot を**全自動**で運用するシステム。
データに基づくPDCAも自動で回す。

> 戦略の要点: 純AI記事量産はGoogleの **Scaled Content Abuse** 対象で稼げない。
> 本システムは「自動更新であるほど有用な実データ」を出力するため量産ペナルティを回避する。

## アーキテクチャ（PDCA）
```
Plan  : トレンド急上昇 + 市場リサーチの穴場 + GSC順位惜しいクエリ + 過去スコア で対象選定
Do    : 楽天APIで商品取得 → 売れやすさスコアで選定 → 価格記録 → 静的HTML生成 → X速報
Check : GSC(表示/CTR/順位) / GA4(維持率) / go.php(クリックアウト) / X指標
Act   : 統合スコアで対象・タイミング・題材を自動ローテーション
```

## クイックスタート（オフライン検証）
```bash
pip install -r requirements.txt
python scripts/run_research.py --mock           # 穴場ニッチの自動発見
python scripts/run_cycle.py   --mock --dry-run  # 収集→生成→公開(data/site/)
python scripts/run_trend_sweep.py --mock --dry-run
pytest -q                                       # テスト
```
生成物は `data/site/`。`--mock` を外すと実APIを使用（要 `.env`）。

## セットアップ（本番）
1. `cp .env.example .env` して各値を設定
2. 各種ID取得（下記）
3. `config/config.yaml` のニッチ/重み/セール日程を調整
4. コアサーバーに配置（`deploy/coreserver-cron.example` 参照）

### 各種ID取得
| 用途 | 取得先 | 環境変数 |
|---|---|---|
| 楽天API | https://webservice.rakuten.co.jp/app/create （応募タイプ「ウェブサイト」） | `RAKUTEN_APP_ID` |
| 楽天アフィリエイト(直) | https://affiliate.rakuten.co.jp/ | `RAKUTEN_AFFILIATE_ID` |
| もしもアフィリエイト | https://af.moshimo.com/af/shop/index （審査・各社提携） | `MOSHIMO_*` |
| Gemini(無料・任意) | https://aistudio.google.com/ | `GEMINI_API_KEY` |
| X(投稿専用) | https://developer.x.com/ | `X_*` |
| Search Console / GA4 | GCPサービスアカウント | `GSC_SITE_URL` / `GA4_PROPERTY_ID` |

> アフィリンクは `AFFILIATE_PROVIDER=rakuten_direct|moshimo` で切替。もしもは最低支払額が低く
> 現金振込しやすい（※W報酬は楽天/Amazon対象外）。

## デプロイ（コアサーバー CORE-X 想定）
- 静的サイト: `data/site/` を `public_html` へ（`scripts/deploy.py --dest <public_html>`）
- クリック計測: `public/go.php` と `public/.htaccess` を `public_html` へ。`/go/<id>?src=` で計測→302
- DB: `data/app.db`（SQLite, Web非公開）。PHPとPythonが共有
- スケジューラ: コアサーバーの cron（`deploy/coreserver-cron.example`）
- **ヘッドレスブラウザは使わない**（HTTP+パースのみ。最安プランで動く）

## コンプライアンス（実装済み・必読）
- **ステマ規制**: 全ページ・全X投稿に「PR」表記（テンプレ/投稿文に自動挿入）
- **楽天API規約**: 価格は24h以内更新・取得日時明記・免責文を価格隣接で掲示（実装済み）。価格推移は「当サイトの観測値」と明示。自己アフィリエイト禁止
- **X規約**: 投稿のみ・同一文反復回避・自動フォロー/いいねなし・人間的頻度
- **運営者情報/プライバシーポリシー** ページを自動生成（E-E-A-T・法対応）

## 収益が出ない前提の設計
- 全自動＝維持の手間ゼロ。止めず回し続けて上振れ（トレンド的中・SEO累積）を取りに行く
- 収益多重化（もしも経由でAmazon/楽天/Yahoo!併記・将来AdSense）、Xフォロワーを資産化
- KPIゲート未達は人手で止めず**題材を自動ローテーション**（M2の optimizer）

## ディレクトリ
`src/` 本体、`public/` 公開資産(go.php/.htaccess)、`scripts/` cronエントリ、`config/`、`tests/`。
完全な設計・調査根拠は計画ファイルを参照。
