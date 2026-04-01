# 制作指示書：SERP診断ツール 3層判定設計 Phase2
**スクレイピングPj → Claude Code｜2026年4月1日**

---

## 0. 本指示書の読み方

本指示書は上から順番に読み、ステップ1から順に実行すること。
各ステップの完了条件を満たしてから次に進むこと。
不明点があれば実装前に質問すること。

---

## 1. 概要

### 1.1 目的
SERP診断ツールの分類精度を改善する。現在のドメインリスト依存（第1層）に加え、第2層（コラム判定）と第3層（サイト性質の自動判定）を追加する。

### 1.2 分類フロー
```
検索結果のURL
    │
    ▼
【第1層】ドメインパターン判定（変更なし）
    │ config.pyのリストで判定
    │ → 広告 / ポータル / 大手 / その他 → 確定
    │
    ▼ リストに該当しないURL
【第2層】コラム判定（★新設）
    │ ヒットページのHTML解析で判定
    │ → コラム → 確定
    │
    ▼ コラムにも該当しないURL
【第3層】サイト性質の自動判定（★新設）
    │ トップページ特定 → サイト規模判定 → 主要ページ分析
    │ → 企業HP（SEOあり）/ 企業HP（SEOなし）/ その他
    │
    ▼
分類確定 → DB保存
```

### 1.3 プロジェクトパス
```
/home/adminterml1/services/scraping/serp_diagnosis/
```

### 1.4 参考コード
```
/home/adminterml1/services/scraping/url_survey/site_check.py
```
※ importしてはならない。技術を参考にして新たに実装する。

---

## 2. ステップ1：把握レポート

以下のフォーマットで理解内容を出力すること。「把握しました」だけで進めないこと。

```
【把握レポート】
3層判定設計の全体像の理解：
  （第1層→第2層→第3層のフローを自分の言葉で説明）
第2層（コラム判定）の理解：
  （7つの材料と3つの条件を列挙）
第3層（サイト性質の自動判定）の理解：
  （3ステップの流れを説明）
トップページ特定の方針：
  （ロゴリンク→パンくず→フォールバックの3段階を説明）
修正対象ファイル：
  （全ファイル名を列挙）
新規ファイル：
  （作成するファイル名と役割）
DB変更の内容：
  （追加カラム名と型を列挙）
懸念点：
  （あれば記載）
```

---

## 3. ステップ2：バックアップ

以下のコマンドを**そのまま**実行すること。

```bash
cd /home/adminterml1/services/scraping/serp_diagnosis/
cp analyzer.py analyzer.py.bak_phase2
cp classifier.py classifier.py.bak_phase2
cp config.py config.py.bak_phase2
cp database.py database.py.bak_phase2
cp app.py app.py.bak_phase2
cp templates/results.html templates/results.html.bak_phase2
cp static/style.css static/style.css.bak_phase2
```

---

## 4. ステップ3：DB変更（database.py）

### 4.1 resultsテーブルへのカラム追加

`init_db()`関数内のCREATE TABLE文に以下のカラムを追加する。

```sql
cms_detected TEXT,           -- 検出されたCMS名（"WordPress","Wix"等）。未検出ならNULL
is_column_page BOOLEAN,      -- 第2層でコラムと判定されたか（1/0）
column_reason TEXT,          -- コラム判定の根拠（"url_path","breadcrumb","cms_structure"）。非コラムならNULL
top_page_url TEXT,           -- 第3層で特定されたトップページURL。第3層未到達ならNULL
site_link_count INTEGER,     -- トップページのサイト内リンク数。第3層未到達ならNULL
site_type TEXT               -- 第3層の判定結果（"local_small","large_site"等）。第3層未到達ならNULL
```

**注意：** 既存カラムは一切変更しない。新カラムはNULL許容で追加する。

### 4.2 既存DBへのマイグレーション

`init_db()`関数の末尾に、既存テーブルに新カラムを追加するALTER TABLE文を追加する。
既にカラムが存在する場合はエラーにならないよう、try/exceptで囲む。

