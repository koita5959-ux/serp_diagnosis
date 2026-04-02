# classifier.py — 分類判定ロジック
import logging
from urllib.parse import urlparse
from config import (
    PORTAL_DOMAINS, MAJOR_DOMAINS, SEO_THRESHOLDS,
    VIDEO_DOMAINS, QA_DOMAINS, SNS_DOMAINS, BLOG_DOMAINS, MEDIA_DOMAINS,
)
from site_analyzer import analyze_site

logger = logging.getLogger(__name__)

# 公共系ドメインのサフィックス
PUBLIC_SUFFIXES = [".go.jp", ".lg.jp"]
PUBLIC_DOMAINS = ["wikipedia.org"]


def judge_column(result):
    """
    第2層：コラム判定。
    analyzer.pyで取得した解析結果を元に、コラムページかどうかを判定する。

    Returns:
        tuple: (is_column: bool, reason: str or None)
        reason: "url_path" / "breadcrumb" / "cms_structure" / None
    """
    cms = result.get("cms_detected")
    url_path_kw = result.get("url_path_keywords", [])
    breadcrumb_kw = result.get("breadcrumb_keywords", [])
    text_length = result.get("page_text_length", 0) or 0
    heading_count = result.get("heading_count", 0) or 0
    text_depth = result.get("text_depth", 0) or 0

    # EC系CMSはコラムではない（第3層の「その他」候補）
    if cms in ("Shopify", "BASE"):
        return False, None

    # 条件1：URLパスにキーワードあり＋テキスト2,000文字以上
    if url_path_kw and text_length >= 2000:
        return True, "url_path"

    # 条件2：パンくずにキーワードあり＋テキスト2,000文字以上
    if breadcrumb_kw and text_length >= 2000:
        return True, "breadcrumb"

    # 条件3：CMS指紋あり（Shopify/BASE除外済み）＋テキスト2,000文字以上
    #         ＋見出しタグ4個以上＋テキスト集中階層が深い（5以上）
    if cms and text_length >= 2000 and heading_count >= 4 and text_depth >= 5:
        return True, "cms_structure"

    return False, None


def classify(result):
    """
    検索結果を分類する。優先順位に従い、先に該当したものが優先。

    Returns:
        str: "広告" / "ポータル" / "大手" / "その他" /
             "企業HP（SEOあり）" / "企業HP（SEOなし）"
    """
    # 1. 広告
    if result.get("is_ad"):
        return "広告"

    url = result.get("url", "")

    # 1.5 HTML取得失敗 → 判定不能のため「その他」
    site_status = result.get("site_status", "")
    if site_status in ("timeout", "blocked", "error"):
        return "その他"

    # 1.6 PDF → サイト分析対象外のため「その他」
    if url.lower().endswith(".pdf"):
        return "その他"

    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]
    except Exception:
        domain = ""

    # 2. ポータル
    for portal in PORTAL_DOMAINS:
        if domain == portal or domain.endswith("." + portal):
            return "ポータル"

    # 3. 大手
    for major in MAJOR_DOMAINS:
        if domain == major or domain.endswith("." + major):
            return "大手"

    # 4. その他（ポータル・大手判定の直後、企業HP判定の前）

    # 4-1. 公共系
    for suffix in PUBLIC_SUFFIXES:
        if domain.endswith(suffix):
            return "その他"
    for pub_domain in PUBLIC_DOMAINS:
        if domain == pub_domain or domain.endswith("." + pub_domain):
            return "その他"

    # 4-2. 動画プラットフォーム
    for d in VIDEO_DOMAINS:
        if domain == d or domain.endswith("." + d):
            return "その他"

    # 4-3. QA・掲示板
    for d in QA_DOMAINS:
        if domain == d or domain.endswith("." + d):
            return "その他"

    # 4-4. SNS
    for d in SNS_DOMAINS:
        if domain == d or domain.endswith("." + d):
            return "その他"

    # 4-5. ブログプラットフォーム
    for d in BLOG_DOMAINS:
        if domain == d or domain.endswith("." + d):
            return "その他"

    # 4-6. まとめ・比較メディア
    for d in MEDIA_DOMAINS:
        if domain == d or domain.endswith("." + d):
            return "その他"

    # ===== 第2層：コラム判定 =====
    is_column, column_reason = judge_column(result)
    if is_column:
        # result dictに判定結果を格納（DB保存用）
        result["is_column_page"] = True
        result["column_reason"] = column_reason
        return "コラム"

    # ===== 第3層：サイト性質の自動判定 =====
    soup = result.get("soup")
    if soup:
        try:
            site_info = analyze_site(url, soup)
            result["top_page_url"] = site_info["top_page_url"]
            result["site_link_count"] = site_info["site_link_count"]
            result["site_type"] = site_info["site_type"]

            # 大規模サイト → その他
            if site_info["site_type"] == "large_site":
                return "その他"

            # EC系CMS検出済み → その他
            if result.get("cms_detected") in ("Shopify", "BASE"):
                return "その他"

        except Exception as e:
            logger.warning(f"第3層分析エラー: {url} - {e}")
            # 第3層エラー時は従来の判定にフォールバック

    # 5. 企業HP（SEOあり）
    has_meta = result.get("has_meta_desc") and (result.get("meta_desc_length", 0) or 0) >= SEO_THRESHOLDS["meta_desc_min_length"]
    has_structured = result.get("has_structured_data")
    # OGPのみではSEO対策と判定しない
    if has_meta and has_structured:
        return "企業HP（SEOあり）"

    # 6. 企業HP（SEOなし）
    return "企業HP（SEOなし）"
