# app.py — Flaskメイン（Chrome拡張連携版）
import csv
import io
import json
import logging
import time
import threading
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, jsonify, Response

from config import LOCATIONS, SERVER_HOST, SERVER_PORT
from database import init_db, create_session, update_session_status, insert_result, get_session, get_all_sessions, get_results, get_results_count
from analyzer import analyze_url
from classifier import classify

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

app = Flask(__name__)


# --- CORS対応（Chrome拡張からのリクエスト用）---
@app.after_request
def add_cors_headers(response):
    origin = request.headers.get("Origin", "")
    # Chrome拡張のoriginを許可
    if origin.startswith("chrome-extension://") or not origin:
        response.headers["Access-Control-Allow-Origin"] = origin or "*"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return response


@app.route("/")
def index():
    sessions = get_all_sessions()
    for s in sessions:
        s["result_count"] = get_results_count(s["id"])
    return render_template("index.html", sessions=sessions)


@app.route("/api/analyze", methods=["POST", "OPTIONS"])
def api_analyze():
    """Chrome拡張から送信された検索結果データを受け取り、分析を実行する"""
    if request.method == "OPTIONS":
        return "", 204

    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "JSONデータがありません"}), 400

        query = data.get("query", "").strip()
        pages_data = data.get("pages", [])
        device = data.get("device", "desktop")

        if not query:
            return jsonify({"error": "検索フレーズがありません"}), 400
        if not pages_data:
            return jsonify({"error": "検索結果データがありません"}), 400

        # 全ページからオーガニック結果と広告を集約
        all_organic = []
        all_ads = []
        for page in pages_data:
            page_num = page.get("pageNumber", 1)
            for item in page.get("organic", []):
                item["page"] = page_num
                all_organic.append(item)
            for item in page.get("ads", []):
                item["page"] = page_num
                all_ads.append(item)

        total_items = len(all_organic) + len(all_ads)
        logger.info(f"分析開始: query='{query}', オーガニック={len(all_organic)}件, 広告={len(all_ads)}件")

        # セッション作成（location_nameは "Chrome拡張" 固定）
        location_label = "Chrome拡張"
        session_id = create_session(query, device, [{"name": location_label}])

        # バックグラウンドで分析実行
        thread = threading.Thread(
            target=_run_analysis,
            args=(session_id, location_label, all_organic, all_ads)
        )
        thread.daemon = True
        thread.start()

        return jsonify({
            "session_id": session_id,
            "message": f"分析を開始しました（{total_items}件）",
        })

    except Exception as e:
        logger.error(f"API分析エラー: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


def _run_analysis(session_id, location_label, all_organic, all_ads):
    """バックグラウンドで各URLを分析・分類してDBに保存"""
    try:
        # 広告をDBに保存
        for ad in all_ads:
            result_data = {
                "location_name": location_label,
                "rank": 0,
                "title": ad.get("title", ""),
                "url": ad.get("url", ""),
                "snippet": ad.get("snippet", ""),
                "is_ad": True,
                "ad_position": ad.get("position", "top"),
                "page": ad.get("page", 1),
                "category": "広告",
                "has_meta_desc": None,
                "meta_desc_length": None,
                "has_structured_data": None,
                "has_ogp": None,
                "page_text_length": None,
                "site_status": None,
            }
            insert_result(session_id, result_data)

        # オーガニック結果を分析・分類してDBに保存
        for i, item in enumerate(all_organic):
            url = item.get("url", "")
            logger.info(f"  分析中 [{i+1}/{len(all_organic)}]: {url[:80]}")

            # URL先のサイト情報を取得
            site_info = analyze_url(url)

            result_data = {
                "location_name": location_label,
                "rank": item.get("rank", i + 1),
                "title": item.get("title", ""),
                "url": url,
                "snippet": item.get("snippet", ""),
                "is_ad": False,
                "ad_position": None,
                "page": item.get("page", 1),
                "has_meta_desc": site_info["has_meta_desc"],
                "meta_desc_length": site_info["meta_desc_length"],
                "has_structured_data": site_info["has_structured_data"],
                "has_ogp": site_info["has_ogp"],
                "page_text_length": site_info["page_text_length"],
                "site_status": site_info["site_status"],
            }

            # 分類
            result_data["category"] = classify(result_data)
            insert_result(session_id, result_data)

            # アクセス間隔（analyzer.pyのanalyze_urlは個別呼び出しなのでここで待機）
            if i < len(all_organic) - 1:
                time.sleep(2)

        update_session_status(session_id, "completed")
        logger.info(f"分析完了: session_id={session_id}")

    except Exception as e:
        logger.error(f"分析エラー: session_id={session_id} - {e}", exc_info=True)
        update_session_status(session_id, "error")


@app.route("/api/status/<session_id>")
def api_status(session_id):
    """セッションのステータスを返す"""
    session = get_session(session_id)
    if not session:
        return jsonify({"error": "セッションが見つかりません"}), 404
    return jsonify({
        "status": session["status"],
        "result_count": get_results_count(session_id),
    })


@app.route("/results/<session_id>")
def results(session_id):
    session = get_session(session_id)
    if not session:
        return redirect(url_for("index"))

    all_results = get_results(session_id)

    # 地域ごとにグループ化
    locations_data = {}
    location_names = json.loads(session["locations"]) if session["locations"] else []
    for loc_name in location_names:
        loc_results = [r for r in all_results if r["location_name"] == loc_name]
        ads = [r for r in loc_results if r["is_ad"]]
        organic = [r for r in loc_results if not r["is_ad"]]

        # サマリー計算
        top_ads = [a for a in ads if a["ad_position"] == "top"]
        bottom_ads = [a for a in ads if a["ad_position"] == "bottom"]

        category_counts = {}
        for r in organic:
            cat = r["category"] or "不明"
            category_counts[cat] = category_counts.get(cat, 0) + 1

        portal_count = category_counts.get("ポータル・大手", 0)
        seo_yes_count = category_counts.get("企業HP（SEOあり）", 0)
        seo_no_count = category_counts.get("企業HP（SEOなし）", 0)
        other_public = category_counts.get("その他（公共系）", 0)
        other_media = category_counts.get("その他（メディア）", 0)

        # 診断コメント
        comments = []
        if seo_no_count >= 3:
            comments.append("★ ショートサイトのヒット率高。推奨エリア")
        elif seo_no_count >= 1:
            comments.append("○ 食い込み余地あり")
        else:
            comments.append("△ 競争が激しいエリア")

        total_organic = len(organic)
        if total_organic > 0 and portal_count / total_organic >= 0.7:
            comments.append("ポータル支配が強いが、裏を返せばチャンス")

        locations_data[loc_name] = {
            "results": loc_results,
            "ads": ads,
            "organic": organic,
            "top_ads_count": len(top_ads),
            "bottom_ads_count": len(bottom_ads),
            "portal_count": portal_count,
            "seo_yes_count": seo_yes_count,
            "seo_no_count": seo_no_count,
            "other_public": other_public,
            "other_media": other_media,
            "comments": comments,
        }

    return render_template("results.html", session=session, locations_data=locations_data, location_names=location_names)


@app.route("/export/<session_id>")
def export_csv(session_id):
    session = get_session(session_id)
    if not session:
        return redirect(url_for("index"))

    all_results = get_results(session_id)

    # CSV生成（UTF-8 BOM付き）
    output = io.StringIO()
    output.write('\ufeff')  # BOM

    writer = csv.writer(output)
    writer.writerow([
        "地域", "順位", "分類", "タイトル", "URL", "スニペット",
        "広告", "広告位置", "meta_desc有無", "meta_desc文字数",
        "構造化データ有無", "OGP有無", "ページ文字量", "取得状態"
    ])

    for r in all_results:
        writer.writerow([
            r["location_name"],
            r["rank"] if not r["is_ad"] else "-",
            r["category"],
            r["title"],
            r["url"],
            r["snippet"],
            "○" if r["is_ad"] else "",
            r["ad_position"] or "",
            "○" if r["has_meta_desc"] else "×" if r["has_meta_desc"] is not None else "-",
            r["meta_desc_length"] if r["meta_desc_length"] is not None else "-",
            "○" if r["has_structured_data"] else "×" if r["has_structured_data"] is not None else "-",
            "○" if r["has_ogp"] else "×" if r["has_ogp"] is not None else "-",
            r["page_text_length"] if r["page_text_length"] is not None else "-",
            r["site_status"] or "-",
        ])

    query = session["query"] or "serp"
    date = datetime.now().strftime("%Y%m%d")
    filename_jp = f"serp_diagnosis_{query}_{date}.csv"
    # ASCII安全なフォールバック名
    filename_ascii = f"serp_diagnosis_{date}.csv"
    # RFC 5987形式でUTF-8ファイル名を指定（日本語対応）
    from urllib.parse import quote
    filename_encoded = quote(filename_jp)

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename={filename_ascii}; filename*=UTF-8''{filename_encoded}"
        }
    )


if __name__ == "__main__":
    init_db()
    app.run(host=SERVER_HOST, port=SERVER_PORT, debug=False)
