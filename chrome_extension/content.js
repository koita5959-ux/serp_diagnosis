// content.js — Google検索結果ページのDOM解析
// content_scriptsとして自動注入され、popup.jsからのメッセージで動作する
// 2026年3月時点のGoogle HTML構造に対応

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === "readResults") {
    try {
      const data = extractSearchResults();
      sendResponse({ success: true, data: data });
    } catch (e) {
      sendResponse({ success: false, error: e.message });
    }
  }
  return true; // 非同期レスポンスのため
});


function extractSearchResults() {
  const results = {
    query: extractQuery(),
    organic: [],
    ads: [],
    pageNumber: extractPageNumber(),
    url: location.href,
  };

  // --- 広告の抽出 ---
  extractAds(results.ads);

  // --- オーガニック結果の抽出 ---
  extractOrganic(results.organic);

  return results;
}


function extractQuery() {
  // 検索ボックスから検索フレーズを取得
  const input = document.querySelector('textarea[name="q"], input[name="q"]');
  return input ? input.value : "";
}


function extractPageNumber() {
  const params = new URLSearchParams(location.search);
  const start = parseInt(params.get("start") || "0");
  return Math.floor(start / 10) + 1;
}


// =====================
// 広告の抽出
// =====================
function extractAds(adsList) {
  // 方法1: #tads / #bottomads コンテナ内のリンクを探す
  const topAds = document.querySelector("#tads");
  if (topAds) {
    parseAdContainer2026(topAds, "top", adsList);
  }

  const bottomAds = document.querySelector("#bottomads");
  if (bottomAds) {
    parseAdContainer2026(bottomAds, "bottom", adsList);
  }

  // 方法2: 「スポンサー」テキストから広告ブロックを探す（フォールバック）
  if (adsList.length === 0) {
    const allSpans = document.querySelectorAll("span");
    const sponsorBlocks = new Set();
    for (const span of allSpans) {
      const text = span.textContent.trim();
      if (text === "スポンサー" || text === "Sponsored" || text === "Ad" || text === "広告") {
        // 広告ブロックの親要素を探す（MjjYudまたは上位のdivブロック）
        let block = span.closest("div.MjjYud") || span.closest("[data-text-ad]") || span.closest(".uEierd");
        if (!block) {
          // さらに上に遡る
          let parent = span.parentElement;
          for (let i = 0; i < 8 && parent; i++) {
            if (parent.querySelector('a[href]:not([href*="google"])')) {
              block = parent;
              break;
            }
            parent = parent.parentElement;
          }
        }
        if (block && !sponsorBlocks.has(block)) {
          sponsorBlocks.add(block);
          const result = parseBlockForAd(block, "top");
          if (result) adsList.push(result);
        }
      }
    }
  }
}


function parseAdContainer2026(container, position, adsList) {
  // 2026年版: #tads内でh3がない場合、外部リンク+テキストで広告を構築
  // まずh3ベースを試す
  const h3s = container.querySelectorAll("h3");
  if (h3s.length > 0) {
    for (const h3 of h3s) {
      const title = h3.textContent.trim();
      if (!title) continue;
      let url = findUrl(h3, container);
      let snippet = findSnippet(h3, container);
      if (title && url) {
        adsList.push({ title, url, snippet, position });
      }
    }
    return;
  }

  // h3がない場合: 外部リンクをベースに広告を抽出
  const links = container.querySelectorAll('a[href^="http"]:not([href*="google."])');
  const seen = new Set();
  for (const a of links) {
    const url = cleanUrl(a.href);
    if (!url || seen.has(url)) continue;
    seen.add(url);

    // リンクのテキストまたは周辺テキストをタイトルとする
    let title = "";
    // リンク内のテキスト（長めのもの優先）
    const linkText = a.textContent.trim();
    const cleanedLinkText = cleanTitle(linkText);
    if (cleanedLinkText.length > 5 && cleanedLinkText.length < 200) {
      title = cleanedLinkText;
    }
    // タイトルが短すぎる場合、周辺を探す
    if (title.length < 5) {
      const parent = a.closest("div");
      if (parent) {
        const texts = parent.querySelectorAll("div, span");
        for (const t of texts) {
          const txt = cleanTitle(t.textContent.trim());
          if (txt.length > 10 && txt.length < 200 && !t.querySelector("a")) {
            title = txt.substring(0, 100);
            break;
          }
        }
      }
    }

    if (title && url) {
      adsList.push({ title: title.substring(0, 150), url, snippet: "", position });
    }
  }
}


