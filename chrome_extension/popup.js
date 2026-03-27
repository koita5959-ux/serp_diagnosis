// popup.js — ポップアップUI制御

const DEFAULT_SERVER = "http://192.168.0.123:5112";

let accumulatedData = [];

document.addEventListener("DOMContentLoaded", async () => {
  // サーバーURL復元
  const stored = await chrome.storage.local.get(["serverUrl", "accumulatedData"]);
  const serverUrl = stored.serverUrl || DEFAULT_SERVER;
  document.getElementById("serverUrl").value = serverUrl;

  // 蓄積データ復元
  if (stored.accumulatedData && stored.accumulatedData.length > 0) {
    accumulatedData = stored.accumulatedData;
  }
  updateUI();

  // イベント
  document.getElementById("btnRead").addEventListener("click", onRead);
  document.getElementById("btnAnalyze").addEventListener("click", onAnalyze);
  document.getElementById("btnClear").addEventListener("click", onClear);
  document.getElementById("serverUrl").addEventListener("change", onServerUrlChange);
});


function updateUI() {
  const totalResults = accumulatedData.reduce(
    (sum, page) => sum + page.organic.length + page.ads.length, 0
  );
  document.getElementById("totalCount").textContent = `${totalResults}件`;
  document.getElementById("pageCount").textContent = `${accumulatedData.length}ページ`;
  document.getElementById("btnAnalyze").disabled = accumulatedData.length === 0;

  // データリスト表示
  const listEl = document.getElementById("dataList");
  if (accumulatedData.length > 0) {
    let html = "";
    for (const page of accumulatedData) {
      const count = page.organic.length + page.ads.length;
      html += `<div class="data-item">
        <span class="query">P${page.pageNumber}: ${page.query}</span>
        <span class="count">${count}件</span>
      </div>`;
    }
    listEl.innerHTML = html;
  } else {
    listEl.innerHTML = "";
  }
}


function showMessage(text, type) {
  const el = document.getElementById("message");
  el.textContent = text;
  el.className = `message ${type}`;
  if (type === "success") {
    setTimeout(() => { el.className = "message"; }, 3000);
  }
}


async function onRead() {
  const btn = document.getElementById("btnRead");
  btn.disabled = true;
  btn.textContent = "読み取り中...";

  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

    if (!tab || !tab.url || (!tab.url.includes("google.co.jp/search") && !tab.url.includes("google.com/search"))) {
      showMessage("Google検索結果ページを開いてください", "error");
      return;
    }

    const response = await chrome.tabs.sendMessage(tab.id, { action: "readResults" });

    if (response && response.success) {
      const data = response.data;
      const totalInPage = data.organic.length + data.ads.length;

      if (totalInPage === 0) {
        showMessage("検索結果が見つかりません。ページを確認してください", "error");
        return;
      }

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

      accumulatedData.push(data);
      await chrome.storage.local.set({ accumulatedData });
      updateUI();
      showMessage(`${totalInPage}件を読み取りました（オーガニック${data.organic.length} + 広告${data.ads.length}）`, "success");
    } else {
      showMessage(response?.error || "読み取りに失敗しました", "error");
    }
  } catch (e) {
    showMessage("読み取りエラー: ページを再読み込みしてください", "error");
    console.error(e);
  } finally {
    btn.disabled = false;
    btn.textContent = "読み取り";
  }
}


async function onAnalyze() {
  if (accumulatedData.length === 0) return;

  const btn = document.getElementById("btnAnalyze");
  btn.disabled = true;
  btn.textContent = "送信中...";

  try {
    const stored = await chrome.storage.local.get(["serverUrl"]);
    const serverUrl = (stored.serverUrl || DEFAULT_SERVER).replace(/\/+$/, "");

    const payload = {
      query: accumulatedData[0].query,
      pages: accumulatedData,
      device: detectDevice(),
    };

    const response = await fetch(`${serverUrl}/api/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      const errText = await response.text();
      throw new Error(`サーバーエラー: ${response.status} ${errText}`);
    }

    const result = await response.json();

    if (result.session_id) {
      // 結果ページを新しいタブで開く
      chrome.tabs.create({ url: `${serverUrl}/results/${result.session_id}` });

      // 蓄積データをクリア
      accumulatedData = [];
      await chrome.storage.local.set({ accumulatedData });
      updateUI();
      showMessage("分析完了！結果ページを開きました", "success");
    } else {
      showMessage(result.error || "分析に失敗しました", "error");
    }
  } catch (e) {
    showMessage(e.message || "サーバーに接続できません", "error");
    console.error(e);
  } finally {
    btn.disabled = false;
    btn.textContent = "分析";
  }
}


async function onClear() {
  accumulatedData = [];
  await chrome.storage.local.set({ accumulatedData });
  updateUI();
  document.getElementById("message").className = "message";
}


function onServerUrlChange(e) {
  chrome.storage.local.set({ serverUrl: e.target.value.trim() });
}


function detectDevice() {
  // 蓄積データのURLからモバイル/デスクトップを推定
  // Google検索のモバイル版は通常 viewport が小さい
  // ここではデフォルトで "desktop" とし、ユーザーが手動検索しているため
  return "desktop";
}
