"""静的サイト生成（Jinja2）。data/site/ に出力 → deploy で public_html へ。

各商品ページ: 価格推移＋3社比較ボックス＋PR表記＋免責文＋JSON-LD。
アフィリンクは link_id を発行して go.php 経由（?src= で流入元識別）。
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from src.affiliate.comparebox import compare_box
from src.common.config import REPO_ROOT, env, load_config
from src.common.log import get_logger
from src.pdca.store import Store
from src.rakuten.client import Item
from src.tracker.price import DISCLAIMER

log = get_logger("publish.site")

TEMPLATE_DIR = REPO_ROOT / "src" / "content" / "templates"
SITE_DIR = REPO_ROOT / "data" / "site"
SPARK_CHARS = "▁▂▃▄▅▆▇█"


def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=select_autoescape(["html", "xml"]),
    )


def _sparkline(series: list[dict]) -> str:
    prices = [p["price"] for p in series if p.get("price")]
    if len(prices) < 2:
        return ""
    lo, hi = min(prices), max(prices)
    span = (hi - lo) or 1
    return "".join(SPARK_CHARS[int((p - lo) / span * (len(SPARK_CHARS) - 1))] for p in prices)


def _link_id(item_code: str, merchant: str) -> str:
    return hashlib.sha1(f"{item_code}:{merchant}".encode()).hexdigest()[:12]


class SiteBuilder:
    def __init__(self, store: Store, config: dict | None = None) -> None:
        self.store = store
        self.cfg = config or load_config()
        self.env = _env()
        self.base_url = env("SITE_BASE_URL", self.cfg["site"]["base_url"]).rstrip("/")
        self.site_ctx = {
            "name": env("SITE_NAME", self.cfg["site"]["name"]),
            "description": self.cfg["site"]["description"],
            "operator": env("SITE_OPERATOR", "運営者"),
        }
        SITE_DIR.mkdir(parents=True, exist_ok=True)

    def _write(self, rel: str, html: str) -> Path:
        path = SITE_DIR / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(html, encoding="utf-8")
        return path

    def build_deal_page(self, item: Item, *, headline: str = "", summary: str = "",
                        buy_guide: str = "", prev_price: int | None = None,
                        src: str = "web") -> dict:
        slug = f"deal/{item.item_code.replace(':', '-').replace('/', '-')}"
        compare = compare_box(item)
        link_ids: dict[str, str] = {}
        for c in compare:
            lid = _link_id(item.item_code, c["merchant"])
            self.store.register_link(lid, c["url"], item.item_code)
            link_ids[c["merchant"]] = lid

        series = self.store.price_series(item.item_code)
        json_ld = json.dumps({
            "@context": "https://schema.org", "@type": "Product",
            "name": item.name, "image": item.image_url,
            "aggregateRating": ({
                "@type": "AggregateRating", "ratingValue": item.review_average,
                "reviewCount": item.review_count} if item.review_count else None),
            "offers": {"@type": "Offer", "price": item.price,
                       "priceCurrency": "JPY",
                       "availability": "https://schema.org/InStock" if item.availability
                       else "https://schema.org/OutOfStock"},
        }, ensure_ascii=False)

        title = headline or f"{item.name} の価格・在庫・買い時"
        html = self.env.get_template("deal.html").render(
            site=self.site_ctx, title=title, headline=headline,
            description=(summary or title)[:120],
            canonical=f"{self.base_url}/{slug}.html",
            og_image=item.image_url, json_ld=json_ld, disclaimer=DISCLAIMER,
            item=item.to_row(), compare=compare, link_ids=link_ids,
            go_base=self.base_url, src=src, series=series,
            spark=_sparkline(series), summary=summary, buy_guide=buy_guide,
            prev_price=prev_price,
        )
        self._write(f"{slug}.html", html)
        self.store.upsert_page(slug, "deal", title, item.item_code)
        return {"slug": slug, "title": title, "headline": headline}

    def build_index(self, pages: list[dict], sale_label: str = "") -> None:
        html = self.env.get_template("index.html").render(
            site=self.site_ctx, title=self.site_ctx["name"],
            description=self.site_ctx["description"],
            canonical=f"{self.base_url}/", disclaimer=DISCLAIMER,
            pages=pages, sale_label=sale_label, json_ld="", og_image="",
        )
        self._write("index.html", html)

    def build_sitemap_and_feed(self, pages: list[dict]) -> None:
        self._write("sitemap.xml", self.env.get_template("sitemap.xml").render(
            base_url=self.base_url, pages=pages))
        self._write("feed.xml", self.env.get_template("feed.xml").render(
            site=self.site_ctx, base_url=self.base_url, pages=pages))

    def build_static_pages(self) -> None:
        """about / privacy（E-E-A-T・法対応）。"""
        for slug, title, body in [
            ("about", "運営者情報",
             f"<h1>運営者情報</h1><p>運営者: {self.site_ctx['operator']}</p>"
             "<p>本サイトは楽天・もしもアフィリエイト等のプログラムにより収益を得ています。</p>"),
            ("privacy", "プライバシーポリシー",
             "<h1>プライバシーポリシー</h1><p>当サイトはアクセス解析(GA4)とCookieを"
             "利用します。アフィリエイトリンクのクリックは効果測定のため記録されます。</p>"),
        ]:
            rendered = self.env.get_template("base.html").render(
                site=self.site_ctx, title=title, description=title,
                canonical=f"{self.base_url}/{slug}.html", disclaimer=DISCLAIMER,
                json_ld="", og_image="",
            )
            # base単体は content ブロックが空 → 本文を disclaimer の前に差し込む
            html = rendered.replace('<p class="disclaimer">', body + '\n<p class="disclaimer">', 1)
            self._write(f"{slug}.html", html)