function parseBlockForAd(block, position) {
  // スポンサーブロックから広告情報を抽出
  const links = block.querySelectorAll('a[href^="http"]:not([href*="google."])');
  let url = "";
  let title = "";

  for (const a of links) {
    const candidate = cleanUrl(a.href);
    if (candidate) {
      url = candidate;
      const text = cleanTitle(a.textContent.trim());
      if (text.length > 5 && text.length < 200) {
        title = text;
      }
      break;
    }
  }

  if (!title) {
    const h3 = block.querySelector("h3");
    if (h3) title = cleanTitle(h3.textContent.trim());
  }
  if (!title) {
    // 最初の目立つテキストをタイトルにする
    const divs = block.querySelectorAll("div, span");
    for (const d of divs) {
      const t = cleanTitle(d.textContent.trim());
      if (t.length > 10 && t.length < 150 && t !== "スポンサー" && t !== "Sponsored") {
        title = t;
        break;
      }
    }
  }

  if (url) {
    return { title: title || url, url, snippet: "", position };
  }
  return null;
}


// =====================
// オーガニック結果の抽出
// =====================
function extractOrganic(organicList) {
  const searchContainer = document.querySelector("#rso") || document.querySelector("#search");
  if (!searchContainer) return;

  let rank = 1;
  const seenUrls = new Set();  // 重複チェック用

  // 方法1: div.MjjYud ベース（2026年版Google）
  const mjjBlocks = searchContainer.querySelectorAll("div.MjjYud");
  if (mjjBlocks.length > 0) {
    for (const block of mjjBlocks) {
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
  }

  // 方法2: div.g ベース（従来版フォールバック）
  if (organicList.length === 0) {
    const gBlocks = searchContainer.querySelectorAll("div.g");
    if (gBlocks.length > 0) {
      for (const block of gBlocks) {
        if (block.closest("#tads") || block.closest("#bottomads")) continue;
        if (block.parentElement.closest("div.g")) continue;

        const result = parseOrganicBlock(block, rank);
        if (result) {
          if (seenUrls.has(result.url)) continue;
          seenUrls.add(result.url);
          organicList.push(result);
          rank++;
        }
      }
    }
  }

  // 方法3: h3ベース（最終フォールバック）
  if (organicList.length === 0) {
    const h3s = searchContainer.querySelectorAll("h3");
    for (const h3 of h3s) {
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


function parseMjjYudBlock(block, startRank) {
  // MjjYudブロックは1つの検索結果を含む場合と、複数を含む場合がある
  const results = [];

  // ブロック内の全h3を探す
  const h3s = block.querySelectorAll("h3");

  for (const h3 of h3s) {
    const title = cleanTitle(h3.textContent.trim());
    if (!title) continue;

    // 「地図」「さらに表示」などの非結果h3をスキップ
    if (title === "地図" || title === "さらに表示" || title === "関連する質問" ||
        title === "他の人はこちらも質問" || title === "強調スニペットについて") continue;

    // URL取得: h3内部のa → h3のclosest(a) → 周辺のa
    let url = findUrl(h3, block);

    if (!url || url.includes("google.com/search") || url.includes("google.co.jp/search")) continue;

    // スニペット取得
    let snippet = findSnippet(h3, block);

    results.push({
      rank: startRank + results.length,
      title,
      url,
      snippet,
    });
  }

  // h3がないがリンクがあるパターン（ナレッジパネル等はスキップ）
  if (results.length === 0) {
    // 外部リンクがあって検索結果っぽいブロックを探す
    const extLinks = block.querySelectorAll('a[href^="http"]:not([href*="google."])');
    for (const a of extLinks) {
      const url = cleanUrl(a.href);
      if (!url) continue;

      // リンク周辺にタイトルっぽいテキストがあるか
      const linkContainer = a.closest("div") || a.parentElement;
      if (!linkContainer) continue;

      let title = cleanTitle(a.textContent.trim());
      if (title.length < 5 || title.length > 200) continue;

      // 明らかに検索結果ではないものをスキップ
      if (title.includes("キャッシュ") || title.includes("類似ページ")) continue;

      results.push({
        rank: startRank + results.length,
        title: title.substring(0, 150),
        url,
        snippet: "",
      });
      break; // 1ブロック1結果
    }
  }

  return results;
}


function parseOrganicBlock(block, rank) {
  // 従来のdiv.gベース（フォールバック）
  const h3 = block.querySelector("h3");
  if (!h3) return null;

  const title = h3.textContent.trim();
  if (!title) return null;

  let url = findUrl(h3, block);
  if (!url || url.includes("google.com/search") || url.includes("google.co.jp/search")) {
    return null;
  }

  let snippet = findSnippet(h3, block);

  return { rank, title, url, snippet };
}


function parseFromH3_2026(h3, rank) {
  const title = h3.textContent.trim();
  if (!title) return null;

  // 非結果h3をスキップ
  if (title === "地図" || title === "さらに表示" || title === "関連する質問" ||
      title === "他の人はこちらも質問" || title === "強調スニペットについて") return null;

  // URL取得: 複数の方法で探す
  let url = findUrl(h3, null);
  if (!url || url.includes("google.com/search") || url.includes("google.co.jp/search")) {
    return null;
  }

  let snippet = findSnippet(h3, null);

  return { rank, title, url, snippet };
}


// =====================
// タイトルクリーニング
// =====================

function cleanTitle(text) {
  if (!text) return "";
  // URL文字列を除去（http:// または https:// で始まる部分）
  let cleaned = text.replace(/https?:\/\/[^\s\u3000]+/g, "").trim();
  // 連続する空白を1つに
  cleaned = cleaned.replace(/\s+/g, " ");
  return cleaned;
}


// =====================
// 共通ユーティリティ
// =====================

function findUrl(h3, container) {
  // 1. h3内部のaタグ
  const innerA = h3.querySelector("a");
  if (innerA && innerA.href) {
    const url = cleanUrl(innerA.href);
    if (url) return url;
  }

  // 2. h3を包含するaタグ
  const parentA = h3.closest("a");
  if (parentA && parentA.href) {
    const url = cleanUrl(parentA.href);
    if (url) return url;
  }

  // 3. h3の親要素からaタグを探す
  let parent = h3.parentElement;
  for (let i = 0; i < 5 && parent; i++) {
    const a = parent.querySelector('a[href^="http"]:not([href*="google.com/search"]):not([href*="google.co.jp/search"])');
    if (a && a.href) {
      const url = cleanUrl(a.href);
      if (url) return url;
    }
    parent = parent.parentElement;
  }

  // 4. コンテナ内の最初の外部リンク
  if (container) {
    const a = container.querySelector('a[href^="http"]:not([href*="google."])');
    if (a && a.href) {
      const url = cleanUrl(a.href);
      if (url) return url;
    }
  }

  return "";
}


function findSnippet(h3, container) {
  // スニペットを探す対象のブロック
  const searchBlock = container || h3.closest("div.MjjYud") || h3.closest("[data-hveid]") || h3.parentElement?.parentElement?.parentElement;
  if (!searchBlock) return "";

  const title = h3.textContent.trim();

  // 1. data-sncf属性、VwiC3b、line-clamp
  const snippetEl = searchBlock.querySelector("[data-sncf]") ||
                    searchBlock.querySelector(".VwiC3b") ||
                    searchBlock.querySelector("[style*='line-clamp']");
  if (snippetEl) {
    const text = snippetEl.textContent.trim();
    if (text.length > 10) return text.substring(0, 300);
  }

  // 2. h3以外で長いテキストを持つ要素
  const elements = searchBlock.querySelectorAll("div, span");
  for (const el of elements) {
    // h3自体やそのコンテナはスキップ
    if (el.querySelector("h3") || el.closest("h3")) continue;
    const text = el.textContent.trim();
    if (text.length > 30 && text !== title && !text.startsWith(title)) {
      return text.substring(0, 300);
    }
  }

  return "";
}


function cleanUrl(href) {
  if (!href) return "";

  // Google リダイレクトURL: /url?q=...
  try {
    const url = new URL(href);
    if (url.pathname === "/url" && url.searchParams.has("q")) {
      return url.searchParams.get("q");
    }
  } catch (e) {
    // URL解析失敗
  }

  // Google内部リンクは除外
  if (href.startsWith("https://www.google") || href.startsWith("https://google") ||
      href.startsWith("/search") || href.startsWith("https://support.google") ||
      href.startsWith("https://maps.google") || href.startsWith("https://accounts.google")) {
    return "";
  }

  // 通常の外部URL
  if (href.startsWith("http")) {
    // フラグメントやトラッキングパラメータを除去
    try {
      const url = new URL(href);
      // #:~:text= のようなフラグメントを除去
      if (url.hash && url.hash.includes(":~:text=")) {
        return url.origin + url.pathname + url.search;
      }
    } catch (e) {}
    return href;
  }

  return "";
}
