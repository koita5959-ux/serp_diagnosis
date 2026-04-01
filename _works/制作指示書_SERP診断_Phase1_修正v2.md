# 制作指示書：SERP診断ツール Phase 1 修正 v2

**スクレイピングPj → Claude Code｜2026年3月27日**

---

## 1. 本指示書の目的

SERP診断ツール Phase 1 の実動テスト（2026/3/27）で発覚した問題を修正する。

**最重要課題：** GoogleのスマホDOM構造が変化しており、検索結果の取得数が大幅に不足している。
Chrome拡張のDOM解析（content.js）を2026年3月時点の構造に対応させ、合わせて関連する不具合を修正する。

---

## 2. 前提情報

### 2.1 実動テストの結果

テスト条件：
- Chrome F12でスマホ表示
- 検索語：「車のちょっとしたキズ」
- 「そのほかの検索結果」ボタンを3回押して追加読み込み
- Chrome拡張で読み取り → 分析実行

確認された問題：

| # | 問題 | 深刻度 |
|---|------|--------|
| 1 | オーガニック結果が13件しか取得できない（期待値30件以上） | ★★★ |
| 2 | 結果画面のステータスが「running」のまま更新されない | ★★ |
| 3 | 広告タイトルにURL文字列が混入する | ★ |
| 4 | スマホ追加読み込みでpopup.jsの重複チェックが誤動作する可能性 | ★★ |

### 2.2 DOM調査の結果（2026年3月27日実機確認）

F12コンソールで確認した**現在のGoogleスマホ版DOM構造**：

```
#rso内:
  h3タグ           → 0個（★ 存在しない）
  div.MjjYud       → 25個
  div.g             → 0個
  外部リンク        → 88個
  ユニークドメイン  → 16個

role="heading" の分布:
  aria-level="1"   → 8個（UI要素：「共有」「マイ アド センター」等）
  aria-level="2"   → 9個（セクション見出し：「動画」「スポンサー広告」等）
  aria-level="3"   → 18個（★ 検索結果タイトル + AI概要 + ショッピング）
  aria-level="4"   → 8個（「他の人はこちらも検索」のみ）
```

**重要な発見：**
- **h3タグは使われていない。** `<div role="heading" aria-level="3">` がタイトル
- タイトルの親にaタグがあればURLが取れる（`h.closest("a")`）
- `aria-level="3"` の18件の内訳：
  - AI概要の見出し 2件（URLなし → 除外対象）
  - 広告タイトル 2件（buv.jp）
  - オーガニック結果 11件（実際の検索結果）
  - Googleショッピング 3件（google.comドメイン → 除外対象）

### 2.3 スマホ版「そのほかの検索結果」の挙動

- ボタンを押すと**ページ遷移ではなくDOM内に追加読み込み**される
- URLは変わらない（`start` パラメータが更新されない）
- 上部の結果はそのままで、下に追記されていく
- つまり「読み取り」1回で全結果を取得する設計が正しい

### 2.4 配置先

```
/home/adminterml1/services/scraping/serp_diagnosis/
├── app.py                     ← 修正対象①
├── chrome_extension/
│   ├── content.js             ← 修正対象②
│   └── popup.js               ← 修正対象③
├── templates/
│   └── results.html           ← 修正対象④
└── （その他のファイルは変更禁止）
```

---

## 3. 修正内容

### 修正①：content.js — h3からrole="heading"への移行（最重要）

**現象：** h3ベースのセレクタがスマホ版Googleで機能せず、検索結果を拾えない。

**原因：** 2026年3月時点のGoogleスマホ版では、検索結果タイトルに `<h3>` ではなく `<div role="heading" aria-level="3">` を使用している。

**修正方針：** 全てのh3セレクタを `h3, [role="heading"][aria-level="3"]` に拡張する。ただし以下を除外すること。

#### 3.1 除外すべきaria-level="3"要素

以下のlevel="3"要素は検索結果ではないため、除外ロジックが必要。

| 種類 | 判定方法 | 対応 |
|------|----------|------|
| AI概要の見出し | closest("a")がない（URLなし） | URLがなければスキップ |
| Googleショッピング | URLのドメインがgoogle.com | google.comドメインは既存の除外ロジックで対応済み |

