# 制作指示書：SERP診断ツール（Flask + Playwright サーバー完結型）

**スクレイピングPj → Claude Code｜2026年3月26日｜Phase 1**

---

## 1. 概要

本ツールは、Google検索結果の構造を分析し、「特定の検索ワード×地域で、企業HPやショートサイトが食い込める余地があるか」を判定する営業支援ツールである。

Flask WebUI上で検索フレーズと地域を入力すると、サーバー側のPlaywrightがヘッドレスChromiumでGoogle検索を実行し、結果を取得・分析・分類する。Linuxサーバー1台で完結する。

### 1.1 背景と目的

スマホ用LP制作の営業活動において、「御社の地域では、このワードでショートサイトのヒット率が高そうです」というレベルのプレゼンができる調査データを取得する。

### 1.2 重要な設計原則

**⚠ 検索フレーズに地域名を含めない。** 実際のスマホユーザーは「安くて速い車の板金修理」と入力し、地域名は入れない。Googleが位置情報から地域を判定して結果を返す。この挙動を再現するため、フレーズと地域は完全に分離する。地域指定はPlaywrightのGeolocation偽装で制御する。

### 1.3 操作フロー（ユーザー視点）

1. ブラウザで http://192.168.0.123:5112 を開く
2. 検索フレーズを入力（例：「安くて速い車の板金修理」）
3. 地域を選択（複数選択可）
4. 検索モードを選択（PC / スマホ）
5. 取得ページ数を指定（3ページ=30件 / 5ページ=50件）
6. 「診断実行」ボタンを押す
7. サーバーが地域ごとに検索・取得・分析を実行
8. 結果画面に地域別の分析結果が表示される
9. CSVエクスポートでデータを取得

---

## 2. システム構成

### 2.1 全体構成図

```
ユーザーPC（ブラウザのみ）
  │
  │ http://192.168.0.123:5112
  ↓
Linuxサーバー（192.168.0.123）
  Flask (port 5112)
  ├─ WebUI（入力画面・結果画面）
  ├─ Playwright（ヘッドレスChromium）
  │   ├─ Geolocation偽装で地域指定
  │   ├─ シークレットモード相当（クリーンコンテキスト）
  │   └─ Google検索実行・結果HTML取得
  ├─ analyzer.py（URL先のサイト情報取得）
  ├─ classifier.py（分類判定）
  └─ SQLite（セッション・結果保存）
```

ユーザーPCにはPythonもChrome拡張も不要。ブラウザだけで操作する。

### 2.2 技術スタック

| 項目 | 技術 | 備考 |
|------|------|------|
| サーバー | Python 3.x + Flask | 既存環境 |
| ブラウザ自動操作 | Playwright (async) | pip install playwright → playwright install chromium |
| URL先の取得 | requests + BeautifulSoup | 既存ライブラリ |
| データ保存 | SQLite | セッション・結果の永続化 |
| ポート | 5112 | 検索・地図系帯域 |
| 配置先 | /home/adminterml1/services/scraping/serp_diagnosis/ | フォルダ作成済み |

---

## 3. フォルダ構成

```
/home/adminterml1/services/scraping/serp_diagnosis/
├── app.py                    # Flaskメイン
├── scraper.py                # PlaywrightでGoogle検索実行
├── parser.py                 # 検索結果HTMLのパース
├── analyzer.py               # URL先のサイト情報取得
├── classifier.py             # 分類判定ロジック
├── config.py                 # ポータルリスト・地域座標・設定値
├── database.py               # SQLite操作
├── requirements.txt
├── data/
│   └── serp_diagnosis.db     # SQLite DB
├── templates/
│   ├── index.html            # 入力画面（トップページ）
│   ├── progress.html         # 実行中画面
│   └── results.html          # 分析結果表示
└── static/
    └── style.css
```

---

## 4. 環境構築（最初に実行）

**⚠ Playwrightのインストールが最初の関門。失敗した場合はエラー内容を報告すること。勝手に代替手段に切り替えない。**

### 4.1 requirements.txt

