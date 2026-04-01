# 制作指示書：SERP診断ツール Phase 1 修正 v2.1（追補）

**スクレイピングPj → Claude Code｜2026年3月27日**

---

## 1. 本指示書の目的

修正v2適用後の実動テストで発覚した**最大の取りこぼし原因**を修正する。

**問題：** Googleの「そのほかの検索結果」で追加読み込みされた結果が、`#rso` の外に配置されている。content.jsは `#rso` 内しか探していないため、大量の結果を取りこぼしている。

---

## 2. 実動テストで判明した事実

2026年3月27日、「車のスピード修理」で「そのほかの検索結果」を4回押した状態で調査。

```
#rso内の [role="heading"][aria-level="3"]: 16件
#rso外の [role="heading"][aria-level="3"]: 39件  ← ★ これが丸ごと取りこぼされている
#botstuff内の外部リンク: 50個
ページ高さ: 13546px
```

**合計55件のタイトルがDOM上に存在するのに、12件しか取得できていない。**

### 2.1 #rso外の結果の特徴

コンソール調査で確認した#rso外の結果39件：
- 通常のオーガニック検索結果（carcon.co.jp, yellowhat.jp, carseven.co.jp 等）
- YouTube動画結果
- 地域関連の結果（岐阜、名古屋、浜松等）
- 全てURLを持ち、`[role="heading"][aria-level="3"]` でタイトルが取得可能

→ #rso内の結果と同じ構造。探す範囲を広げれば同じロジックで拾える。

---

## 3. 修正内容

### 修正対象：content.js — `extractOrganic()` 関数のみ

**修正方針：** 検索対象を `#rso` だけでなく、ページ全体に広げる。ただし広告コンテナ（#tads, #bottomads）は引き続き除外する。

**修正前：**
```javascript
function extractOrganic(organicList) {
  const searchContainer = document.querySelector("#rso") || document.querySelector("#search");
  if (!searchContainer) return;
  // ... #searchContainer内のみを走査
}
```

**修正後：**
```javascript
function extractOrganic(organicList) {
  let rank = 1;
  const seenUrls = new Set();

  // ========================================
  // フェーズ1: #rso 内の結果を取得（従来ロジック）
  // ========================================
  const rso = document.querySelector("#rso");
  if (rso) {
    const mjjBlocks = rso.querySelectorAll("div.MjjYud");
    if (mjjBlocks.length > 0) {
      for (const block of mjjBlocks) {
        if (block.closest("#tads") || block.closest("#bottomads")) continue;
        const results = parseMjjYudBlock(block, rank);
        for (const result of results) {
          if (seenUrls.has(result.url)) continue;
          seenUrls.add(result.url);
          organicList.push(result);
          rank++;
        }
      }
    }
  }

  // ========================================
  // フェーズ2: #rso 外の追加読み込み結果を取得
  // ========================================
  // 「そのほかの検索結果」で追加読み込みされた結果は#rsoの外に配置される。
  // #botstuff やその他の領域にあるMjjYudブロックを走査する。
  const allMjjBlocks = document.querySelectorAll("div.MjjYud");
  for (const block of allMjjBlocks) {
    // #rso内は既に処理済み → スキップ
    if (rso && rso.contains(block)) continue;
    // 広告コンテナ内はスキップ
    if (block.closest("#tads") || block.closest("#bottomads")) continue;

    const results = parseMjjYudBlock(block, rank);
    for (const result of results) {
      if (seenUrls.has(result.url)) continue;
      seenUrls.add(result.url);
      organicList.push(result);
      rank++;
    }
  }

  // ========================================
  // フェーズ3: MjjYudに含まれないheading要素のフォールバック
  // ========================================
  // MjjYudブロックに属さない検索結果がある場合に対応
  if (organicList.length === 0) {
    const allHeadings = document.querySelectorAll('[role="heading"][aria-level="3"], h3');
    for (const h3 of allHeadings) {
      if (h3.closest("#tads") || h3.closest("#bottomads")) continue;
      const result = parseFromH3_2026(h3, rank);
      if (result) {
        if (seenUrls.has(result.url)) continue;
        seenUrls.add(result.url);
        organicList.push(result);
        rank++;
      }
    }
  }
}
```

### 修正のポイント

