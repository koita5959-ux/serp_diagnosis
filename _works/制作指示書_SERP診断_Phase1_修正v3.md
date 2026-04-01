# 制作指示書：SERP診断ツール Phase 1 修正 v3

**スクレイピングPj → Claude Code｜2026年3月27日**

---

## 1. 本指示書の目的

SERP診断ツール Phase 1 の実動テスト（2026/3/27 v2.1修正適用後）で判明した**分類精度とデータ品質の問題**を修正する。

v2.1で抽出件数の課題（12件→62件）は解決した。本指示書では「拾ったデータの品質」を高める。

**本指示書のテーマ：拾えるようになった結果を、正しく分類する**

---

## 2. 前提情報

### 2.1 実動テストの結果（v2.1修正後）

テスト条件：
- 検索語：「車のスピード修理」
- 「そのほかの検索結果」を4回押して追加読み込み
- Chrome拡張で読み取り → 分析実行

結果（session: 61b6d1e0）：
- 広告 3件、オーガニック 62件、合計 65件
- 処理時間：約4分

### 2.2 確認された問題

| # | 問題 | 影響 | 深刻度 |
|---|------|------|--------|
| 1 | 非オーガニック要素が順位に混入 | rank 1に「その他のお店やサービス」（地図パック） | ★★★ |
| 2 | 分類の優先順序が不適切 | YouTube、知恵袋等が「企業HP」に分類される | ★★★ |
| 3 | ポータル・大手のドメインリストが不足 | 62件中3件（goo-net.comのみ）しかポータル判定されない | ★★★ |
| 4 | 「その他」の判定基準が未整備 | 動画/QA/SNS等の受け皿がなく全て企業HPに流入 | ★★★ |
| 5 | SEO判定基準が甘い | OGPだけで「SEOあり」になる（WPプラグイン自動挿入） | ★★ |
| 6 | srsltidパラメータで重複すり抜け | 同一ページがrank 1とrank 8に二重登録 | ★★ |
| 7 | sleep(2)の一律適用 | 62件で約2分の無駄な待機時間 | ★★ |
| 8 | CSVにメタ情報がない | 検索フレーズ・集計が記録されない | ★★ |
| 9 | 広告スニペットの重複 | 3件の広告が全て同じスニペットになる | ★ |

### 2.3 問題の本質

現在の分類順序：
```
広告 → ポータル・大手 → 公共系 → メディア → SEOあり → SEOなし（残り全部）
```

この順序では、YouTube・知恵袋・楽天Car等がポータルにもその他にも引っかからず、全て「企業HP」に流入する。結果として「企業HP（SEOなし）23件」の中に営業対象にならないサイトが混入し、ターゲット候補の数字が膨らむ。

### 2.4 配置先

```
/home/adminterml1/services/scraping/serp_diagnosis/
├── app.py                     ← 修正対象①
├── config.py                  ← 修正対象②
├── classifier.py              ← 修正対象③
├── chrome_extension/
│   ├── content.js             ← 修正対象④
│   └── popup.js               （変更なし）
├── templates/
│   └── results.html           （変更なし）
└── （その他のファイルは変更禁止）
```

---

## 3. 修正内容

### 修正A：分類順序の再設計（classifier.py）

**目的：** 「企業HP」の判定に入る前に、営業対象にならないものを全て除外する。

**修正後の分類順序：**

```
1. 広告           ← is_adフラグ（変更なし）
2. ポータル・大手   ← ドメインリスト一致（リスト大幅拡充）
3. その他         ← 動画/QA/SNS/ブログ/公共/メディア等（★新設・統合）
4. 企業HP（SEOあり）← SEO判定（基準厳格化）
5. 企業HP（SEOなし）← 上記いずれにも該当しない残り
```

**分類の設計意図：**
- 「ポータル・大手」= 業種横断で検索上位に出てくる大手サイト。自社でSERPを支配しているプレイヤー
- 「その他」= 営業対象にならないが、ポータルとも言えないもの（公共、動画、QA等）
- 「企業HP」= 純粋な個別企業のサイト。営業判断の対象

