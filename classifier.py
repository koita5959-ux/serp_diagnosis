# classifier.py — 分類判定ロジック
from urllib.parse import urlparse
from config import PORTAL_DOMAINS, NEWS_DOMAINS, SEO_THRESHOLDS

# 公共系ドメインのサフィックス
PUBLIC_SUFFIXES = [".go.jp", ".lg.jp"]
PUBLIC_DOMAINS = ["wikipedia.org"]


def classify(result):
    """
    検索結果を分類する。優先順位に従い、先に該当したものが優先。

    Returns:
        str: "広告" / "ポータル・大手" / "その他（公共系）" / "その他（メディア）" /
             "企業HP（SEOあり）" / "企業HP（SEOなし）"
    """
    # 1. 広告
    if result.get("is_ad"):
        return "広告"

    url = result.get("url", "")
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]
    except Exception:
        domain = ""

    # 2. ポータル・大手
    for portal in PORTAL_DOMAINS:
        if domain == portal or domain.endswith("." + portal):
            return "ポータル・大手"

    # 3. その他（公共系）
    for suffix in PUBLIC_SUFFIXES:
        if domain.endswith(suffix):
            return "その他（公共系）"
    for pub_domain in PUBLIC_DOMAINS:
        if domain == pub_domain or domain.endswith("." + pub_domain):
            return "その他（公共系）"

    # 4. その他（メディア）
    for news in NEWS_DOMAINS:
        if domain == news or domain.endswith("." + news):
            return "その他（メディア）"

    # 5. 企業HP（SEOあり）
    has_meta = result.get("has_meta_desc") and (result.get("meta_desc_length", 0) or 0) >= SEO_THRESHOLDS["meta_desc_min_length"]
    has_structured = result.get("has_structured_data")
    has_ogp = result.get("has_ogp")

    if has_meta and (has_structured or has_ogp):
        return "企業HP（SEOあり）"

    # 6. 企業HP（SEOなし）
    return "企業HP（SEOなし）"