```
flask
playwright
requests
beautifulsoup4
chardet
```

### 4.2 インストールコマンド

```bash
cd /home/adminterml1/services/scraping/serp_diagnosis
pip3 install -r requirements.txt --break-system-packages
playwright install chromium
playwright install-deps chromium
```

playwright install-deps はシステムライブラリ（libgbm, libnss3等）をインストールする。sudo権限が必要な場合がある。失敗した場合はそのエラーをそのまま報告すること。

---

## 5. scraper.py — Google検索実行

### 5.1 機能概要

PlaywrightのヘッドレスChromiumで、指定された地域のGeolocationを偽装し、Google検索を実行する。複数ページの結果HTMLを取得して返す。

### 5.2 関数仕様

```python
async def search_google(query: str, location: dict, pages: int, device: str) -> list[str]:
    """
    Google検索を実行し、各ページのHTMLをリストで返す。

    Args:
        query: 検索フレーズ（例: 「安くて速い車の板金修理」）
        location: {"name": "名古屋市", "lat": 35.1815, "lng": 136.9066}
        pages: 取得ページ数（1ページ=10件）
        device: "mobile" or "desktop"

    Returns:
        list[str]: 各ページのHTML文字列のリスト
    """
```

### 5.3 実装要件

| 項目 | 仕様 |
|------|------|
| ブラウザモード | headless=True |
| コンテキスト | 毎回新規作成（シークレットモード相当）、Cookie・履歴なし |
| Geolocation | context作成時に geolocation={"latitude": lat, "longitude": lng} を設定、permissions=["geolocation"] を付与 |
| User-Agent | device="mobile" の場合: iPhone SafariのUAを設定、device="desktop" の場合: Windows ChromeのUAを設定 |
| 検索URL | https://www.google.co.jp/search?q={query}&hl=ja ※地域名はqueryに含めない |
| ページ遷移 | 1ページ目取得後、「次へ」リンクをクリックして次ページへ。各ページ取得後にHTMLを保存 |
| 待機時間 | ページ遷移後: 3秒待機（ページ読み込み待ち）、ページ間: 2〜5秒のランダム待機 |
| CAPTCHA検知 | HTML内に「recaptcha」または「unusual traffic」が含まれる場合、CAPTCHA検知としてログに記録し、その地域の検索を中断する。エラーではなく「部分結果」として返す |
| ブラウザ終了 | 各地域の検索完了後に必ず browser.close() |

---

## 6. parser.py — 検索結果HTMLのパース

取得したHTMLからオーガニック結果と広告を抽出する。

### 6.1 抽出仕様

| 分類 | 抽出項目 | 取得方法 |
|------|----------|----------|
| オーガニック | 順位 | 結果ブロックの出現順で連番 |
| オーガニック | タイトル | h3タグのテキスト |
| オーガニック | URL | a[href]のhref属性から実URLを取得。Google内部リダイレクトURLは除外 |
| オーガニック | スニペット | 結果ブロック内の説明文 |
| 広告 | 全項目 | #tads（トップ広告）、#bottomads（ボトム広告）、または「スポンサー」テキストを含むブロック |
| ページ情報 | 検索フレーズ | input[name=q]のvalue |

**⚠ GoogleはDOM構造を頻繁に変更する。obfuscatedクラス名に依存せず、構造的特徴（h3タグ、aタグのhref属性等）を優先すること。初回実装時に実際のHTMLを取得してセレクタを確認・調整すること。**

---

## 7. analyzer.py — サイト情報取得

検索結果の各URLにアクセスし、SEO対策の有無を判定するための情報を取得する。

| 取得項目 | 取得方法 | SEO指標としての意味 |
|----------|----------|---------------------|
| meta description | soup.find('meta', attrs={'name':'description'}) | 設定なし → SEO意識なし |
| title tag | soup.find('title').string | 社名のみ → SEO意識なし |
| 構造化データ | soup.find_all('script', type='application/ld+json') | なし → SEO未実施 |
| OGP設定 | soup.find('meta', property='og:title') | なし → SNS配慮なし |
| ページ文字量 | len(soup.get_text()) | コンテンツ量の指標 |
| レスポンスステータス | response.status_code | サイト稼働状況 |

