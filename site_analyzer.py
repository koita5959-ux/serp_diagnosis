# site_analyzer.py — 第3層：サイト性質の自動判定
import re
import json
import logging
import time
import requests
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup
import chardet

logger = logging.getLogger(__name__)

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
TIMEOUT = 10

# サイト内リンク数の上限（これ以下ならローカル企業規模）
SITE_LINK_THRESHOLD = 30

# 除外する拡張子
EXCLUDE_EXTENSIONS = re.compile(
    r'\.(pdf|zip|doc|docx|xls|xlsx|png|jpg|jpeg|gif|svg|css|js|mp3|mp4|wav|avi|mov)$', re.I
)

# 主要ページ候補のURLパスパターン
KEY_PAGE_PATTERNS = re.compile(
    r'(about|company|corporate|profile'
    r'|service|business|works|product'
    r'|access|map|contact|inquiry'
    r'|greeting|message|philosophy'
    r'|overview|gaiyou|kaisha)',
    re.I
)

# 都道府県名リスト（所在地検出用）
PREFECTURES = [
    "北海道", "青森県", "岩手県", "宮城県", "秋田県", "山形県", "福島県",
    "茨城県", "栃木県", "群馬県", "埼玉県", "千葉県", "東京都", "神奈川県",
    "新潟県", "富山県", "石川県", "福井県", "山梨県", "長野県",
    "岐阜県", "静岡県", "愛知県", "三重県",
    "滋賀県", "京都府", "大阪府", "兵庫県", "奈良県", "和歌山県",
    "鳥取県", "島根県", "岡山県", "広島県", "山口県",
    "徳島県", "香川県", "愛媛県", "高知県",
    "福岡県", "佐賀県", "長崎県", "熊本県", "大分県", "宮崎県", "鹿児島県", "沖縄県",
]


def get_domain(url):
    """URLからドメインを取得（www.を除去）"""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]
        return domain
    except Exception:
        return ""


def get_base_domain(url):
    """URLからベースドメインを取得（co.jp等を考慮）"""
    domain = get_domain(url) if "://" in url else url.lower()
    parts = domain.split(".")
    if len(parts) >= 3 and parts[-2] in ("co", "or", "ne", "ac", "go", "gr", "lg"):
        return ".".join(parts[-3:])
    elif len(parts) >= 2:
        return ".".join(parts[-2:])
    return domain


def is_same_site(url1, url2):
    """2つのURLが同一サイトか判定"""
    return get_base_domain(url1) == get_base_domain(url2)


def find_top_page(soup, hit_url):
    """
    ステップ1：ヒットページのHTMLからトップページURLを特定する。

    優先順：
    1. ヘッダーのロゴリンク
    2. パンくずリストの先頭リンク
    3. フォールバック：ドメインルート

    Returns: トップページのURL文字列
    """
    parsed = urlparse(hit_url)
    domain_root = f"{parsed.scheme}://{parsed.netloc}/"

    # 1. ヘッダーのロゴリンク
    header = soup.find("header")
    if header:
        # img を含む a タグ（ロゴリンク）を優先
        for a in header.find_all("a", href=True):
            if a.find("img"):
                href = a["href"]
                abs_url = urljoin(hit_url, href)
                if is_same_site(abs_url, hit_url):
                    return abs_url
        # ヘッダー内の最初のaタグ
        first_a = header.find("a", href=True)
        if first_a:
            href = first_a["href"]
            abs_url = urljoin(hit_url, href)
            if is_same_site(abs_url, hit_url):
                return abs_url

    # 2. パンくずリストの先頭リンク
    # 2a. nav内のol/li
    for nav in soup.find_all("nav"):
        ol = nav.find("ol")
        if ol:
            first_li = ol.find("li")
            if first_li:
                a = first_li.find("a", href=True)
                if a:
                    text = a.get_text(strip=True)
                    # 「ホーム」「トップ」「TOP」「Home」等
                    if any(kw in text for kw in ["ホーム", "トップ", "TOP", "Home", "HOME", "トップページ"]):
                        abs_url = urljoin(hit_url, a["href"])
                        if is_same_site(abs_url, hit_url):
                            return abs_url

    # 2b. 構造化データ BreadcrumbList
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
            items = []
            if isinstance(data, dict):
                if data.get("@type") == "BreadcrumbList":
                    items = data.get("itemListElement", [])
                for graph_item in data.get("@graph", []):
                    if isinstance(graph_item, dict) and graph_item.get("@type") == "BreadcrumbList":
                        items = graph_item.get("itemListElement", [])
            if items:
                # position=1の要素のURL
                for item in items:
                    if item.get("position") == 1:
                        item_obj = item.get("item", "")
                        if isinstance(item_obj, dict):
                            url = item_obj.get("@id", "")
                        else:
                            url = str(item_obj)
                        if url and is_same_site(url, hit_url):
                            return url
        except (ValueError, TypeError, KeyError):
            pass

    # 2c. aria-label="breadcrumb" 内の先頭リンク
    for elem in soup.find_all(attrs={"aria-label": lambda v: v and "breadcrumb" in v.lower()}):
        first_a = elem.find("a", href=True)
        if first_a:
            abs_url = urljoin(hit_url, first_a["href"])
            if is_same_site(abs_url, hit_url):
                return abs_url

    # 3. フォールバック
    return domain_root


