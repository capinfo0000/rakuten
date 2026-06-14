"""OGP/X用画像のローカル生成（Pillow・無料・ブラウザ不要）。

Canvaブリーフ（濃紺#0f172a背景・赤#dc2626アクセント・価格強調・PR表記）と同じ
ブランドでローカル生成し、無人ランタイムを承認なしで完結させる。
凝った素材を別途Canvaで作る場合は assets/ogp_base.png を置けば背景に使う。
Pillow未導入でもNoneでスキップ（フェイルソフト）。
"""
from __future__ import annotations

import textwrap
from pathlib import Path

from src.common.config import REPO_ROOT
from src.common.log import get_logger

log = get_logger("content.image")

W, H = 1200, 630  # OGP標準

# ブランドトークン（base.html のCSS変数と対応）
NAVY = (15, 23, 42)
NAVY_2 = (30, 41, 59)
ACCENT = (220, 38, 38)
WHITE = (255, 255, 255)
MUTED = (148, 163, 184)

# 任意のブランド背景（Canva等で用意したら配置）
BRAND_BG = REPO_ROOT / "assets" / "ogp_base.png"


def make_card(title: str, out_path: Path, *, price: int | None = None,
              old_price: int | None = None, badge: str = "値下げ速報",
              site_name: str = "トレンド価格ウォッチ") -> Path | None:
    """ブランドOGP/Xカードを生成。失敗時 None（フェイルソフト）。"""
    try:
        from PIL import Image, ImageDraw
    except Exception as exc:  # noqa: BLE001
        log.warning("Pillow未導入のため画像生成スキップ: %s", exc)
        return None

    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        img = _base_image(Image)
        draw = ImageDraw.Draw(img)

        f_badge = _load_font(30)
        f_title = _load_font(52)
        f_price = _load_font(88)
        f_old = _load_font(38)
        f_foot = _load_font(26)

        # 左の赤アクセントバー
        draw.rectangle([0, 0, 18, H], fill=ACCENT)

        # バッジ（値下げ速報 等）
        bx, by = 80, 70
        bw = 24 + len(badge) * f_badge.size
        draw.rounded_rectangle([bx, by, bx + bw, by + 50], radius=8, fill=ACCENT)
        draw.text((bx + 14, by + 8), badge, font=f_badge, fill=WHITE)

        # タイトル（最大3行）
        y = 160
        for line in textwrap.wrap(title, width=18)[:3]:
            draw.text((80, y), line, font=f_title, fill=WHITE)
            y += 72

        # 価格エリア（強調）
        if price is not None:
            py = max(y + 20, 420)
            draw.text((80, py), f"{price:,}円", font=f_price, fill=ACCENT)
            if old_price and old_price > price:
                pw = draw.textlength(f"{price:,}円", font=f_price)
                draw.text((80 + pw + 30, py + 36), f"{old_price:,}円",
                          font=f_old, fill=MUTED)
                # 取り消し線
                ow = draw.textlength(f"{old_price:,}円", font=f_old)
                ly = py + 36 + f_old.size // 2
                draw.line([80 + pw + 30, ly, 80 + pw + 30 + ow, ly], fill=MUTED, width=3)

        # フッター: サイト名 + PR表記（ステマ規制）
        draw.text((80, H - 70), site_name, font=f_foot, fill=WHITE)
        pr = "PR・アフィリエイト"
        prw = draw.textlength(pr, font=f_foot)
        draw.text((W - prw - 80, H - 70), pr, font=f_foot, fill=MUTED)

        img.save(out_path, "PNG")
        return out_path
    except Exception as exc:  # noqa: BLE001
        log.warning("画像生成失敗: %s", exc)
        return None


def _base_image(Image):
    """ブランド背景があれば使用、無ければ縦グラデーション風の単色2分割。"""
    if BRAND_BG.exists():
        try:
            return Image.open(BRAND_BG).convert("RGB").resize((W, H))
        except OSError:
            pass
    img = Image.new("RGB", (W, H), NAVY)
    # 下部をわずかに明るくして奥行きを出す
    band = Image.new("RGB", (W, H // 3), NAVY_2)
    img.paste(band, (0, H - H // 3))
    return img


def _load_font(size: int):
    from PIL import ImageFont

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