アクセス間隔: 2秒。timeout: 10秒。User-Agent: 明示的に設定。取得失敗時は「取得不可」として記録し、処理を止めない。

---

## 8. classifier.py — 分類ロジック

以下の順で判定する。先に該当したものが優先。

| 優先順 | 分類 | 判定ロジック | UI表示色 |
|--------|------|-------------|----------|
| 1 | 広告 | is_ad == true | 赤 |
| 2 | ポータル・大手 | ドメインがポータルリストに一致 | オレンジ |
| 3 | その他（公共系） | .go.jp / .lg.jp / wikipedia.org | グレー |
| 4 | その他（メディア） | ニュースサイトリストに一致 | グレー |
| 5 | 企業HP（SEOあり） | meta descあり AND（構造化データあり OR OGPあり） | 青 |
| 6 | 企業HP（SEOなし） | 上記に該当しない独自ドメイン | 緑 |

**「企業HP（SEOなし）」がターゲット候補。この数が多い地域×ワードの組み合わせが、「ショートサイトが食い込める余地がある」ことの証拠になる。**

---

## 9. config.py — 設定値

### 9.1 地域リスト（初期値）

```python
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
```

### 9.2 ポータルリスト（初期値）

```python
PORTAL_DOMAINS = [
    "hotpepper.jp", "tabelog.com", "gnavi.co.jp", "suumo.jp", "homes.co.jp",
    "ekiten.jp", "minkou.jp", "goo-net.com", "carsensor.net",
    "beauty.hotpepper.jp", "retty.me", "food.rakuten.co.jp",
    "kakaku.com", "zba.jp", "ielove.co.jp",
]
```

### 9.3 ニュースサイトリスト（初期値）

```python
NEWS_DOMAINS = [
    "news.yahoo.co.jp", "mainichi.jp", "asahi.com",
    "yomiuri.co.jp", "nikkei.com", "nhk.or.jp", "sankei.com",
]
```

### 9.4 SEO判定閾値

| 項目 | SEO対策ありの条件 |
|------|-------------------|
| meta description | 存在する AND 50文字以上 |
| 構造化データ | JSON-LDが1つ以上 |
| OGP | og:titleが存在 |
| 総合判定 | meta descあり AND（構造化あり OR OGPあり） |

---

## 10. データベース設計

### sessions テーブル

| カラム | 型 | 説明 |
|--------|-----|------|
| id | TEXT PRIMARY KEY | UUID |
| name | TEXT NOT NULL | セッション名（自動生成: 検索ワード_日時） |
| query | TEXT | 検索フレーズ |
| device | TEXT | mobile / desktop |
| locations | TEXT | 対象地域（JSON配列） |
| created_at | TEXT NOT NULL | 作成日時 |
| status | TEXT DEFAULT 'running' | running / completed / partial / error |

### results テーブル

| カラム | 型 | 説明 |
|--------|-----|------|
| id | INTEGER PRIMARY KEY AUTOINCREMENT | 連番 |
| session_id | TEXT NOT NULL | sessions.id への FK |
| location_name | TEXT | 地域名 |
| rank | INTEGER | 検索順位 |
| title | TEXT | ページタイトル |
| url | TEXT | URL |
| snippet | TEXT | スニペット |
| is_ad | BOOLEAN DEFAULT 0 | 広告フラグ |
| ad_position | TEXT | top / bottom / null |
| page | INTEGER | 取得元ページ番号 |
| category | TEXT | 分類結果 |
| has_meta_desc | BOOLEAN | meta description有無 |
| meta_desc_length | INTEGER | meta description文字数 |
| has_structured_data | BOOLEAN | 構造化データ有無 |
| has_ogp | BOOLEAN | OGP設定有無 |
| page_text_length | INTEGER | ページ文字量 |
| site_status | TEXT | OK / error / blocked / timeout |

---

## 11. app.py — Flaskエンドポイント

