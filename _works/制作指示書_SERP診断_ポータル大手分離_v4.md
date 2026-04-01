# 制作指示書：SERP診断ツール ポータル・大手分離 v4

**スクレイピングPj → Claude Code｜2026年4月1日**

---

## 1. 本指示書の目的

SERP診断ツールの分類を改善する。2つの修正を行う。

1. **「ポータル・大手」カテゴリを「ポータル」と「大手」の2つに分離する**
2. **ポータルドメインリストを拡充し、「企業HP（SEOなし）」の精度を上げる**

---

## 2. 背景

### 2.1 問題

6つの検索フレーズ（襖の張り替え、障子の張り替え、ドアノブの交換、鍵の交換、雨戸の修理、畳の表替え）で実動テストした結果、「企業HP（SEOなし）」135件のうち58件（43%）がポータル・メディア等の非企業サイトであった。

原因：ドメインリストにリフォーム・住宅系ポータルが登録されていなかった。

### 2.2 ポータルと大手の定義

| カテゴリ | 定義 | 例 |
|----------|------|-----|
| ポータル | 口コミ・比較・仲介・掲載で他社の情報を集約するサイト。固有の企業サイトではない | くらしのマーケット、食べログ、SUUMO、エキテン |
| 大手 | 自社で商品・サービス・プラットフォームを運営する大手企業 | 楽天、Amazon、イエローハット、カーコンビニ倶楽部 |

**企業HPに残すもの（ポータルでも大手でもない）：**
- 大手HC（コメリ、カインズ等）→ 自社商品を提供する企業HP
- 大手メーカー（LIXIL、パナソニック等）→ 自社商品を提供する企業HP
- SEOが強い個別企業（鳥松、金沢屋、鍵猿等）→ 固有の企業サイト

---

## 3. 修正対象ファイル

```
config.py       ← 修正対象①（ドメインリスト分離・追加）
classifier.py   ← 修正対象②（分類ロジック変更）
app.py          ← 修正対象③（サマリー計算・CSV集計）
templates/results.html ← 修正対象④（サマリーパネル表示）
static/style.css      ← 修正対象⑤（バッジ・サマリーのスタイル追加）
```

**上記以外のファイルは変更しない。**

---

## 4. 修正内容

### 修正A：ドメインリストの分離・追加（config.py）

現在の `PORTAL_DOMAINS` を `PORTAL_DOMAINS` と `MAJOR_DOMAINS` に分離し、新規ドメインを追加する。

#### PORTAL_DOMAINS（修正後の全体）

```python
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
```

#### MAJOR_DOMAINS（新規追加）

```python
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
```

#### MEDIA_DOMAINS（追加分）

既存リストの末尾に以下を追加する。

```python
    "allabout.co.jp", "travelbook.co.jp",
    "iekoma.com", "makit.jp", "housejoho.com",
    "shuminoengei.jp",
```

#### QA_DOMAINS（追加分）

既存リストの末尾に以下を追加する。

```python
    "question.realestate.yahoo.co.jp",
```

---

### 修正B：分類ロジックの変更（classifier.py）

#### B-1. importの変更

```python
from config import (
    PORTAL_DOMAINS, MAJOR_DOMAINS, SEO_THRESHOLDS,
    VIDEO_DOMAINS, QA_DOMAINS, SNS_DOMAINS, BLOG_DOMAINS, MEDIA_DOMAINS,
)
```

#### B-2. 分類順序

修正後の分類順序は以下の通り。

```
1. 広告           ← is_adフラグ（変更なし）
2. ポータル       ← PORTAL_DOMAINS一致（★カテゴリ名変更）
3. 大手           ← MAJOR_DOMAINS一致（★新設）
4. その他         ← 動画/QA/SNS/ブログ/公共/メディア（変更なし）
5. 企業HP（SEOあり）← SEO判定（変更なし）
6. 企業HP（SEOなし）← 残り（変更なし）
```

#### B-3. 具体的な修正箇所

現在の「ポータル・大手」判定部分を以下に置き換える。

```python
    # 2. ポータル
    for portal in PORTAL_DOMAINS:
        if domain == portal or domain.endswith("." + portal):
            return "ポータル"

    # 3. 大手
    for major in MAJOR_DOMAINS:
        if domain == major or domain.endswith("." + major):
            return "大手"
```

---

### 修正C：サマリー計算・CSV集計の変更（app.py）

#### C-1. resultsルートのサマリー計算（200行目付近）

修正前：
```python
        portal_count = category_counts.get("ポータル・大手", 0)
```

修正後：
```python
        portal_count = category_counts.get("ポータル", 0)
        major_count = category_counts.get("大手", 0)
```

`locations_data` の辞書にも `major_count` を追加する。

修正前：
```python
            "portal_count": portal_count,
```

修正後：
```python
            "portal_count": portal_count,
            "major_count": major_count,
```

#### C-2. 診断コメントのポータル支配判定（221行目付近）

修正前：
```python
        if total_organic > 0 and portal_count / total_organic >= 0.7:
            comments.append("ポータル支配が強いが、裏を返せばチャンス")
```