#### 3.2 修正が必要な関数の一覧

以下の関数内で h3 への参照を `h3, [role="heading"][aria-level="3"]` に変更すること。

**（A）`extractOrganic()` 関数**

```javascript
// 修正前
const mjjBlocks = searchContainer.querySelectorAll("div.MjjYud");

// ここは変更不要。MjjYudブロックの走査は維持する。
// 変更が必要なのは parseMjjYudBlock() 内のh3参照。
```

**（B）`parseMjjYudBlock()` 関数**

```javascript
// 修正前
const h3s = block.querySelectorAll("h3");

// 修正後
const h3s = block.querySelectorAll('h3, [role="heading"][aria-level="3"]');
```

この変更で、MjjYudブロック内のタイトル要素を検出できるようになる。

**（C）`parseOrganicBlock()` 関数（フォールバック）**

```javascript
// 修正前
const h3 = block.querySelector("h3");

// 修正後
const h3 = block.querySelector('h3, [role="heading"][aria-level="3"]');
```

**（D）`extractOrganic()` 内の方法3（最終フォールバック）**

```javascript
// 修正前
const h3s = searchContainer.querySelectorAll("h3");

// 修正後
const h3s = searchContainer.querySelectorAll('h3, [role="heading"][aria-level="3"]');
```

**（E）`findUrl()` 関数**

```javascript
// 修正前
// 1. h3内部のaタグ
const innerA = h3.querySelector("a");
// ...
// 2. h3を包含するaタグ
const parentA = h3.closest("a");

// 修正後（そのまま動作する。引数名がh3でもdiv[role=heading]でも
// querySelector/closestは正常に動く。変更不要。）
```

**（F）`findSnippet()` 関数**

```javascript
// 修正前
const searchBlock = container || h3.closest("div.MjjYud") || h3.closest("[data-hveid]") || h3.parentElement?.parentElement?.parentElement;
// ...
if (el.querySelector("h3") || el.closest("h3")) continue;

// 修正後
const searchBlock = container || h3.closest("div.MjjYud") || h3.closest("[data-hveid]") || h3.parentElement?.parentElement?.parentElement;
// ...
if (el.querySelector('h3, [role="heading"][aria-level="3"]') || el.closest('h3, [role="heading"][aria-level="3"]')) continue;
```

**（G）`parseMjjYudBlock()` 内のスキップ対象タイトル**

```javascript
// 修正前
if (title === "地図" || title === "さらに表示" || title === "関連する質問" ||
    title === "他の人はこちらも質問" || title === "強調スニペットについて") continue;

// 修正後：AI概要の見出し等を追加
if (title === "地図" || title === "さらに表示" || title === "関連する質問" ||
    title === "他の人はこちらも質問" || title === "強調スニペットについて" ||
    title === "車のちょっとした傷の補修方法" || // ← これはダメ。固定文字列ではなく汎用的な除外が必要
    ) continue;

// 正しい修正：URLがないlevel="3"を除外する
// parseMjjYudBlock内で、URLが取得できなかった場合にスキップするロジックは既にある：
//   if (!url || url.includes("google.com/search") ...) continue;
// ただしAI概要の見出しはURLなしなのでfindUrl()が空文字を返し、スキップされる。
// → 既存ロジックで対応済み。追加のスキップ条件は不要。
```

**（H）広告抽出 `extractAds()` 関数内**

```javascript
// 修正前
const h3s = container.querySelectorAll("h3");

// 修正後
const h3s = container.querySelectorAll('h3, [role="heading"][aria-level="3"]');
```

#### 3.3 注意事項

- `findUrl()` と `findSnippet()` は引数名が `h3` だが、実際にはdiv要素が渡されるケースが増える。DOMのquerySelector/closestはタグに依存しないので動作上の問題はない
- デスクトップ版GoogleではまだH3が使われている可能性があるため、`h3` セレクタは削除せず**追加**すること（`h3, [role="heading"]...`）

---

### 修正②：content.js — 広告タイトルのURL混入除去

**現象：** 広告のタイトルが `buv.jphttps://www.buv.jp小さなキズ凹み修理2,980円から` のようにURL文字列が混入。

