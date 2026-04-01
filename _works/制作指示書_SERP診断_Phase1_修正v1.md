# 制作指示書：SERP診断ツール Phase 1 修正

**スクレイピングPj → Claude Code｜2026年3月26日**

---

## 1. 本指示書の目的

SERP診断ツール Phase 1 の初回実動テストで発覚したバグを修正する。
対象はサーバー側（app.py）とChrome拡張側（content.js）の2ファイルのみ。
他のファイル（analyzer.py, classifier.py, database.py, config.py, templates/, static/）には一切手を加えないこと。

---

## 2. 前提情報

### 2.1 実動テストの結果

- Chrome拡張でGoogle検索結果を読み取り、サーバーに送信するパイプラインは正常に動作した
- 広告4件 + オーガニック30件が取得され、分類・DB保存・結果表示まで完了
- ただし以下の3つのバグが確認された

### 2.2 配置先

```
/home/adminterml1/services/scraping/serp_diagnosis/
├── app.py                     ← 修正対象①
├── chrome_extension/
│   └── content.js             ← 修正対象②（差し替え済みファイルあり）
│   └── content.js.bak         ← 旧版バックアップ（触らない）
└── （その他のファイルは変更禁止）
```

### 2.3 現在のGoogle HTML構造（2026年3月時点）

初回テストのセレクタ調査で判明した事実：

| 要素 | 状態 |
|------|------|
| `div.g` | 0個（従来のセレクタでは取得不可） |
| `div.MjjYud` | 28個（新しい検索結果ラッパー） |
| `#rso` | あり |
| h3内のaタグ | `h3.closest("a")` は null。`h3.querySelector("a")` で内部aからURLを取得可能 |
| `#tads`（広告） | 存在するがh3は0個。外部リンクベースで抽出する必要あり |

**content.jsはこの構造に対応した新版に既に差し替え済み。**
本指示書ではこの新版content.jsの「追加修正」を指示する。

---

## 3. 修正内容

### 修正①：content.js — オーガニック結果の重複排除

**現象：** 同じURLが2回ずつ取得される（30件中14件が重複）。
例：carcon.co.jp が2回、ikeuchi-jidousha.com が4回。

**原因推定：** `div.MjjYud` ブロックの中にネストした構造がある場合、同じh3を親と子の両方で拾ってしまっている。

**修正方針：** `extractOrganic()` 関数で、結果をorganicListに追加する際にURL重複チェックを入れる。同じURLが既にリストにある場合はスキップする。

**修正箇所：** `extractOrganic()` 関数内

**修正方法：**

```javascript
function extractOrganic(organicList) {
  const searchContainer = document.querySelector("#rso") || document.querySelector("#search");
  if (!searchContainer) return;

  let rank = 1;
  const seenUrls = new Set();  // ← 追加：重複チェック用

  // 方法1: div.MjjYud ベース（2026年版Google）
  const mjjBlocks = searchContainer.querySelectorAll("div.MjjYud");
  if (mjjBlocks.length > 0) {
    for (const block of mjjBlocks) {
      if (block.closest("#tads") || block.closest("#bottomads")) continue;

      const results = parseMjjYudBlock(block, rank);
      for (const result of results) {
        // ★ 重複チェック追加
        if (seenUrls.has(result.url)) continue;
        seenUrls.add(result.url);
        organicList.push(result);
        rank++;
      }
    }
  }

  // 方法2, 方法3 にも同様に seenUrls チェックを追加すること
  // ...
}
```

**注意：** 方法2（div.g）・方法3（h3ベース）のフォールバックにも同じseenUrlsチェックを適用すること。

---

### 修正②：content.js — 広告タイトルからURL文字列を除去

**現象：** 広告のタイトルが「池内自動車https://www.ikeuchi-jidousha.com板金は高いという常識を覆します」のようにURLが混入している。

**原因：** `parseAdContainer2026()` でリンク要素のtextContentを取得する際、子要素にURL表示用のテキストが含まれている。

**修正方針：** タイトル文字列からURL部分を除去するクリーニング関数を追加する。

**追加する関数：**

```javascript
function cleanTitle(text) {
  if (!text) return "";
  // URL文字列を除去（http:// または https:// で始まる部分）
  let cleaned = text.replace(/https?:\/\/[^\s\u3000]+/g, "").trim();
  // 連続する空白を1つに
  cleaned = cleaned.replace(/\s+/g, " ");
  return cleaned;
}
```

**適用箇所：** 以下の箇所でタイトルを設定する直前に `cleanTitle()` を通す。

1. `parseAdContainer2026()` 内でタイトルを設定する全箇所
2. `parseBlockForAd()` 内でタイトルを設定する全箇所
3. `parseMjjYudBlock()` 内でもタイトル取得時に適用（防御的に）

**例：**

```javascript
// 修正前
if (linkText.length > 5 && linkText.length < 200) {
  title = linkText;
}

// 修正後
const cleanedText = cleanTitle(linkText);
if (cleanedText.length > 5 && cleanedText.length < 200) {
  title = cleanedText;
}
```

---

### 修正③：app.py — CSVエクスポートの日本語ファイル名対応

