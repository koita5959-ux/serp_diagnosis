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

# ポータル・大手ドメインリスト
PORTAL_DOMAINS = [
    "hotpepper.jp", "tabelog.com", "gnavi.co.jp", "suumo.jp", "homes.co.jp",
    "ekiten.jp", "minkou.jp", "goo-net.com", "carsensor.net",
    "beauty.hotpepper.jp", "retty.me", "food.rakuten.co.jp",
    "kakaku.com", "zba.jp", "ielove.co.jp",
]

# ニュースサイトドメインリスト
NEWS_DOMAINS = [
    "news.yahoo.co.jp", "mainichi.jp", "asahi.com",
    "yomiuri.co.jp", "nikkei.com", "nhk.or.jp", "sankei.com",
]

# SEO判定閾値
SEO_THRESHOLDS = {
    "meta_desc_min_length": 50,
    "structured_data_min_count": 1,
}

# サーバー設定
SERVER_HOST = "0.0.0.0"
SERVER_PORT = 5112

# DB設定
import os
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "data", "serp_diagnosis.db")