```python
# 既存テーブルへのカラム追加（マイグレーション）
new_columns = [
    ("cms_detected", "TEXT"),
    ("is_column_page", "BOOLEAN"),
    ("column_reason", "TEXT"),
    ("top_page_url", "TEXT"),
    ("site_link_count", "INTEGER"),
    ("site_type", "TEXT"),
]
for col_name, col_type in new_columns:
    try:
        cursor.execute(f"ALTER TABLE results ADD COLUMN {col_name} {col_type}")
    except sqlite3.OperationalError:
        pass  # カラムが既に存在する場合
```

### 4.3 insert_result関数の更新

`insert_result()`関数のINSERT文に新カラムを追加する。

**変更前のINSERT文のカラム：**
```
session_id, location_name, rank, title, url, snippet,
is_ad, ad_position, page, category,
has_meta_desc, meta_desc_length, has_structured_data,
has_ogp, page_text_length, site_status
```

**変更後のINSERT文のカラム：**
```
session_id, location_name, rank, title, url, snippet,
is_ad, ad_position, page, category,
has_meta_desc, meta_desc_length, has_structured_data,
has_ogp, page_text_length, site_status,
cms_detected, is_column_page, column_reason,
top_page_url, site_link_count, site_type
```

プレースホルダー（?）も6個追加し、引数のタプルに以下を追加：
```python
result_data.get("cms_detected"),
result_data.get("is_column_page"),
result_data.get("column_reason"),
result_data.get("top_page_url"),
result_data.get("site_link_count"),
result_data.get("site_type"),
```

---

## 5. ステップ4：analyzer.pyの拡張

### 5.1 現行のanalyze_url関数の変更

現行の`analyze_url()`の返却dictに以下のキーを追加する。
また、**BeautifulSoupオブジェクト（soup）もdictに含めて返す**。第2層の判定でHTML構造を解析する必要があるため。

**追加する返却キー：**
```python
"soup": None,                  # BeautifulSoupオブジェクト（HTMLパース済み）
"cms_detected": None,          # CMS検出結果（文字列 or None）
"is_column_page": False,       # コラム判定結果
"column_reason": None,         # コラム判定根拠
"url_path_keywords": [],       # URLパスから検出されたキーワード
"breadcrumb_keywords": [],     # パンくずから検出されたキーワード
"heading_count": 0,            # h2+h3タグの合計数
"text_depth": 0,               # テキスト集中階層の深さ
"outer_link_count": 0,         # テキスト集中エリア外のリンク数
```

### 5.2 HTMLパース後の追加解析

`response`取得成功後、`soup`生成後に以下の解析を追加する。
**全てHTTPアクセスなし。既に取得済みのHTMLに対する解析のみ。**

#### 5.2.1 CMS指紋検出（材料A）

```python
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
```

この関数を`analyzer.py`内に定義する。

#### 5.2.2 URLパスキーワード検出（材料B）

```python
def detect_url_path_keywords(url):
    """
    URLのパス部分からコラム系キーワードを検出する。
    Returns: 検出されたキーワードのリスト。
    """
    from urllib.parse import urlparse
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
```

#### 5.2.3 パンくずリストキーワード検出（材料C）

```python
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
    import json as _json
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = _json.loads(script.string or "")
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
```

#### 5.2.4 見出しタグカウント（材料E）

```python
def count_headings(soup):
    """h2 + h3タグの合計数を返す。"""
    h2_count = len(soup.find_all("h2"))
    h3_count = len(soup.find_all("h3"))
    return h2_count + h3_count
```

#### 5.2.5 テキスト集中階層の深さ（材料F）

```python
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
```

#### 5.2.6 記事周辺リンク群カウント（材料G）

```python
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
```

### 5.3 analyze_url関数の修正箇所

現行のanalyze_url関数を以下のように修正する。

**修正前（soup生成後、return resultの前）：**
```python
soup = BeautifulSoup(html_text, "html.parser")

# meta description
meta_desc = soup.find("meta", attrs={"name": "description"})
...
# ページ文字量
text = soup.get_text()
result["page_text_length"] = len(text)
```

**修正後：**
```python
soup = BeautifulSoup(html_text, "html.parser")

# meta description
meta_desc = soup.find("meta", attrs={"name": "description"})
...
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
```

