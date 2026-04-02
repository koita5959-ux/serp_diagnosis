# config.py — 設定値

# 地域リスト
LOCATIONS = [
    {"name": "名古屋市", "lat": 35.1815, "lng": 136.9066},
    {"name": "豊田市", "lat": 35.0826, "lng": 137.1560},
    {"name": "岡崎市", "lat": 34.9551, "lng": 137.1467},
    {"name": "一宮市", "lat": 35.3030, "lng": 136.8030},
    {"name": "春日井市", "lat": 35.2474, "lng": 136.9722},
    {"name": "岐阜市", "lat": 35.4233, "lng": 136.7607},
    {"name": "大垣市", "lat": 35.3594, "lng": 136.6129},
    {"name": "四日市市", "lat": 34.9650, "lng": 136.6246},
    {"name": "津市", "lat": 34.7191, "lng": 136.5086},
    {"name": "静岡市", "lat": 34.9756, "lng": 138.3828},
    {"name": "浜松市", "lat": 34.7108, "lng": 137.7261},
]

# ポータルドメインリスト（口コミ・比較・仲介・掲載で他社の情報を集約するサイト）
PORTAL_DOMAINS = [
    # --- グルメ・飲食 ---
    "hotpepper.jp", "tabelog.com", "gnavi.co.jp", "retty.me",

    # --- 不動産 ---
    "suumo.jp", "homes.co.jp", "ielove.co.jp",

    # --- 自動車 ---
    "goo-net.com", "carsensor.net", "goobike.com",

    # --- 口コミ・比較・情報ポータル ---
    "ekiten.jp", "minkou.jp", "kakaku.com", "zba.jp",
    "epark.jp",

    # --- 求人 ---
    "indeed.com", "townwork.net", "baitoru.com",
    "rikunabi.com", "mynavi.jp", "doda.jp",

    # --- リフォーム・住宅比較ポータル ---
    "curama.jp", "meetsmore.com", "homepro.jp",
    "rehome-navi.com", "ienakama.com", "rescue-navi.jp",
    "sunrefre.jp", "nuri-kae.jp", "reform-market.com",
    "seikatsu110.jp", "sharing-tech.co.jp", "kenbiya.com",
]

# 大手企業ドメインリスト（自社で商品・サービスを提供する大手）
MAJOR_DOMAINS = [
    # --- EC・ショッピングモール ---
    "rakuten.co.jp", "rakuten.ne.jp", "amazon.co.jp", "amazon.com",
    "shopping.yahoo.co.jp", "food.rakuten.co.jp", "monotaro.com",

    # --- 大手カー用品・自動車チェーン ---
    "yellowhat.jp", "autobacs.com",
    "carcon.co.jp", "carseven.co.jp", "carnext.jp",
    "autoc-one.jp", "mota.inc",
]

# --- 「その他」判定ドメインリスト ---

# 動画プラットフォーム
VIDEO_DOMAINS = [
    "youtube.com", "youtu.be", "nicovideo.jp", "tiktok.com", "vimeo.com",
]

# QA・掲示板
QA_DOMAINS = [
    "chiebukuro.yahoo.co.jp", "oshiete.goo.ne.jp", "detail.chiebukuro.yahoo.co.jp",
    "komachi.yomiuri.co.jp", "okwave.jp",
    "question.realestate.yahoo.co.jp",
]

# SNS
SNS_DOMAINS = [
    "twitter.com", "x.com", "instagram.com", "facebook.com",
    "threads.net", "linkedin.com",
]

# ブログプラットフォーム
BLOG_DOMAINS = [
    "note.com", "ameblo.jp", "hatenablog.com", "hatenablog.jp",
    "hateblo.jp", "fc2.com", "livedoor.com", "blogspot.com",
    "medium.com", "wordpress.com",
]

# まとめ・比較メディア
MEDIA_DOMAINS = [
    "news.yahoo.co.jp", "mainichi.jp", "asahi.com",
    "yomiuri.co.jp", "nikkei.com", "nhk.or.jp", "sankei.com",
    "ctn-net.jp", "tokusen-tai.com", "mybest.com",
    "diamond.jp", "toyokeizai.net", "president.jp",
    "itmedia.co.jp", "impress.co.jp",
    "allabout.co.jp", "travelbook.co.jp",
    "iekoma.com", "makit.jp", "housejoho.com",
    "shuminoengei.jp",
    "nifty.com",
]

# SEO判定閾値
SEO_THRESHOLDS = {
    "meta_desc_min_length": 80,
    "structured_data_min_count": 1,
}

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

# サーバー設定
SERVER_HOST = "0.0.0.0"
SERVER_PORT = 5112

# DB設定
import os
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "data", "serp_diagnosis.db")
