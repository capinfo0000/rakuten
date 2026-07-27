"""1サイクルの統括（Plan + Do）と、トレンドスイープ。"""
from __future__ import annotations

from src.common.config import env, load_config
from src.common.log import get_logger
from src.content import generator
from src.eventcal.events import sale_status
from src.pdca.store import Store
from src.publish.site_builder import SiteBuilder
from src.publish.social import broadcast, build_posters
from src.rakuten.client import RakutenClient
from src.rakuten.selector import rank_items
from src.tracker import price as tracker
from src.trends import radar, sources, mapper

log = get_logger("pipeline")


def build_client(mock: bool = False):
    if mock:
        from src.rakuten.mock import MockRakutenClient
        return MockRakutenClient()
    app_id = env("RAKUTEN_APP_ID")
    if not app_id:
        raise SystemExit("RAKUTEN_APP_ID 未設定。--mock を使うか .env を設定してください。")
    return RakutenClient(app_id, env("RAKUTEN_AFFILIATE_ID"))


def _collect_candidates(client, niches: list[dict]) -> list:
    items: dict[str, object] = {}
    for niche in niches:
        for kw in niche.get("keywords", []):
            for it in client.search(keyword=kw, hits=10):
                items[it.item_code] = it
        gid = niche.get("genre_id")
        if gid:
            for it in client.ranking(genre_id=gid):
                items[it.item_code] = it
    return list(items.values())


def run_cycle(client, store: Store, config: dict | None = None,
              dry_run: bool = False) -> dict:
    config = config or load_config()
    sale = sale_status()
    weights = config.get("score_weights", {})
    builder = SiteBuilder(store, config)
    posters = build_posters(store, config, dry_run=dry_run)
    drop_pct = config.get("tracking", {}).get("drop_alert_pct", 5.0)
    limit = config.get("site", {}).get("posts_per_run", 20)

    candidates = _collect_candidates(client, config.get("niches", []))
    scored = rank_items(candidates, weights, sale)
    log.info("候補%s件 → 上位%s件を採用", len(candidates), min(limit, len(scored)))

    pages: list[dict] = []
    for item, score in scored[:limit]:
        row = item.to_row()
        row["score"] = round(score, 4)
        store.upsert_product(row)
        event = tracker.snapshot(store, item, drop_alert_pct=drop_pct)

        headline = ""
        summary = ""
        prev_price = None
        if event and event["kind"] == "price_drop":
            prev_price = event["prev_price"]
            headline = f"{event['drop_pct']:.0f}%値下げ: {item.name[:24]}"
            summary = generator.price_drop_summary(
                item.name, prev_price, item.price, event["drop_pct"])
        buy_guide = generator.buy_timing_guide(item.name, sale.label) if sale.active else ""

        page = builder.build_deal_page(
            item, headline=headline, summary=summary, buy_guide=buy_guide,
            prev_price=prev_price, src="web")
        page["headline"] = headline
        pages.append(page)

        # 値下げ等の notable イベントのみ X 速報（上限内・文面バリエーション）
        if event:
            url = f"{builder.base_url}/{page['slug']}.html"
            text = generator.x_post_text(item.name, headline or event["detail"],
                                         url, sale.label)
            broadcast(posters, text, page["slug"], image_path=page.get("image_path"))

    builder.build_index(pages, sale_label=sale.label)
    builder.build_sitemap_and_feed(pages)
    builder.build_static_pages()
    log.info("サイクル完了: %sページ生成 (%s)", len(pages), sale.label)
    return {"pages": len(pages), "sale": sale.label}


def run_trend_sweep(client, store: Store, config: dict | None = None,
                    dry_run: bool = False) -> dict:
    """高頻度: 急上昇検知→換金可能なら速報ページ＋X投稿を即応。"""
    config = config or load_config()
    tcfg = config.get("trends", {})
    sale = sale_status()
    builder = SiteBuilder(store, config)
    posters = build_posters(store, config, dry_run=dry_run)

    genre_ids = [n["genre_id"] for n in config.get("niches", []) if n.get("genre_id")]
    keywords = [k for n in config.get("niches", []) for k in n.get("keywords", [])]

    signals = sources.rakuten_rising(client, genre_ids)
    signals += sources.google_trends(keywords)
    signals += sources.yahoo_realtime()

    hits = radar.detect(store, signals, max_items=tcfg.get("max_trend_items", 10))
    mapped = mapper.map_to_products(client, hits)

    pages: list[dict] = []
    for hit, items in mapped:
        item = items[0]
        store.upsert_product(item.to_row())
        tracker.snapshot(store, item)
        headline = f"急上昇: {hit.term}"
        page = builder.build_deal_page(item, headline=headline, src="x")
        pages.append(page)
        url = f"{builder.base_url}/{page['slug']}.html"
        text = generator.x_post_text(item.name, f"いま話題: {hit.term}", url, sale.label)
        broadcast(posters, text, page["slug"], image_path=page.get("image_path"))

    log.info("トレンドスイープ完了: 検知%s / 採用%s", len(hits), len(pages))
    return {"trends": len(hits), "pages": len(pages)}