**注意：** resultの初期値dictにも上記キーの初期値を追加すること。soupの初期値はNone。

---

## 6. ステップ5：第2層コラム判定（classifier.pyに追加）

### 6.1 コラム判定関数

classifier.pyに以下の関数を追加する。

```python
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
```

### 6.2 classify関数の修正

classify関数に第2層の呼び出しを追加する。

**修正箇所：** 現行の「4-6. まとめ・比較メディア」判定の後、「5. 企業HP（SEOあり）」判定の前に挿入する。

**修正前：**
```python
    # 4-6. まとめ・比較メディア
    for d in MEDIA_DOMAINS:
        if domain == d or domain.endswith("." + d):
            return "その他"

    # 5. 企業HP（SEOあり）
```

**修正後：**
```python
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

    # 5. 企業HP（SEOあり）
```

**重要：** classify関数はresult dictを受け取っているので、result["is_column_page"]とresult["column_reason"]をここで設定できる。

---

## 7. ステップ6：第3層サイト性質の自動判定

### 7.1 新規ファイル作成：site_analyzer.py

以下のパスに新規ファイルを作成する。

```
/home/adminterml1/services/scraping/serp_diagnosis/site_analyzer.py
```

### 7.2 site_analyzer.pyの全体構造

```python
# site_analyzer.py — 第3層：サイト性質の自動判定
import re
import json
import logging
import requests
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup

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
        import chardet
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
    import time
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
```

---

## 8. ステップ7：classifier.pyの3層統合

### 8.1 classify関数の最終形

第2層（ステップ6で追加済み）の後に、第3層の呼び出しを追加する。

**修正箇所：** 第2層コラム判定の後、現行の「5. 企業HP（SEOあり）」判定を第3層の結果で分岐させる。

**修正後のclassify関数の全体フロー：**

```python
from site_analyzer import analyze_site

def classify(result):
    """
    検索結果を分類する。3層判定。
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

    # 2. ポータル
    for portal in PORTAL_DOMAINS:
        if domain == portal or domain.endswith("." + portal):
            return "ポータル"

    # 3. 大手
    for major in MAJOR_DOMAINS:
        if domain == major or domain.endswith("." + major):
            return "大手"

    # 4. その他（第1層の各サブカテゴリ）
    # 4-1. 公共系
    for suffix in PUBLIC_SUFFIXES:
        if domain.endswith(suffix):
            return "その他"
    for pub_domain in PUBLIC_DOMAINS:
        if domain == pub_domain or domain.endswith("." + pub_domain):
            return "その他"

    # 4-2〜4-6: VIDEO, QA, SNS, BLOG, MEDIA（現行のまま）
    for d in VIDEO_DOMAINS:
        if domain == d or domain.endswith("." + d):
            return "その他"
    for d in QA_DOMAINS:
        if domain == d or domain.endswith("." + d):
            return "その他"
    for d in SNS_DOMAINS:
        if domain == d or domain.endswith("." + d):
            return "その他"
    for d in BLOG_DOMAINS:
        if domain == d or domain.endswith("." + d):
            return "その他"
    for d in MEDIA_DOMAINS:
        if domain == d or domain.endswith("." + d):
            return "その他"

    # ===== 第2層：コラム判定 =====
    is_column, column_reason = judge_column(result)
    if is_column:
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
    if has_meta and has_structured:
        return "企業HP（SEOあり）"

    # 6. 企業HP（SEOなし）
    return "企業HP（SEOなし）"
```

**注意：** classifier.pyの先頭に `import logging` と `logger = logging.getLogger(__name__)` を追加すること。

---

## 9. ステップ8：config.pyの閾値追加

config.pyに以下を追加する。

```python
# 第2層：コラム判定閾値
COLUMN_THRESHOLDS = {
    "min_text_length": 2000,    # コラム判定に必要な最低テキスト文字数
    "min_heading_count": 4,     # 条件3に必要な最低見出し数（h2+h3）
    "min_text_depth": 5,        # 条件3に必要な最低テキスト集中階層深さ
}

# 第3層：サイト規模判定閾値
SITE_ANALYSIS_THRESHOLDS = {
    "max_internal_links": 30,   # サイト内リンク数の上限（これ以下ならローカル企業規模）
    "max_key_pages": 3,         # 主要ページの最大取得数
    "access_interval": 2,       # アクセス間隔（秒）
}
```