修正後：
```python
        portal_major_total = portal_count + major_count
        if total_organic > 0 and portal_major_total / total_organic >= 0.7:
            comments.append("ポータル支配が強いが、裏を返せばチャンス")
```

#### C-3. CSVエクスポートの集計行（269行目付近）

修正前：
```python
    writer.writerow(["ポータル・大手", category_counts.get("ポータル・大手", 0)])
```

修正後：
```python
    writer.writerow(["ポータル", category_counts.get("ポータル", 0)])
    writer.writerow(["大手", category_counts.get("大手", 0)])
```

---

### 修正D：サマリーパネル表示の変更（templates/results.html）

現在の「ポータル・大手」のサマリーアイテム1個を、「ポータル」と「大手」の2個に分割する。

修正前（49-52行目付近）：
```html
                        <div class="summary-item summary-portal">
                            <span class="summary-label">ポータル・大手</span>
                            <span class="summary-value">{{ data.portal_count }}件</span>
                        </div>
```

修正後：
```html
                        <div class="summary-item summary-portal">
                            <span class="summary-label">ポータル</span>
                            <span class="summary-value">{{ data.portal_count }}件</span>
                        </div>
                        <div class="summary-item summary-major">
                            <span class="summary-label">大手</span>
                            <span class="summary-value">{{ data.major_count }}件</span>
                        </div>
```

---

### 修正E：CSSスタイルの追加（static/style.css）

以下のスタイルを追加する。

```css
.summary-major .summary-value { color: #ff7043; }
.badge-大手 { background: #bf360c; color: #ffab91; }
.badge-ポータル { background: #e65100; color: #ffcc80; }
```

既存の `.badge-ポータル-大手` はそのまま残しておいてよい（過去データの表示用）。

---

## 5. 作業手順

### ステップ1：把握レポート出力

```
【把握レポート】
修正A（ドメインリスト分離・追加）の理解：
修正B（分類ロジック変更）の理解：
修正C（サマリー計算・CSV集計）の理解：
修正D（サマリーパネル表示）の理解：
修正E（CSSスタイル追加）の理解：
変更対象ファイル：
変更しないファイル：
懸念点：
```

### ステップ2：バックアップ

```bash
cd /home/adminterml1/services/scraping/serp_diagnosis/
cp config.py config.py.bak_v4
cp classifier.py classifier.py.bak_v4
cp app.py app.py.bak_v4
cp templates/results.html templates/results.html.bak_v4
cp static/style.css static/style.css.bak_v4
```

### ステップ3：修正実施

以下の順序で修正する：

1. config.py — ドメインリスト分離・追加（修正A）
2. classifier.py — 分類ロジック変更（修正B）
3. app.py — サマリー計算・CSV集計変更（修正C）
4. templates/results.html — サマリーパネル変更（修正D）
5. static/style.css — スタイル追加（修正E）

### ステップ4：変更差分の報告

各ファイルの変更差分を報告する。

### ステップ5：Flaskサービス再起動

```bash
sudo systemctl restart serp_diagnosis
```

**注意：** Chrome拡張（content.js）は変更なしのため「更新」不要。

### ステップ6：完了報告

```
【完了報告】
修正A（ドメインリスト分離・追加）：完了 / 差異あり（理由：...）
修正B（分類ロジック変更）：完了 / 差異あり（理由：...）
修正C（サマリー計算・CSV集計）：完了 / 差異あり（理由：...）
修正D（サマリーパネル表示）：完了 / 差異あり（理由：...）
修正E（CSSスタイル追加）：完了 / 差異あり（理由：...）
差異の有無：
```

---

## 6. テスト手順

### テスト：分類精度の確認

1. 「襖の張り替え」で検索 →「そのほかの検索結果」を4回押す
2. Chrome拡張で読み取り → 分析
3. 結果画面で確認：
   - サマリーパネルに「ポータル」と「大手」が別々に表示されること
   - くらしのマーケット、ミツモア、リショップナビ等が「ポータル」に分類されること
   - All About、イエコマ等が「その他」に分類されること
   - 「企業HP（SEOなし）」に残っているのが固有の企業サイトであること
4. CSVエクスポートして、集計行に「ポータル」と「大手」が別行で出力されていること

---

## 7. 禁止事項

| 項目 | 内容 |
|------|------|
| 指定外のファイル変更 | 5ファイル以外は触らない |
| 既存ドメインの削除 | 移動はするが削除はしない |
| 指示書にないドメインの追加 | 勝手に追加しない |
| 分類カテゴリの名称変更 | 「ポータル」「大手」「企業HP（SEOあり）」「企業HP（SEOなし）」「その他」の名称は本指示書の通りにする |
| 分類ロジックの変更 | 修正B以外のロジック変更は行わない |

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

## 9. 過去データへの影響

分類カテゴリ名が「ポータル・大手」→「ポータル」「大手」に変わるため、過去のセッションの結果を閲覧した場合、サマリーパネルのカウントが変わる可能性がある（過去データのcategory列は「ポータル・大手」のまま）。

これは既知の影響であり、対応不要とする。過去データは参考程度であり、必要時に再分析すればよい。

---

以上、スクレイピングプロジェクトより