| メソッド | パス | 機能 |
|----------|------|------|
| GET | / | 入力画面 + 過去のセッション一覧 |
| POST | /diagnose | 診断実行。バックグラウンドで検索・分析を実行し、進捗画面にリダイレクト |
| GET | /progress/\<session_id\> | 進捗画面。地域ごとの進捗をリアルタイム表示。完了後に結果画面へ自動遷移 |
| GET | /api/progress/\<session_id\> | 進捗API（JSONレスポンス。JavaScriptからポーリング） |
| GET | /results/\<session_id\> | 分析結果表示 |
| GET | /export/\<session_id\> | CSVエクスポート（UTF-8 BOM付き） |

Flask起動設定: host='0.0.0.0', port=5112, debug=False

---

## 12. 画面仕様

### 12.1 入力画面（/）

| 要素 | 仕様 |
|------|------|
| 検索フレーズ | テキスト入力。プレースホルダー: 「安くて速い車の板金修理」 |
| 地域選択 | チェックボックス式の地域リスト。複数選択可。config.pyのLOCATIONSから生成。「全選択」「全解除」ボタン付き |
| 検索モード | ラジオボタン: スマホ（デフォルト） / PC |
| 取得ページ数 | セレクトボックス: 1 / 2 / 3 / 5（デフォルト: 3） |
| 診断実行ボタン | 選択地域数 × ページ数の推定時間を表示 |
| 過去のセッション一覧 | 日時・セッション名・件数・「結果を見る」リンク・「CSV」リンク |

### 12.2 進捗画面（/progress/\<id\>）

| 表示要素 | 内容 |
|----------|------|
| 全体進捗 | 「3/5 地域完了」のようなプログレスバー |
| 地域別状態 | 名古屋市: ✅ 完了（30件）、豊田市: ⏳ 検索中...、岡崎市: ⏳ 待機中 |
| CAPTCHA検知時 | 「名古屋市: CAPTCHA検知、部分結果で続行」と表示 |
| 完了後 | 「結果を見る」ボタンを表示（または自動遷移） |

進捗更新はポーリング（JavaScriptで定期的に /api/progress/\<id\> を取得）で実現する。

### 12.3 結果画面（/results/\<id\>）

#### サマリーパネル（地域別）

| 表示項目 | 内容 |
|----------|------|
| 検索フレーズ | 「安くて速い車の板金修理」 |
| 地域タブ | 地域ごとにタブ切替で結果表示 |
| 広告数 | 広告の件数と位置（上部X件・下部Y件） |
| ポータル占有数 | ポータル・大手の件数 |
| 企業HP（SEOあり） | 件数 |
| 企業HP（SEOなし） | 件数 ← これがターゲット |
| その他 | 件数 |
| 診断コメント | 自動生成コメント |

#### 診断コメントの自動生成ロジック

| 条件 | コメント |
|------|----------|
| 企業HP（SEOなし）が3件以上 | 「★ ショートサイトのヒット率高。推奨エリア」 |
| 企業HP（SEOなし）が1〜2件 | 「○ 食い込み余地あり」 |
| 企業HP（SEOなし）が0件 | 「△ 競争が激しいエリア」 |
| ポータル占有が70%以上 | 「ポータル支配が強いが、裏を返せばチャンス」 |

#### 結果一覧テーブル

全件を順位順に表示。カラム: 順位 / 分類（色付きバッジ） / タイトル（クリックでURL先へ） / ドメイン / SEO指標（meta/構造化/OGPの有無アイコン）

### 12.4 UIスタイル

ダッシュボード（port 5100）と同系統のダークテーマ。背景: #1a1a2e系、カード: #16213e系、アクセント: 青緑系。既存のスクレイピングツール群と統一感のあるデザイン。

---

## 13. CSVエクスポート仕様

| 項目 | 仕様 |
|------|------|
| 文字コード | UTF-8 BOM付き |
| ファイル名 | serp_diagnosis_{query}_{date}.csv |
| カラム順 | 地域, 順位, 分類, タイトル, URL, スニペット, 広告, 広告位置, meta_desc有無, meta_desc文字数, 構造化データ有無, OGP有無, ページ文字量, 取得状態 |