**「その他」の統合について：**
現在「その他（公共系）」「その他（メディア）」に分かれているが、UIのサマリーでは合算表示されており、分ける実益が薄い。本修正でこれらを「その他」に統合する。CSV上では「分類」列が「その他」となるが、集計上はこれで十分。将来的に細分化が必要になった場合は「サブ分類」列の追加で対応する。

### 修正B：ポータル・大手ドメインリストの拡充（config.py）

**目的：** 業種を問わず検索上位に出現する大手サイトを網羅的にカバーする。

**修正後のPORTAL_DOMAINS：**

```python
PORTAL_DOMAINS = [
    # --- グルメ・飲食 ---
    "hotpepper.jp", "tabelog.com", "gnavi.co.jp", "retty.me",
    "food.rakuten.co.jp",

    # --- 不動産 ---
    "suumo.jp", "homes.co.jp", "ielove.co.jp",

    # --- 自動車 ---
    "goo-net.com", "carsensor.net", "goobike.com",
    "carcon.co.jp", "carseven.co.jp", "carnext.jp",
    "autoc-one.jp", "mota.inc",

    # --- 口コミ・比較・情報ポータル ---
    "ekiten.jp", "minkou.jp", "kakaku.com", "zba.jp",
    "epark.jp",

    # --- EC・ショッピング ---
    "rakuten.co.jp", "amazon.co.jp", "amazon.com",
    "shopping.yahoo.co.jp",

    # --- 大手カー用品・チェーン ---
    "yellowhat.jp", "autobacs.com",

    # --- 求人・ビジネス ---
    "indeed.com", "townwork.net", "baitoru.com",
    "rikunabi.com", "mynavi.jp", "doda.jp",
]
```

**注意：** `rakuten.co.jp` はサブドメイン込みで判定する（`car.rakuten.co.jp` 等）。現在のclassifier.pyの `domain.endswith("." + portal)` で対応済み。

### 修正C：「その他」判定基準の新設（config.py + classifier.py）

**目的：** 営業対象にならないが、ポータルとも分類できないサイトを正しく除外する。

**config.pyに追加するリスト：**

```python
# --- 「その他」判定ドメインリスト ---

# 動画プラットフォーム
VIDEO_DOMAINS = [
    "youtube.com", "youtu.be", "nicovideo.jp", "tiktok.com", "vimeo.com",
]

# QA・掲示板
QA_DOMAINS = [
    "chiebukuro.yahoo.co.jp", "oshiete.goo.ne.jp", "detail.chiebukuro.yahoo.co.jp",
    "komachi.yomiuri.co.jp", "okwave.jp",
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
]
```

**classifier.pyでの判定：**

```python
# 3. その他（ポータル判定の直後、企業HP判定の前）

# 3-1. 公共系
for suffix in PUBLIC_SUFFIXES:
    if domain.endswith(suffix):
        return "その他"
for pub_domain in PUBLIC_DOMAINS:
    if domain == pub_domain or domain.endswith("." + pub_domain):
        return "その他"

# 3-2. 動画プラットフォーム
for d in VIDEO_DOMAINS:
    if domain == d or domain.endswith("." + d):
        return "その他"

# 3-3. QA・掲示板
for d in QA_DOMAINS:
    if domain == d or domain.endswith("." + d):
        return "その他"

# 3-4. SNS
for d in SNS_DOMAINS:
    if domain == d or domain.endswith("." + d):
        return "その他"

# 3-5. ブログプラットフォーム
for d in BLOG_DOMAINS:
    if domain == d or domain.endswith("." + d):
        return "その他"

# 3-6. まとめ・比較メディア
for d in MEDIA_DOMAINS:
    if domain == d or domain.endswith("." + d):
        return "その他"
```

**将来の拡張方針：**
固定リストで拾えないドメインは「企業HP」に残る前提で運用する。実データを見ながらリストを育てていく。将来的にはページ内容からの自動判定（titleに「比較」「ランキング」等のキーワード、URL構造に `/list/` `/shop/` 等）を補助的に入れる余地を残す。

### 修正D：SEO判定基準の厳格化（classifier.py）