**原因：** `parseAdContainer2026()` のh3なしルートで `cleanTitle()` がURL除去しきれていない。現在の正規表現 `/https?:\/\/[^\s\u3000]+/g` は `buv.jp` のようなプロトコルなしのURLを除去できない。

**修正方針：** `cleanTitle()` 関数のURL除去パターンを強化する。

```javascript
function cleanTitle(text) {
  if (!text) return "";
  // URL文字列を除去（https://... 形式）
  let cleaned = text.replace(/https?:\/\/[^\s\u3000]+/g, "").trim();
  // ドメイン形式のテキストも除去（例: "www.example.com" "example.co.jp"）
  cleaned = cleaned.replace(/(?:www\.)?[a-zA-Z0-9-]+\.[a-zA-Z]{2,}(?:\.[a-zA-Z]{2,})?(?:\/[^\s\u3000]*)?/g, "").trim();
  // 連続する空白を1つに
  cleaned = cleaned.replace(/\s+/g, " ");
  return cleaned;
}
```

**適用箇所の確認：** `parseAdContainer2026()` と `parseBlockForAd()` 内の全てのタイトル設定箇所で `cleanTitle()` が呼ばれていることを確認すること。現在のコードでは一部 `cleanTitle` を通していない箇所がある可能性があるため、全箇所を確認・修正すること。

---

### 修正③：popup.js — 追加読み込み方式への対応

**現象：** スマホ版Googleの「そのほかの検索結果」はページ遷移ではなくDOM追加読み込みのため、URLが変わらない。popup.jsの重複チェックがURL単位のため、2回目の読み取りが「既に読み取り済み」と判定される。

**原因：** `onRead()` 内の以下の重複チェック。

```javascript
// 現在のコード
const isDuplicate = accumulatedData.some(
  p => p.url === data.url  // ← URLが変わらないので常に重複判定される
);
```

**修正方針：** スマホ追加読み込み方式では、1回の「読み取り」で画面上の全結果を取得する設計とする。同じURLからの読み取りは「上書き」として扱う。

```javascript
// 修正後
// 同じURLからの読み取りの場合、件数が増えていれば上書き（追加読み込みされた結果を反映）
const existingIndex = accumulatedData.findIndex(p => p.url === data.url);
if (existingIndex >= 0) {
  const existingCount = accumulatedData[existingIndex].organic.length + accumulatedData[existingIndex].ads.length;
  const newCount = data.organic.length + data.ads.length;
  if (newCount > existingCount) {
    // 追加読み込みで増えた → 上書き
    accumulatedData[existingIndex] = data;
    await chrome.storage.local.set({ accumulatedData });
    updateUI();
    showMessage(`${newCount}件に更新しました（+${newCount - existingCount}件）`, "success");
    return;
  } else {
    showMessage(`変化なし（${existingCount}件のまま）。「そのほかの検索結果」を押してから再読み取りしてください`, "info");
    return;
  }
}
```

**また、`extractPageNumber()` も修正する：**

```javascript
// 修正前
function extractPageNumber() {
  const params = new URLSearchParams(location.search);
  const start = parseInt(params.get("start") || "0");
  return Math.floor(start / 10) + 1;
}

// 修正後：追加読み込みの場合は取得した結果数から推定
function extractPageNumber() {
  // URLのstartパラメータがあればそれを使う（ページ遷移型）
  const params = new URLSearchParams(location.search);
  const start = parseInt(params.get("start") || "0");
  if (start > 0) {
    return Math.floor(start / 10) + 1;
  }
  // startがない場合は1を返す（追加読み込み型は全結果を1回で取得）
  return 1;
}
```

---

### 修正④：results.html — ステータスの自動更新

**現象：** Chrome拡張から分析を送信すると、結果ページが即座に開かれるが、バックグラウンド分析がまだ完了していないため「状態: running」のまま表示される。分析完了後もページをリロードしない限りステータスが更新されない。

**修正方針：** ステータスが「running」の場合、JavaScriptで定期的にステータスを確認し、完了したらページをリロードする。

**（A）app.py にステータス確認APIを追加：**

```python
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
```

**（B）results.html の末尾にポーリングスクリプトを追加：**

