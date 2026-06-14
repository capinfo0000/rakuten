"""アフィリンク生成の抽象層。

provider を設定で切替:
  - rakuten_direct : Item Search が返す affiliateUrl をそのまま使う
  - moshimo        : もしものクリック計測リンクで商品URLをラップ

go.php もこの仕様（最終的な遷移先URL）に従う。新ASPは Provider を足すだけ。
"""
from __future__ import annotations

from urllib.parse import quote, urlparse

from src.common.config import env
from src.common.log import get_logger

log = get_logger("affiliate")

# go.php が外部リダイレクトを許可するドメイン（オープンリダイレクト対策）
ALLOWED_HOSTS = (
    "rakuten.co.jp", "hb.afl.rakuten.co.jp", "a.r10.to",
    "af.moshimo.com", "amazon.co.jp", "amzn.to",
    "shopping.yahoo.co.jp", "store.shopping.yahoo.co.jp",
)


def is_allowed_url(url: str) -> bool:
    """許可ドメインのみ True。go.php の安全リダイレクト判定と同じ思想。"""
    try:
        host = (urlparse(url).hostname or "").lower()
    except ValueError:
        return False
    return any(host == h or host.endswith("." + h) for h in ALLOWED_HOSTS)


class RakutenDirectProvider:
    name = "rakuten_direct"

    def build(self, *, rakuten_url: str, affiliate_url: str, **_: str) -> str:
        # Item Search が affiliateId 付きで返した affiliateUrl を優先
        return affiliate_url or rakuten_url


class MoshimoProvider:
    """もしものクリック計測リンク。

    形式: https://af.moshimo.com/af/c/click?a_id=..&p_id=..&pc_id=..&pl_id=..&url=<遷移先>
    各プロモーション(楽天/Amazon/Yahoo)ごとに p_id/pc_id/pl_id が異なる。
    """

    name = "moshimo"
    BASE = "https://af.moshimo.com/af/c/click"

    def _wrap(self, dest_url: str, p_id: str, pc_id: str, pl_id: str) -> str:
        a_id = env("MOSHIMO_A_ID", "")
        if not (a_id and p_id and pc_id and pl_id):
            log.warning("もしものID未設定のため遷移先URLを直接返します")
            return dest_url
        return (f"{self.BASE}?a_id={a_id}&p_id={p_id}&pc_id={pc_id}"
                f"&pl_id={pl_id}&url={quote(dest_url, safe='')}")

    def build(self, *, rakuten_url: str, affiliate_url: str, merchant: str = "rakuten",
              **_: str) -> str:
        merchant = merchant.lower()
        dest = rakuten_url or affiliate_url
        p = env(f"MOSHIMO_{merchant.upper()}_P_ID", "")
        pc = env(f"MOSHIMO_{merchant.upper()}_PC_ID", "")
        pl = env(f"MOSHIMO_{merchant.upper()}_PL_ID", "")
        return self._wrap(dest, p, pc, pl)


_PROVIDERS = {p.name: p for p in (RakutenDirectProvider(), MoshimoProvider())}


def get_provider(name: str | None = None):
    name = name or env("AFFILIATE_PROVIDER", "rakuten_direct")
    return _PROVIDERS.get(name, _PROVIDERS["rakuten_direct"])


def affiliate_link(*, rakuten_url: str, affiliate_url: str = "",
                   merchant: str = "rakuten", provider: str | None = None) -> str:
    """設定された provider で最終アフィリンクを返す。"""
    return get_provider(provider).build(
        rakuten_url=rakuten_url, affiliate_url=affiliate_url, merchant=merchant)