def collect_internal_links(soup, source_url):
    """
    ページ内のサイト内リンク（同一ベースドメインへのリンク）を収集する。
    Returns: リンクURLのset
    """
    links = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith(("javascript:", "mailto:", "tel:", "#")):
            continue
        abs_url = urljoin(source_url, href)
        # フラグメント除去
        abs_url = abs_url.split("#")[0]
        if not abs_url.startswith(("http://", "https://")):
            continue
        if not is_same_site(abs_url, source_url):
            continue
        if EXCLUDE_EXTENSIONS.search(abs_url):
            continue
        links.add(abs_url)
    return links


def select_key_pages(links, top_url, max_pages=5):
    """
    トップページのリンクから主要ページを選定する。
    ナビゲーション系のパスパターンに合致するURLを優先。
    Returns: 選定されたURLのリスト（最大max_pages件）
    """
    scored = []
    for link in links:
        if link == top_url:
            continue
        path = urlparse(link).path.lower()
        score = 0
        if KEY_PAGE_PATTERNS.search(path):
            score += 5
        # 浅い階層を優先
        depth = len([p for p in path.strip("/").split("/") if p])
        if depth <= 1:
            score += 2
        elif depth <= 2:
            score += 1
        scored.append((score, link))

    scored.sort(key=lambda x: -x[0])
    return [url for _, url in scored[:max_pages]]


def fetch_page_safe(url):
    """
    URLにアクセスしてBeautifulSoupとテキストを返す。
    失敗時はNone, ""を返す。
    """
    try:
        response = requests.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=TIMEOUT,
            allow_redirects=True,
        )
        if response.status_code >= 400:
            return None, ""
        # 文字コード処理
        if response.encoding is None or response.encoding == "ISO-8859-1":
            detected = chardet.detect(response.content)
            encoding = detected.get("encoding", "utf-8")
            html_text = response.content.decode(encoding, errors="replace")
        else:
            html_text = response.text
        soup = BeautifulSoup(html_text, "html.parser")
        text = soup.get_text()
        return soup, text
    except Exception as e:
        logger.warning(f"第3層ページ取得失敗: {url} - {e}")
        return None, ""


def analyze_site(hit_url, hit_soup):
    """
    第3層のメイン関数。ヒットページのURL・soupから、サイト性質を判定する。

    Returns:
        dict: {
            "top_page_url": str,       # 特定したトップページURL
            "site_link_count": int,    # トップページのサイト内リンク数
            "site_type": str,          # "local_small" / "large_site"
            "has_location": bool,      # 所在地情報があるか
            "has_contact": bool,       # 問い合わせ手段があるか
            "has_company_page": bool,  # 会社概要ページがあるか
        }
    """
    result = {
        "top_page_url": None,
        "site_link_count": None,
        "site_type": None,
        "has_location": False,
        "has_contact": False,
        "has_company_page": False,
    }

    # ステップ1：トップページ特定
    top_url = find_top_page(hit_soup, hit_url)
    result["top_page_url"] = top_url

    # ステップ2：トップページにアクセスしてサイト内リンク数を取得
    time.sleep(2)  # アクセス間隔
    top_soup, top_text = fetch_page_safe(top_url)
    if not top_soup:
        # トップページ取得失敗 → 判定不能、site_type=None のまま返す
        return result

    internal_links = collect_internal_links(top_soup, top_url)
    result["site_link_count"] = len(internal_links)

    # サイト規模判定
    if len(internal_links) > SITE_LINK_THRESHOLD:
        result["site_type"] = "large_site"
        return result  # 大規模サイト → これ以上の分析は不要

    # ステップ3：主要ページにアクセスしてサイト分析
    result["site_type"] = "local_small"

    key_pages = select_key_pages(internal_links, top_url, max_pages=3)
    all_texts = [top_text]

    for page_url in key_pages:
        time.sleep(2)  # アクセス間隔
        _, page_text = fetch_page_safe(page_url)
        if page_text:
            all_texts.append(page_text)

    combined_text = "\n".join(all_texts)

    # 所在地情報の検出
    for pref in PREFECTURES:
        if pref in combined_text:
            result["has_location"] = True
            break

    # 問い合わせ手段の検出
    contact_keywords = [
        "お問い合わせ", "お問合せ", "問い合わせ",
        "contact", "inquiry",
        "TEL", "tel:", "電話番号",
    ]
    for kw in contact_keywords:
        if kw in combined_text or kw.lower() in combined_text.lower():
            result["has_contact"] = True
            break

    # 会社概要ページの有無
    company_patterns = ["会社概要", "about", "company", "企業情報"]
    for link in internal_links:
        path = urlparse(link).path.lower()
        for pat in company_patterns:
            if pat in path:
                result["has_company_page"] = True
                break
        if result["has_company_page"]:
            break
    # テキスト内にも「会社概要」があれば検出
    if not result["has_company_page"] and "会社概要" in combined_text:
        result["has_company_page"] = True

    return result