**目的：** WordPressプラグイン自動挿入によるOGPだけで「SEOあり」になる問題を解消する。

**修正前の判定：**
```python
has_meta = has_meta_desc and meta_desc_length >= 50
has_structured = has_structured_data
has_ogp = has_ogp
if has_meta and (has_structured or has_ogp):
    return "企業HP（SEOあり）"
```

**修正後の判定：**
```python
has_meta = has_meta_desc and meta_desc_length >= 80  # 50→80に引き上げ
has_structured = has_structured_data
# OGPのみではSEO対策と判定しない
if has_meta and has_structured:
    return "企業HP（SEOあり）"
```

**変更点：**
- meta description の閾値を 50文字 → 80文字 に引き上げ
- OGP を SEO判定の材料から除外（構造化データのみで判定）

**理由：**
- 80文字未満のmeta descriptionは自動生成や手抜きの可能性が高い
- OGPはWordPressプラグイン（Yoast SEO、All in One SEO等）で自動挿入されるため、「意図的なSEO対策」の証拠にならない
- 構造化データ（JSON-LD）は意図的に実装しないと入らないため、SEO意識の証拠として信頼性が高い

**注意：** この判定基準は初回として設定する。実データを見て閾値を調整する想定。

### 修正E：非オーガニック要素の除外（content.js）

**目的：** Googleの地図パック、画像カルーセル等の非オーガニック要素が順位に混入するのを防ぐ。

**修正対象：** `parseMjjYudBlock()` 関数内のスキップ対象タイトル

**修正前（278-279行目）：**
```javascript
if (title === "地図" || title === "さらに表示" || title === "関連する質問" ||
    title === "他の人はこちらも質問" || title === "強調スニペットについて") continue;
```

**修正後：**
```javascript
// 非オーガニック要素のスキップ
const skipTitles = [
  "地図", "さらに表示", "関連する質問",
  "他の人はこちらも質問", "強調スニペットについて",
  "その他のお店やサービス", "ウェブ検索結果",
  "画像", "動画", "ニュース", "ショッピング",
  "他の人はこちらも検索", "関連キーワード",
  "トップニュース", "レシピ", "求人",
];
if (skipTitles.includes(title)) continue;
```

**同様の修正を `parseFromH3_2026()` 関数にも適用する（353-354行目）。**

**注意：** 完全一致で判定する。部分一致にすると正当なタイトルを誤除外するリスクがある。実際のSERPで新たな非オーガニック見出しが確認された場合は、リストに追加していく。

### 修正F：URL正規化によるsrsltid重複排除（content.js）

**目的：** Googleが付与する `srsltid` トラッキングパラメータにより同一ページが重複登録される問題を解消する。

**修正対象：** `cleanUrl()` 関数

**追加する処理（既存のcleanUrl関数の末尾、`return href;` の前）：**
```javascript
// Googleトラッキングパラメータを除去
if (href.startsWith("http")) {
  try {
    const url = new URL(href);
    url.searchParams.delete("srsltid");
    return url.toString();
  } catch (e) {}
  return href;
}
```

**注意：** `srsltid` 以外のGoogleトラッキングパラメータ（`ved`, `uact` 等）も将来的に除去対象になる可能性があるが、初回は `srsltid` のみとする。

### 修正G：sleep撤廃（app.py）

**目的：** 一律 sleep(2) による無駄な待機時間を解消する。

**修正対象：** `_run_analysis()` 関数内のsleep処理

**修正前（152-154行目）：**
```python
# アクセス間隔（analyzer.pyのanalyze_urlは個別呼び出しなのでここで待機）
if i < len(all_organic) - 1:
    time.sleep(2)
```

**修正後：**
```python
# 同一ドメインへの連続アクセス時のみ1秒待機
if i < len(all_organic) - 1:
    from urllib.parse import urlparse
    current_domain = urlparse(url).netloc
    next_url = all_organic[i + 1].get("url", "")
    next_domain = urlparse(next_url).netloc
    if current_domain == next_domain:
        time.sleep(1)
```

**効果：** 62件の処理時間が約4分 → 約2分に短縮（sleep約2分が削減される）。