1. **フェーズ1（#rso内）は従来ロジックをそのまま維持**。動作実績のあるコードを壊さない
2. **フェーズ2で `document.querySelectorAll("div.MjjYud")` を使いページ全体を走査**。ただし `rso.contains(block)` で#rso内は重複スキップ
3. **`seenUrls` で重複排除**。#rso内と#rso外で同じURLが出現しても2重登録されない
4. **フェーズ3のフォールバックも全体対象**に変更（`searchContainer` ではなく `document`）
5. **既存の `parseMjjYudBlock()` をそのまま再利用**。新しい関数は不要

### 変更しないもの

- `parseMjjYudBlock()` — そのまま使う
- `parseOrganicBlock()` — フォールバック用、そのまま
- `parseFromH3_2026()` — フォールバック用、そのまま
- `findUrl()` — そのまま
- `findSnippet()` — そのまま
- `extractAds()` — 広告抽出は変更不要（#tads/#bottomadsベースで正常動作）

---

## 4. 追加修正：広告タイトルのURL混入（v2で未解決分）

`parseAdContainer2026()` 内のh3/headingルートで `cleanTitle` が適用されていない箇所を修正する。

**修正前（112行目付近）：**
```javascript
const h3s = container.querySelectorAll('h3, [role="heading"][aria-level="3"]');
if (h3s.length > 0) {
  for (const h3 of h3s) {
    const title = h3.textContent.trim();  // ← cleanTitleを通していない
    if (!title) continue;
    let url = findUrl(h3, container);
    let snippet = findSnippet(h3, container);
    if (title && url) {
      adsList.push({ title, url, snippet, position });
    }
  }
```

**修正後：**
```javascript
const h3s = container.querySelectorAll('h3, [role="heading"][aria-level="3"]');
if (h3s.length > 0) {
  for (const h3 of h3s) {
    const title = cleanTitle(h3.textContent.trim());  // ← cleanTitleを適用
    if (!title) continue;
    let url = findUrl(h3, container);
    let snippet = findSnippet(h3, container);
    if (title && url) {
      adsList.push({ title, url, snippet, position });
    }
  }
```

---

## 5. 作業手順

### ステップ1：把握レポート出力

```
【把握レポート】
修正の理解：（#rso外の追加読み込み結果をフェーズ2で取得することについて）
追加修正の理解：（広告タイトルのcleanTitle適用について）
変更対象ファイル：content.js のみ
変更しないファイル：（それ以外全て）
懸念点：（あれば）
```

### ステップ2：content.js の修正

1. `/home/adminterml1/services/scraping/serp_diagnosis/chrome_extension/content.js` のバックアップを取る

```bash
cp /home/adminterml1/services/scraping/serp_diagnosis/chrome_extension/content.js \
   /home/adminterml1/services/scraping/serp_diagnosis/chrome_extension/content.js.bak.v2
```

2. `extractOrganic()` 関数を本指示書のコードに置き換え
3. `parseAdContainer2026()` 内の `cleanTitle` 適用漏れを修正
4. 修正後、変更箇所の差分を報告

### ステップ3：完了報告

```
【完了報告】
extractOrganic() 修正：完了 / 差異あり（理由：...）
広告cleanTitle修正：完了 / 差異あり（理由：...）
```

**注意：Chrome拡張の修正なのでFlask再起動は不要。**
テスト手順：
1. chrome://extensions/ でSERP診断拡張を「更新」
2. Google検索ページをリロード
3. 「そのほかの検索結果」を数回押してから「読み取り」→「分析」

---

## 6. 禁止事項

| 項目 | 内容 |
|------|------|
| ファイル追加 | 新しいファイルを作成しない |
| 他ファイル修正 | content.js 以外は触らない |
| 関数の新規追加 | 既存関数の再利用で対応する |
| 勝手な改善 | 指示書にない改善は行わない |

---

## 7. 差異報告のルール

指示書と異なる実装をした場合は、必ず以下の形式で報告すること。

```
【差異報告】
指示書の内容：（何を指示されていたか）
実際の実装：（何をしたか）
理由：（なぜ変えたか）
影響：（他の箇所への影響はあるか）
```

---

## 8. 期待される結果

修正後、「車のスピード修理」+「そのほかの検索結果」4回の条件で：
- 修正前：オーガニック12件
- 修正後：オーガニック40〜55件（DOM上の全結果を取得）

---

以上、スクレイピングプロジェクトより