```html
{% if session.status == 'running' %}
<script>
(function() {
    const sessionId = "{{ session.id }}";
    const interval = setInterval(async () => {
        try {
            const res = await fetch(`/api/status/${sessionId}`);
            const data = await res.json();
            if (data.status !== "running") {
                clearInterval(interval);
                location.reload();
            }
        } catch (e) {
            console.error("ステータス確認エラー:", e);
        }
    }, 3000);  // 3秒ごとに確認
})();
</script>
{% endif %}
```

---

## 4. 作業手順

### ステップ1：把握レポート出力

本指示書を読み終えたら、以下の形式で把握レポートを出力すること。

```
【把握レポート】
修正①の理解：（h3→role="heading"移行について、具体的に何をするか）
修正②の理解：（広告タイトルURL除去について、具体的に何をするか）
修正③の理解：（popup.js重複チェックについて、具体的に何をするか）
修正④の理解：（ステータス自動更新について、具体的に何をするか）
変更対象ファイル：（ファイル名を列挙）
変更しないファイル：（明示）
懸念点：（あれば）
```

### ステップ2：content.js の修正

1. `/home/adminterml1/services/scraping/serp_diagnosis/chrome_extension/content.js` のバックアップを取る
2. 修正①（h3→role="heading"移行）を適用
3. 修正②（広告タイトルURL除去）を適用
4. 修正後、変更箇所の差分を報告

### ステップ3：popup.js の修正

1. `/home/adminterml1/services/scraping/serp_diagnosis/chrome_extension/popup.js` のバックアップを取る
2. 修正③（追加読み込み対応）を適用
3. 修正後、変更箇所の差分を報告

### ステップ4：app.py の修正

1. 修正④（A）のステータス確認APIを追加
2. 修正後、変更箇所の差分を報告

### ステップ5：results.html の修正

1. 修正④（B）のポーリングスクリプトを追加
2. 修正後、変更箇所の差分を報告

### ステップ6：Flask再起動

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

### ステップ7：サーバー側動作確認

```bash
# テストデータで分析APIをテスト
curl -s -X POST http://localhost:5112/api/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "query": "テスト修正v2",
    "pages": [{
      "query": "テスト修正v2",
      "pageNumber": 1,
      "url": "https://www.google.co.jp/search?q=test",
      "organic": [
        {"rank": 1, "title": "テストサイト1", "url": "https://example.com", "snippet": "テスト"},
        {"rank": 2, "title": "テストサイト2", "url": "https://example.org", "snippet": "テスト2"}
      ],
      "ads": [
        {"title": "広告テスト", "url": "https://ads.example.com", "snippet": "広告", "position": "top"}
      ]
    }],
    "device": "desktop"
  }'

# ステータスAPIテスト（上記のsession_idを使用）
# curl -s http://localhost:5112/api/status/{session_id}
```

### ステップ8：完了報告

```
【完了報告】
修正①（h3→role="heading"）：完了 / 差異あり（理由：...）
修正②（広告タイトルURL除去）：完了 / 差異あり（理由：...）
修正③（popup.js重複チェック）：完了 / 差異あり（理由：...）
修正④（ステータス自動更新）：完了 / 差異あり（理由：...）
Flask再起動：PID=（数値）
サーバー動作確認結果：（結果）
Chrome拡張は手動テストが必要：（注記）
```

---

## 5. 禁止事項

| 項目 | 内容 |
|------|------|
| ファイル追加 | 新しいファイルを作成しない |
| 他ファイル修正 | analyzer.py, classifier.py, database.py, config.py, static/style.css は触らない |
| DB構造変更 | テーブル構造・カラムは変更しない |
| APIインターフェース変更 | 既存の /api/analyze のリクエスト/レスポンス形式は変更しない |
| 分類ロジック変更 | classifier.py の判定条件は変更しない |
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

## 7. テスト時の注意

Chrome拡張の修正（content.js, popup.js）はサーバー再起動では反映されない。
テスト手順：

1. Chrome拡張の管理画面（chrome://extensions/）を開く
2. SERP診断の拡張を一度「無効」にしてから「有効」に戻す、または「更新」ボタンを押す
3. Google検索ページをリロード（content.jsの再注入のため）
4. 拡張ポップアップを開いて「読み取り」→「分析」を実行

---

以上、スクレイピングプロジェクトより