**注意：** analyzer.pyとsite_analyzer.pyの閾値は、このconfig.pyの値を参照するようにしてもよいし、直接定数で持ってもよい。ただし閾値の値は上記と一致させること。

---

## 10. ステップ9：app.pyの修正

### 10.1 サマリー計算にコラム追加

`results()`関数のサマリー計算部分を修正する。

**修正箇所：** `category_counts`の集計後に`column_count`を追加。

```python
portal_count = category_counts.get("ポータル", 0)
major_count = category_counts.get("大手", 0)
column_count = category_counts.get("コラム", 0)        # ★追加
seo_yes_count = category_counts.get("企業HP（SEOあり）", 0)
seo_no_count = category_counts.get("企業HP（SEOなし）", 0)
other_count = category_counts.get("その他", 0)
```

`locations_data[loc_name]`のdictにも追加：
```python
"column_count": column_count,   # ★追加
```

### 10.2 CSV集計にコラム追加

`export_csv()`関数の集計行を修正する。

**修正前：**
```python
writer.writerow(["大手", category_counts.get("大手", 0)])
writer.writerow(["その他", category_counts.get("その他", 0)])
```

**修正後：**
```python
writer.writerow(["大手", category_counts.get("大手", 0)])
writer.writerow(["コラム", category_counts.get("コラム", 0)])    # ★追加
writer.writerow(["その他", category_counts.get("その他", 0)])
```

### 10.3 CSV詳細行に第2層・第3層情報追加

CSVのヘッダー行に以下を追加する（末尾に追加）：
```
"CMS検出", "コラム判定", "トップページURL", "サイト内リンク数", "サイト種別"
```

詳細行にも以下を追加：
```python
r.get("cms_detected") or "-",
"○" if r.get("is_column_page") else "-",
r.get("top_page_url") or "-",
r.get("site_link_count") if r.get("site_link_count") is not None else "-",
r.get("site_type") or "-",
```

**注意：** `get_results()`が返すdictにはDB上のカラム名がそのまま入る。新カラムは過去データではNULLなので、`r.get()`で安全に取得できる。ただし`sqlite3.Row`のdict変換で新カラムが含まれることを確認すること（`SELECT *`なら自動的に含まれる）。

### 10.4 _run_analysis関数の修正

`_run_analysis()`関数内で、`classify()`呼び出し後に新カラムの値をresult_dataに反映する。

**修正箇所：**
```python
# 分類
result_data["category"] = classify(result_data)
```

**この行の後に追加：**
```python
# 第2層・第3層の結果をresult_dataに反映（classify内で設定される）
# cms_detectedはanalyze_urlで設定済み
```

**ただし、** `result_data`は`site_info`のキーと`analyze_url`の返却キーから構成される。
`_run_analysis()`内のresult_data構築部分に以下を追加する：

**修正前（site_info取得後のresult_data構築）：**
```python
result_data = {
    ...
    "site_status": site_info["site_status"],
}
```

**修正後：**
```python
result_data = {
    ...
    "site_status": site_info["site_status"],
    # 第2層・第3層用（初期値）
    "cms_detected": site_info.get("cms_detected"),
    "is_column_page": False,
    "column_reason": None,
    "top_page_url": None,
    "site_link_count": None,
    "site_type": None,
    # soup（分類用。DBには保存しない）
    "soup": site_info.get("soup"),
    # 第2層材料
    "url_path_keywords": site_info.get("url_path_keywords", []),
    "breadcrumb_keywords": site_info.get("breadcrumb_keywords", []),
    "heading_count": site_info.get("heading_count", 0),
    "text_depth": site_info.get("text_depth", 0),
    "outer_link_count": site_info.get("outer_link_count", 0),
    "page_text_length": site_info["page_text_length"],
}

# 分類（classify内で第2層・第3層の結果がresult_dataに設定される）
result_data["category"] = classify(result_data)

# soupはDB保存不要なので削除
result_data.pop("soup", None)
# リスト型もDB保存不要
result_data.pop("url_path_keywords", None)
result_data.pop("breadcrumb_keywords", None)
result_data.pop("heading_count", None)
result_data.pop("text_depth", None)
result_data.pop("outer_link_count", None)
```

