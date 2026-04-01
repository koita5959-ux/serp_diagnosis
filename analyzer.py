# analyzer.py — URL先のサイト情報取得
import json
import time
import logging
import requests
from urllib.parse import urlparse
from bs4 import BeautifulSoup
import chardet

logger = logging.getLogger(__name__)

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
TIMEOUT = 10
ACCESS_INTERVAL = 2


def detect_cms(soup, html_text):
    """
    HTMLソースからCMSの指紋を検出する。
    Returns: CMS名の文字列。未検出ならNone。
    """
    html_lower = html_text.lower()

    # WordPress
    if "wp-content" in html_lower or "wp-includes" in html_lower:
        return "WordPress"
    meta_gen = soup.find("meta", attrs={"name": "generator"})
    if meta_gen and meta_gen.get("content", "").lower().startswith("wordpress"):
        return "WordPress"

    # Wix
    if "wix.com" in html_lower:
        return "Wix"

    # Jimdo
    if "jimdo" in html_lower:
        return "Jimdo"

    # はてなブログ
    if "hatenablog" in html_lower:
        return "Hatena"

    # Shopify
    if "cdn.shopify.com" in html_lower:
        return "Shopify"

    # BASE
    if "thebase.in" in html_lower:
        return "BASE"

    return None


def detect_url_path_keywords(url):
    """
    URLのパス部分からコラム系キーワードを検出する。
    Returns: 検出されたキーワードのリスト。
    """
    path = urlparse(url).path.lower()
    keywords = [
        "/column/", "/columns/",
        "/blog/", "/blogs/",
        "/article/", "/articles/",
        "/magazine/",
        "/media/",
        "/news/",
        "/journal/",
        "/tips/",
        "/guide/",
        "/howto/",
        "/knowledge/",
        "/info/",
        "/useful/",
    ]
    found = [kw.strip("/") for kw in keywords if kw in path]
    return found


def detect_breadcrumb_keywords(soup):
    """
    パンくずリストからコラム系キーワードを検出する。
    検出対象：nav内のol/li構造、および構造化データBreadcrumbList。
    Returns: 検出されたキーワードのリスト。
    """
    breadcrumb_texts = []

    # 1. nav内のol/liからテキスト取得
    for nav in soup.find_all("nav"):
        ol = nav.find("ol")
        if ol:
            for li in ol.find_all("li"):
                text = li.get_text(strip=True)
                if text:
                    breadcrumb_texts.append(text)

    # 2. 構造化データ（BreadcrumbList）
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
            if isinstance(data, dict):
                if data.get("@type") == "BreadcrumbList":
                    for item in data.get("itemListElement", []):
                        name = item.get("name", "")
                        if name:
                            breadcrumb_texts.append(name)
                # @graphの中にBreadcrumbListがある場合
                for graph_item in data.get("@graph", []):
                    if isinstance(graph_item, dict) and graph_item.get("@type") == "BreadcrumbList":
                        for item in graph_item.get("itemListElement", []):
                            name = item.get("name", "")
                            if name:
                                breadcrumb_texts.append(name)
        except (ValueError, TypeError, KeyError):
            pass

    # 3. aria-label="breadcrumb" or class名にbreadcrumb
    for elem in soup.find_all(attrs={"aria-label": lambda v: v and "breadcrumb" in v.lower()}):
        for li in elem.find_all("li"):
            text = li.get_text(strip=True)
            if text:
                breadcrumb_texts.append(text)

    # キーワード照合
    column_keywords = [
        "コラム", "ブログ", "お役立ち", "お知らせ", "記事",
        "読みもの", "マガジン", "ニュース", "豆知識", "基礎知識",
    ]
    found = []
    for bc_text in breadcrumb_texts:
        for kw in column_keywords:
            if kw in bc_text and kw not in found:
                found.append(kw)
    return found


def count_headings(soup):
    """h2 + h3タグの合計数を返す。"""
    h2_count = len(soup.find_all("h2"))
    h3_count = len(soup.find_all("h3"))
    return h2_count + h3_count