**現象：** CSVエクスポートでぐるぐる回り（ダウンロードされない）。

**原因：** `Content-Disposition` ヘッダーに日本語ファイル名を直接入れており、`latin-1` エンコードエラーが発生。

**エラーログ：**
```
UnicodeEncodeError: 'latin-1' codec can't encode characters in position 57-68: ordinal not in range(256)
```

**修正箇所：** `export_csv()` 関数のレスポンス部分

**修正方法：** RFC 5987形式でUTF-8ファイル名を指定する。

```python
# 修正前
query = session["query"] or "serp"
date = datetime.now().strftime("%Y%m%d")
filename = f"serp_diagnosis_{query}_{date}.csv"

return Response(
    output.getvalue(),
    mimetype="text/csv",
    headers={"Content-Disposition": f"attachment; filename={filename}"}
)

# 修正後
from urllib.parse import quote

query = session["query"] or "serp"
date = datetime.now().strftime("%Y%m%d")
filename_jp = f"serp_diagnosis_{query}_{date}.csv"
filename_ascii = f"serp_diagnosis_{date}.csv"
filename_encoded = quote(filename_jp)

return Response(
    output.getvalue(),
    mimetype="text/csv",
    headers={
        "Content-Disposition": f"attachment; filename={filename_ascii}; filename*=UTF-8''{filename_encoded}"
    }
)
```

**解説：**
- `filename=` にはASCII安全なフォールバック名を設定
- `filename*=UTF-8''` にはURLエンコードした日本語ファイル名を設定
- ブラウザは `filename*` を優先するため、日本語ファイル名でダウンロードされる
- `from urllib.parse import quote` をファイル先頭のimport群に移動しても可

---

## 4. 作業手順

### ステップ1：把握レポート出力

本指示書を読み終えたら、以下の形式で把握レポートを出力すること。

```
【把握レポート】
修正①の理解：（具体的に何をするか）
修正②の理解：（具体的に何をするか）
修正③の理解：（具体的に何をするか）
変更対象ファイル：（ファイル名を列挙）
変更しないファイル：（明示）
懸念点：（あれば）
```

### ステップ2：content.js の修正

1. `/home/adminterml1/services/scraping/serp_diagnosis/chrome_extension/content.js` を編集
2. 修正①（重複排除）を適用
3. 修正②（タイトルURL除去）を適用
4. 修正後、変更箇所の差分を報告

### ステップ3：app.py の修正

1. `/home/adminterml1/services/scraping/serp_diagnosis/app.py` を編集
2. 修正③（CSVファイル名）を適用
3. 修正後、変更箇所の差分を報告

### ステップ4：Flask再起動

```bash
# 5112ポートのプロセスを特定して停止
kill $(ss -tlnp | grep :5112 | grep -oP 'pid=\K[0-9]+') 2>/dev/null
sleep 2

# 再起動
cd /home/adminterml1/services/scraping/serp_diagnosis
nohup python3 app.py > serp_diagnosis.log 2>&1 &
echo "PID: $!"

# 起動確認
sleep 2
curl -s -o /dev/null -w "HTTP %{http_code}" http://localhost:5112/ && echo " - OK"
```

### ステップ5：動作確認

以下のcurlテストでCSVエクスポートが正常に動くことを確認する。

```bash
# テストデータでセッション作成
curl -s -X POST http://localhost:5112/api/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "query": "テスト検索",
    "pages": [{
      "query": "テスト検索",
      "pageNumber": 1,
      "url": "https://www.google.co.jp/search?q=test",
      "organic": [
        {"rank": 1, "title": "テストサイト1", "url": "https://example.com", "snippet": "テスト"},
        {"rank": 2, "title": "テストサイト2", "url": "https://example.org", "snippet": "テスト2"}
      ],
      "ads": []
    }],
    "device": "desktop"
  }'

# レスポンスからsession_idを取得し、CSVエクスポートをテスト
# （session_idは上記レスポンスのJSONから取得すること）
```

CSVが正常にダウンロードされ、ファイル名に日本語が含まれることを確認。

### ステップ6：完了報告

```
【完了報告】
修正①（重複排除）：完了 / 差異あり（理由：...）
修正②（タイトルURL除去）：完了 / 差異あり（理由：...）
修正③（CSVファイル名）：完了 / 差異あり（理由：...）
Flask再起動：PID=（数値）
動作確認結果：（結果）
```

---

## 5. 禁止事項

| 項目 | 内容 |
|------|------|
| ファイル追加 | 新しいファイルを作成しない |
| 他ファイル修正 | analyzer.py, classifier.py, database.py, config.py, templates/, static/ は触らない |
| ロジック変更 | 分類ロジック、DB構造、APIインターフェースは変更しない |
| 勝手な改善 | 指示書にない「ついでの改善」は行わない |
| デフォルト値への依存 | コマンドは完全な形で実行する |

---

## 6. 差異報告のルール

指示書と異なる実装をした場合は、必ず以下の形式で報告すること。

```
【差異報告】
指示書の内容：（何を指示されていたか）
実際の実装：（何をしたか）
理由：（なぜ変えたか）
影響：（他の箇所への影響はあるか）
```

---

以上、スクレイピングプロジェクトより