---

## 11. ステップ10：テンプレート修正（results.html）

### 11.1 サマリーパネルにコラム追加

「大手」と「企業HP（SEOあり）」の間に以下を挿入する。

**挿入位置：** `summary-major` の div の後、`summary-seo-yes` の div の前。

```html
<div class="summary-item summary-column">
    <span class="summary-label">コラム</span>
    <span class="summary-value">{{ data.column_count }}件</span>
</div>
```

### 11.2 バッジクラス名の確認

現行のバッジのクラス名生成は以下のロジック：
```
badge-{{ r.category | replace('（', '-') | replace('）', '') | replace('・', '-') }}
```

「コラム」の場合、`badge-コラム` となる。これに対応するCSSを追加する（ステップ11で対応）。

---

## 12. ステップ11：CSS修正（style.css）

### 12.1 コラムのサマリー色追加

```css
.summary-column .summary-value { color: #ab47bc; }
```

**挿入位置：** `.summary-major .summary-value` の後。

### 12.2 コラムのバッジ色追加

```css
.badge-コラム { background: #6a1b9a; color: #ce93d8; }
```

**挿入位置：** `.badge-大手` の後。

---

## 13. ステップ12：Flaskサービス再起動

```bash
sudo systemctl restart serp_diagnosis
```

---

## 14. ステップ13：完了報告

以下のフォーマットで報告すること。

```
【完了報告】
第2層（コラム判定）の実装：完了 / 差異あり（理由：...）
第3層（サイト性質の自動判定）の実装：完了 / 差異あり（理由：...）
トップページ特定の実装方式：（具体的に記載）
DB変更：完了 / 差異あり（理由：...）
表示・CSV変更：完了 / 差異あり（理由：...）
判定閾値の採用値：
  コラム判定テキスト量：2,000文字
  コラム判定見出し数：4個
  コラム判定テキスト深さ：5
  サイト内リンク上限：30本
  主要ページ取得数：3ページ
差異の有無：あり / なし
  （ありの場合、差異報告のフォーマットで記載）
```

---

## 15. 差異報告のルール

指示書と異なる実装をした場合は、必ず以下の形式で報告すること。

```
【差異報告】
指示書の内容：（何を指示されていたか）
実際の実装：（何をしたか）
理由：（なぜ変えたか）
影響：（他の箇所への影響はあるか）
```

---

## 16. 禁止事項

| 項目 | 内容 |
|------|------|
| Chrome拡張の変更 | content.js、popup.js、popup.html、manifest.jsonは触らない |
| 第1層ロジックの変更 | 既存のドメインパターン判定は変更しない |
| 既存カラムの削除・変更 | DBの既存カラムの構造を変えない |
| url_surveyへの依存 | url_surveyのコードをimportしない |
| 分類フローの順序変更 | 第1層→第2層→第3層の順序は変えない |
| 過度なライブラリ追加 | 既存の依存（requests, bs4, chardet）以外は原則追加しない |

---

## 17. ファイル一覧と変更種別

| ファイル | 変更種別 | 主な変更内容 |
|----------|----------|------------|
| database.py | 修正 | 新カラム追加、マイグレーション、insert_result拡張 |
| analyzer.py | 修正 | CMS検出・パンくず解析・見出しカウント等の関数追加、返却dict拡張 |
| site_analyzer.py | **新規** | 第3層のトップページ特定・サイト規模判定・主要ページ分析 |
| classifier.py | 修正 | judge_column関数追加、classify関数に第2層・第3層呼び出し追加 |
| config.py | 修正 | COLUMN_THRESHOLDS, SITE_ANALYSIS_THRESHOLDS追加 |
| app.py | 修正 | サマリーにcolumn_count追加、CSV集計・詳細行追加、_run_analysis拡張 |
| templates/results.html | 修正 | サマリーパネルにコラム追加 |
| static/style.css | 修正 | コラムのサマリー色・バッジ色追加 |

---

**以上。ステップ1（把握レポート）から開始すること。**
