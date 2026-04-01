# analyzer.py — URL先のサイト情報取得
import time
import logging
import requests
from bs4 import BeautifulSoup
import chardet

logger = logging.getLogger(__name__)

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
TIMEOUT = 10
ACCESS_INTERVAL = 2


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