### 修正H：CSVメタ情報・サマリー追加（app.py）

**目的：** CSVファイル単体で「何の検索結果か」「分類の集計」が分かるようにする。

**修正対象：** `export_csv()` 関数

**修正後のCSV構造：**
```
検索フレーズ,車のスピード修理
実行日時,2026-03-27 09:26:50
デバイス,desktop
（空行）
--- 集計 ---
広告,3
ポータル・大手,5
その他,6
企業HP（SEOあり）,28
企業HP（SEOなし）,20
合計,62
（空行）
地域,順位,分類,タイトル,URL,スニペット,...（以下データ本体）
```

**実装：** `writer.writerow()` でメタ情報と集計行を先頭に出力してからヘッダー行とデータ行を書く。集計は `get_results()` から取得した全結果の `category` をカウントする。

### 修正I：広告スニペットの重複修正（content.js）

**目的：** 複数の広告が全て同じスニペットになる問題を解消する。

**原因：** `parseAdContainer2026()` 内の h3ルートで `findSnippet(h3, container)` を呼んでいるが、第2引数の `container` が `#tads` 全体を指しているため、最初に見つかったスニペットが全広告に適用される。

**修正方針：** h3の直近の親ブロック（個別の広告ブロック）をスニペット検索の範囲にする。

**修正前（110-111行目付近）：**
```javascript
let url = findUrl(h3, container);
let snippet = findSnippet(h3, container);
```

**修正後：**
```javascript
let url = findUrl(h3, container);
// 個別の広告ブロック内でスニペットを探す（container全体ではなく）
const adBlock = h3.closest("div.MjjYud") || h3.closest("[data-text-ad]") || h3.closest(".uEierd") || h3.parentElement?.parentElement?.parentElement;
let snippet = findSnippet(h3, adBlock || container);
```

---

## 4. UI表示の整合（results.html）

### 修正対象：サマリーパネル

「その他（公共系）」と「その他（メディア）」を統合して「その他」にしたため、results.htmlのサマリーパネルの表示を確認する。

**現状のapp.py（199-205行目）でサマリーを計算している箇所：**
```python
portal_count = category_counts.get("ポータル・大手", 0)
seo_yes_count = category_counts.get("企業HP（SEOあり）", 0)
seo_no_count = category_counts.get("企業HP（SEOなし）", 0)
other_public = category_counts.get("その他（公共系）", 0)
other_media = category_counts.get("その他（メディア）", 0)
```

**修正後：**
```python
portal_count = category_counts.get("ポータル・大手", 0)
seo_yes_count = category_counts.get("企業HP（SEOあり）", 0)
seo_no_count = category_counts.get("企業HP（SEOなし）", 0)
other_count = category_counts.get("その他", 0)
```

results.htmlのサマリーパネルも `other_public + other_media` → `other_count` に変更する。

---

## 5. 作業手順

### ステップ1：把握レポート出力

```
【把握レポート】
修正A（分類順序再設計）の理解：
修正B（ポータルリスト拡充）の理解：
修正C（その他判定新設）の理解：
修正D（SEO判定厳格化）の理解：
修正E（非オーガニック除外）の理解：
修正F（URL正規化）の理解：
修正G（sleep撤廃）の理解：
修正H（CSVメタ情報追加）の理解：
修正I（広告スニペット重複）の理解：
変更対象ファイル：
変更しないファイル：
懸念点：
```

### ステップ2：バックアップ

```bash
cd /home/adminterml1/services/scraping/serp_diagnosis/
cp app.py app.py.bak_v3
cp config.py config.py.bak_v3
cp classifier.py classifier.py.bak_v3
cp chrome_extension/content.js chrome_extension/content.js.bak.v2.1
```

### ステップ3：修正実施

以下の順序で修正する：

1. config.py — ドメインリストの拡充・追加（修正B, C）
2. classifier.py — 分類順序の再設計・SEO判定変更（修正A, D）
3. content.js — 非オーガニック除外・URL正規化・広告スニペット（修正E, F, I）
4. app.py — sleep撤廃・CSVメタ情報追加・サマリー計算変更（修正G, H, セクション4）
5. results.html — サマリーパネルの表示変更（セクション4）