---

## 14. 起動・運用

### 14.1 サーバー起動コマンド

```bash
# 起動
cd /home/adminterml1/services/scraping/serp_diagnosis
nohup python3 app.py > serp_diagnosis.log 2>&1 &

# 停止
pkill -f 'serp_diagnosis/app.py'

# ポート指定停止（念のため）
kill -9 $(ss -tlnp | grep :5112 | grep -oP 'pid=\K[0-9]+')
```

### 14.2 ダッシュボード登録

ダッシュボード（port 5100）のconfig.jsonに以下を追加する。

```json
{
  "name": "SERP診断",
  "type": "web",
  "port": 5112,
  "description": "Google検索結果構造分析ツール"
}
```

**⚠ 既存のエントリを破壊しないこと。追加のみ。既存のエントリを削除・変更しない。**

---

## 15. Googleガード対策

本ツールは使用頻度が低い（1日数回〜十数回）ため、過度な対策は不要。以下の基本対策を実装する。

| 対策 | 実装 |
|------|------|
| ページ間待機 | 2〜5秒のランダム待機 |
| User-Agent | 実際のブラウザUAを設定 |
| クリーンコンテキスト | 毎回新規コンテキスト（Cookieなし） |
| CAPTCHA検知 | HTML内に recaptcha または unusual traffic が含まれる場合、その地域の検索を中断し「部分結果」として継続 |
| 地域間待機 | 地域切替時に5〜10秒の待機 |
| ブロック時 | エラーで止めず、取得できた分だけで結果を返す |

「叱られて育つ」方針。まず動かし、問題があればその時点で対応する。

---

## 16. Claude Codeへの指示

### 16.1 実装順序

| 順序 | 内容 | 完了条件 |
|------|------|----------|
| 1 | Playwrightインストール・動作確認 | playwright install chromium が成功すること。失敗時はエラーを報告し停止 |
| 2 | requirements.txt + pip install | 全ライブラリがインストールされること |
| 3 | database.py + DB初期化 | テーブル作成が正常完了 |
| 4 | config.py | 地域リスト・ポータルリスト・設定値が定義されている |
| 5 | scraper.py | PlaywrightでGoogle検索が実行できること。Geolocation偽装が動作すること |
| 6 | parser.py | 取得したHTMLから検索結果が抽出できること |
| 7 | analyzer.py | 指定URLのmeta情報が取得できること |
| 8 | classifier.py | テストデータで正しく分類できること |
| 9 | app.py + templates/ + static/ | Flask起動、全画面動作確認 |
| 10 | ダッシュボード登録 | config.json更新、カード表示確認 |

### 16.2 把握レポートの要求

**各ステップの着手前に、以下の形式で把握レポートを出力すること。「把握しました」だけで進めない。**

```
[把握レポート]
■ これから作るもの: (具体的に)
■ ファイル名: (作成・編集するファイル)
■ 作業内容: (何をするか)
■ 完了条件: (どうなったら完了か)
■ 指示書との差異: (あれば理由付きで)
```

### 16.3 差異報告の義務

制作指示書と異なる実装をする場合、その理由を必ず報告すること。報告なしの変更は認めない。

### 16.4 テストシナリオ

| シナリオ | 操作 | 期待結果 |
|----------|------|----------|
| 正常系 | 「板金修理」× 名古屋市 × 3ページ | 結果画面にサマリーと一覧が表示される |
| 複数地域 | 同ワード × 3地域 | 地域タブで切替可能 |
| 広告あり | 広告が表示される検索結果 | 広告が赤バッジで分離表示 |
| CSVエクスポート | 結果からCSVダウンロード | UTF-8 BOM付き、全カラム出力 |
| CAPTCHA検知 | 連続検索でCAPTCHAが出た場合 | 部分結果で継続、エラーで止まらない |
| URL取得失敗 | 存在しないURLが結果に含まれる場合 | 「取得不可」として記録、処理続行 |
