"""テキスト生成。

主役はデータ（表・推移・差分）。LLMは短い要約/X投稿/買い時ガイドのみ。
Gemini無料枠が無い/失敗時はテンプレ文へフォールバック（全自動を止めない）。
品質ガード: 最低限の情報量を満たさないものは公開保留。
"""
from __future__ import annotations

from src.common.config import env
from src.common.log import get_logger

log = get_logger("content")

MIN_BODY_CHARS = 120  # 品質ガード: 本文の最低文字数


def _gemini(prompt: str, max_chars: int = 280) -> str | None:
    """Gemini呼び出し。鍵無し/失敗は None（フォールバックへ）。"""
    key = env("GEMINI_API_KEY")
    if not key:
        return None
    try:
        import google.generativeai as genai

        genai.configure(api_key=key)
        model = genai.GenerativeModel(env("GEMINI_MODEL", "gemini-2.5-flash"))
        resp = model.generate_content(prompt)
        text = (resp.text or "").strip()
        return text[:max_chars] if text else None
    except Exception as exc:  # noqa: BLE001 — フェイルソフト
        log.warning("Gemini生成スキップ: %s", exc)
        return None


def price_drop_summary(name: str, prev_price: int, price: int, drop_pct: float) -> str:
    """値下げ速報の短い要約（テンプレ→LLMで肉付け）。"""
    base = (f"「{name}」が {prev_price:,}円から {price:,}円へ"
            f"値下がりしました（{drop_pct:.1f}%OFF）。")
    prompt = (f"次の事実だけを使い、誇張せず40〜80字の日本語で値下げを紹介して。"
              f"事実: 商品『{name}』が{prev_price}円→{price}円({drop_pct:.0f}%OFF)。")
    return _gemini(prompt, 120) or base


def buy_timing_guide(name: str, sale_label: str) -> str:
    base = (f"{sale_label}は「{name}」を狙う好機。ポイント倍率が上がる"
            f"買い回り期間・5と0のつく日を活用しましょう。")
    prompt = (f"{sale_label}中に『{name}』を買う際のポイント獲得のコツを、"
              f"事実ベースで80〜120字の日本語で。")
    return _gemini(prompt, 200) or base


def x_post_text(name: str, headline: str, url: str, sale_label: str = "") -> str:
    """X速報の投稿文（毎回バリエーションを作る＝同一文反復のスパム回避）。"""
    tag = "#楽天 #値下げ" if "OFF" in headline else "#楽天"
    sale = f" {sale_label}" if sale_label and sale_label != "通常期" else ""
    base = f"【速報】{headline}{sale}\n{name}\n{url} {tag}"
    prompt = (f"X(旧Twitter)の投稿文を120字以内で。煽らず事実ベース。"
              f"必ず文末にURL『{url}』とハッシュタグ『{tag}』を含める。"
              f"商品『{name}』、見出し『{headline}』{sale}。")
    text = _gemini(prompt, 250)
    if text and url in text:
        return text
    return base


def passes_quality_gate(body: str) -> bool:
    """公開可否の品質ガード（低品質量産の回避）。"""
    return bool(body) and len(body) >= MIN_BODY_CHARS