### ステップ4：変更差分の報告

各ファイルの変更差分を報告する。

### ステップ5：Flaskサービス再起動

```bash
# app.py, config.py, classifier.pyの変更を反映
sudo systemctl restart serp_diagnosis  # またはプロセス再起動
```

**注意：** Chrome拡張（content.js）の変更は chrome://extensions/ で「更新」を押して反映する。

### ステップ6：完了報告

```
【完了報告】
修正A（分類順序再設計）：完了 / 差異あり（理由：...）
修正B（ポータルリスト拡充）：完了 / 差異あり（理由：...）
修正C（その他判定新設）：完了 / 差異あり（理由：...）
修正D（SEO判定厳格化）：完了 / 差異あり（理由：...）
修正E（非オーガニック除外）：完了 / 差異あり（理由：...）
修正F（URL正規化）：完了 / 差異あり（理由：...）
修正G（sleep撤廃）：完了 / 差異あり（理由：...）
修正H（CSVメタ情報追加）：完了 / 差異あり（理由：...）
修正I（広告スニペット重複）：完了 / 差異あり（理由：...）
UI表示整合：完了 / 差異あり（理由：...）
```

---

## 6. テスト手順

### テスト1：分類精度の確認

1. Chrome拡張を「更新」
2. 「車のスピード修理」で検索 →「そのほかの検索結果」を4回押す
3. 読み取り → 分析
4. 結果画面で確認：
   - 「その他のお店やサービス」がオーガニック結果に含まれていないこと
   - YouTube、知恵袋が「その他」に分類されていること
   - 楽天Car、カーコン等が「ポータル・大手」に分類されていること
   - 「企業HP」に残っているのが個別企業サイトであること

### テスト2：URL重複の確認

- 同一URLが異なる順位で重複登録されていないこと
- parts.mobiful.jp が1件のみ表示されること

### テスト3：CSVの確認

- CSVエクスポートして先頭にメタ情報・集計があること
- 検索フレーズが記録されていること

### テスト4：処理時間の確認

- 62件程度の処理が約2分で完了すること（従来約4分）

---

## 7. 禁止事項

| 項目 | 内容 |
|------|------|
| ファイル追加 | 新しいファイルを作成しない |
| 指示外のファイル修正 | 指定された5ファイル以外は触らない |
| 勝手な改善 | 指示書にない改善は行わない |
| 分類名の変更 | 「ポータル・大手」「その他」「企業HP（SEOあり）」「企業HP（SEOなし）」の名称を変えない |

---

## 8. 差異報告のルール

指示書と異なる実装をした場合は、必ず以下の形式で報告すること。

```
【差異報告】
指示書の内容：（何を指示されていたか）
実際の実装：（何をしたか）
理由：（なぜ変えたか）
影響：（他の箇所への影響はあるか）
```

---

## 9. 期待される結果

修正後、「車のスピード修理」+「そのほかの検索結果」4回の条件で：

| 分類 | 修正前 | 修正後（期待値） |
|------|--------|----------------|
| 広告 | 3件 | 3件（変化なし） |
| ポータル・大手 | 3件 | 8〜12件（リスト拡充で増加） |
| その他 | 0件 | 5〜10件（YouTube/知恵袋/公共等） |
| 企業HP（SEOあり） | 36件 | 20〜30件（判定厳格化+その他への移動で減少） |
| 企業HP（SEOなし） | 23件 | 15〜22件（純粋な営業候補に近づく） |
| 合計 | 65件 | 60件前後（非オーガニック除外で若干減少） |

---

## 10. 今後の展望（本指示書の範囲外）

本修正は分類精度改善の初回である。以下は今後のサイクルで段階的に取り組む。

- ドメインリストの育成：実データを見ながらリストを追加
- ページ内容からの自動分類：titleに「比較」「ランキング」等を含むサイトの自動判定
- 業種別ポータル判定：検索フレーズから業種を推定し、業種固有のポータルを自動認識
- SEO判定の高度化：構造化データのtype（LocalBusiness等）まで確認

---

以上、スクレイピングプロジェクトより
