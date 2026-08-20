"""X（旧Twitter）のインプ最大化を狙う投稿ドラフト生成。

トレンド/時事の1トピックから、切り口(angle)違いの投稿案を複数生成する。
「1行目(フック)が9割」に基づき、最初の一撃で止める文を重視。
Geminiが使えれば自然な文、無ければテンプレにフォールバック（全自動を止めない）。

方針: AIは"下書き"まで。最終的に人が厳選して投稿する（アルゴリズム/規約に強い）。
"""
from __future__ import annotations

from dataclasses import dataclass

from src.content.generator import _gemini
from src.common.log import get_logger

log = get_logger("content.xdraft")


@dataclass
class Angle:
    id: str
    name: str
    instruction: str     # Geminiへの切り口指示
    template: str        # フォールバック（{topic}を埋める）


# インプが伸びやすい代表的な切り口
ANGLES: list[Angle] = [
    Angle("hot_take", "ホットテイク",
          "強めの断定・独自見解で意見を述べる。賛否が分かれてもよい。",
          "{topic}、正直これは見逃せない。理由を一つだけ言うと——"),
    Angle("question", "問いかけ",
          "読者に問いかけて反応(リプ/引用)を誘う。",
          "{topic}って結局どう思う？自分はこう見てる👇"),
    Angle("list", "リスト型",
          "要点を3つの短い箇条書きで。スクロールを止める。",
          "{topic}で今おさえるべき3つ\n①…\n②…\n③…"),
    Angle("empathy", "共感/あるある",
          "共感を誘う『あるある』や本音で距離を縮める。",
          "{topic}、みんな言わないけど正直こうだよね。"),
    Angle("contrarian", "逆張り",
          "世間の空気と逆の視点を提示して注目を集める（事実は曲げない）。",
          "{topic}、みんな騒いでるけど本質はそこじゃない。"),
]

MAX_CHARS = 135  # 無料アカウント想定で日本語は短め


def _prompt(topic: str, angle: Angle, context: str) -> str:
    return (
        f"あなたはXで伸びる投稿を書くプロです。トピック『{topic}』について、"
        f"次の切り口で日本語のX投稿を1つ書いてください。\n"
        f"切り口: {angle.instruction}\n"
        f"制約: 1行目(フック)で必ずスクロールを止める。全体{MAX_CHARS}字以内。"
        f"煽りすぎず事実は曲げない。ハッシュタグは付けても1個まで。絵文字は最小限。"
        f"説明や前置きは書かず、投稿本文だけを出力。\n"
        + (f"参考情報: {context}\n" if context else "")
    )


def generate_drafts(topic: str, context: str = "", angles: list[Angle] | None = None
                    ) -> list[dict]:
    """1トピックから切り口違いのドラフトを生成。[{angle, angle_name, text}]。"""
    angles = angles or ANGLES
    drafts: list[dict] = []
    for a in angles:
        text = _gemini(_prompt(topic, a, context), max_chars=MAX_CHARS + 20)
        if not text:
            text = a.template.format(topic=topic)
        drafts.append({"angle": a.id, "angle_name": a.name, "text": text.strip()})
    return drafts


def _opinion_prompt(topic: str, opinion: str, angle: Angle) -> str:
    return (
        f"あなたはXで伸びる投稿を書くプロの編集者です。\n"
        f"トピック『{topic}』について、投稿者本人の本音は次の通りです:\n"
        f"「{opinion}」\n\n"
        f"この本音を軸に、Xで伸びやすいように『{angle.name}』の切り口で、"
        f"少し誇張して(ただし事実は曲げない/嘘はつかない)インパクトのある投稿に仕上げてください。\n"
        f"制約: 1行目(フック)で必ずスクロールを止める。全体{MAX_CHARS}字以内。"
        f"投稿者の意見・立場は変えない。ハッシュタグは1個まで、絵文字は最小限。"
        f"説明や前置きは書かず、投稿本文だけを出力。"
    )


def draft_from_opinion(topic: str, opinion: str, n: int = 4) -> list[dict]:
    """『ネタ＋本人の意見』から、伸びそうに誇張したドラフトを複数生成。

    人の本音(オリジナリティ)を核に、AIがフック強化・誇張・整形だけ行う。
    嘘や事実の捏造はしない（意見の増幅にとどめる）。
    """
    chosen = ANGLES[:n]
    drafts: list[dict] = []
    for a in chosen:
        text = _gemini(_opinion_prompt(topic, opinion, a), max_chars=MAX_CHARS + 20)
        if not text:
            # フォールバック: 意見をそのままフック化
            text = f"{opinion}\n——{topic}、これだけは言いたい。"
        drafts.append({"angle": a.id, "angle_name": a.name, "text": text.strip()})
    return drafts
