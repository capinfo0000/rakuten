"""OGP/X用画像のローカル生成（Pillow・無料・ブラウザ不要）。

凝ったブランド素材は別途Canva(私のセッション)で用意するが、
無人ランタイムはこのPillow生成で完結させる。Pillow未導入でもNoneでスキップ。
"""
from __future__ import annotations

import textwrap
from pathlib import Path

from src.common.log import get_logger

log = get_logger("content.image")

W, H = 1200, 630  # OGP標準


def make_card(text: str, out_path: Path, subtitle: str = "",
              bg=(15, 23, 42), fg=(255, 255, 255), accent=(248, 113, 113)) -> Path | None:
    """見出しテキストのカード画像を生成。失敗時 None（フェイルソフト）。"""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except Exception as exc:  # noqa: BLE001
        log.warning("Pillow未導入のため画像生成スキップ: %s", exc)
        return None

    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        img = Image.new("RGB", (W, H), bg)
        draw = ImageDraw.Draw(img)

        font_title = _load_font(56)
        font_sub = _load_font(32)

        # アクセントバー
        draw.rectangle([0, 0, 16, H], fill=accent)

        y = 130
        for line in textwrap.wrap(text, width=16)[:4]:
            draw.text((80, y), line, font=font_title, fill=fg)
            y += 78
        if subtitle:
            draw.text((80, H - 110), subtitle, font=font_sub, fill=accent)

        img.save(out_path, "PNG")
        return out_path
    except Exception as exc:  # noqa: BLE001
        log.warning("画像生成失敗: %s", exc)
        return None


def _load_font(size: int):
    from PIL import ImageFont

    # 日本語フォント候補（環境にあれば使用、無ければデフォルト）
    candidates = [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/truetype/fonts-japanese-gothic.ttf",
        "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc",
    ]
    for path in candidates:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    return ImageFont.load_default()