def measure_text_depth(soup):
    """
    DOM構造で最もテキスト量が多い要素のネスト深さを返す。
    bodyタグからの深さを測定。
    """
    max_depth = 0
    max_text_len = 0

    def _get_depth(element):
        depth = 0
        parent = element.parent
        while parent and parent.name != "[document]":
            depth += 1
            parent = parent.parent
        return depth

    # テキストを直接持つ要素（p, div, span, td, li等）を対象
    text_tags = ["p", "div", "span", "td", "li", "article", "section"]
    for tag in soup.find_all(text_tags):
        # 直下テキストのみ（子要素のテキストを除外）
        direct_text = "".join(
            t.strip() for t in tag.find_all(string=True, recursive=False)
        )
        text_len = len(direct_text)
        if text_len > max_text_len:
            max_text_len = text_len
            max_depth = _get_depth(tag)

    return max_depth


def count_outer_links(soup):
    """
    テキスト集中エリア外のaタグ数を返す。
    mainタグまたはarticleタグを本文エリアとし、その外側のリンク数を数える。
    """
    # 本文エリアの特定
    main_area = soup.find("main") or soup.find("article")

    if main_area:
        # 全リンク数から本文エリア内リンク数を引く
        total_links = len(soup.find_all("a", href=True))
        main_links = len(main_area.find_all("a", href=True))
        return total_links - main_links
    else:
        # main/articleが無い場合は判定不能、0を返す
        return 0


def analyze_url(url: str) -> dict:
    """
    URLにアクセスしてSEO関連情報を取得する。

    Returns:
        dict: {
            "has_meta_desc": bool,
            "meta_desc_length": int,
            "has_structured_data": bool,
            "has_ogp": bool,
            "page_text_length": int,
            "site_status": str,  # "OK" / "error" / "blocked" / "timeout"
        }
    """
    result = {
        "has_meta_desc": False,
        "meta_desc_length": 0,
        "has_structured_data": False,
        "has_ogp": False,
        "page_text_length": 0,
        "site_status": "error",
        "soup": None,
        "cms_detected": None,
        "is_column_page": False,
        "column_reason": None,
        "url_path_keywords": [],
        "breadcrumb_keywords": [],
        "heading_count": 0,
        "text_depth": 0,
        "outer_link_count": 0,
    }

    try:
        response = requests.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=TIMEOUT,
            allow_redirects=True,
        )

        if response.status_code == 403:
            result["site_status"] = "blocked"
            return result
        elif response.status_code >= 400:
            result["site_status"] = "error"
            return result

        result["site_status"] = "OK"

        # 文字コード検出
        if response.encoding is None or response.encoding == "ISO-8859-1":
            detected = chardet.detect(response.content)
            encoding = detected.get("encoding", "utf-8")
            html_text = response.content.decode(encoding, errors="replace")
        else:
            html_text = response.text

        soup = BeautifulSoup(html_text, "html.parser")

        # meta description
        meta_desc = soup.find("meta", attrs={"name": "description"})
        if meta_desc and meta_desc.get("content"):
            result["has_meta_desc"] = True
            result["meta_desc_length"] = len(meta_desc["content"])

        # 構造化データ（JSON-LD）
        structured_data = soup.find_all("script", type="application/ld+json")
        if len(structured_data) >= 1:
            result["has_structured_data"] = True

        # OGP設定
        ogp_title = soup.find("meta", property="og:title")
        if ogp_title:
            result["has_ogp"] = True

        # ページ文字量
        text = soup.get_text()
        result["page_text_length"] = len(text)

        # --- 第2層用の解析（追加ここから） ---
        result["soup"] = soup
        result["cms_detected"] = detect_cms(soup, html_text)
        result["url_path_keywords"] = detect_url_path_keywords(url)
        result["breadcrumb_keywords"] = detect_breadcrumb_keywords(soup)
        result["heading_count"] = count_headings(soup)
        result["text_depth"] = measure_text_depth(soup)
        result["outer_link_count"] = count_outer_links(soup)
        # --- 第2層用の解析（追加ここまで） ---

    except requests.exceptions.Timeout:
        result["site_status"] = "timeout"
        logger.warning(f"タイムアウト: {url}")
    except Exception as e:
        result["site_status"] = "error"
        logger.warning(f"取得失敗: {url} - {e}")

    return result


def analyze_urls(urls: list[str]) -> list[dict]:
    """
    複数URLをアクセス間隔を空けながら分析する。
    """
    results = []
    for i, url in enumerate(urls):
        if i > 0:
            time.sleep(ACCESS_INTERVAL)
        result = analyze_url(url)
        results.append(result)
    return results
