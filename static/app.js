// RootSafe Arborist — Frontend Controller
let conversationHistory = [];
let treesCatalog = [];

document.addEventListener("DOMContentLoaded", () => {
  initTreeCatalog();
  setupEventListeners();
});

// Setup sidebar and UI interactions
function setupEventListeners() {
  const form = document.getElementById("chat-form");
  const input = document.getElementById("message-input");
  const openSidebarBtn = document.getElementById("open-sidebar-btn");
  const closeSidebarBtn = document.getElementById("close-sidebar-btn");
  const sidebar = document.getElementById("sidebar");
  const searchInput = document.getElementById("tree-search-input");

  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const message = input.value.trim();
    if (!message) return;
    sendMessage(message);
    input.value = "";
    input.style.height = "auto";
  });

  // Auto-resize textarea
  input.addEventListener("input", () => {
    input.style.height = "auto";
    input.style.height = Math.min(input.scrollHeight, 120) + "px";
  });

  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      form.dispatchEvent(new Event("submit"));
    }
  });

  // Scenario chips
  document.querySelectorAll(".chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      const query = chip.getAttribute("data-query");
      if (query) {
        sendMessage(query);
      }
    });
  });

  // Sidebar controls
  if (openSidebarBtn) {
    openSidebarBtn.addEventListener("click", () => sidebar.classList.add("open"));
  }
  if (closeSidebarBtn) {
    closeSidebarBtn.addEventListener("click", () => sidebar.classList.remove("open"));
  }

  // Search input filter
  searchInput.addEventListener("input", (e) => {
    const term = e.target.value.toLowerCase();
    renderTreeList(treesCatalog.filter(t => 
      t.name_th.toLowerCase().includes(term) || 
      t.name_en.toLowerCase().includes(term) ||
      t.architectural_use.toLowerCase().includes(term)
    ));
  });
}

// Fetch and render trees in sidebar
async function initTreeCatalog() {
  const listContainer = document.getElementById("tree-list-container");
  const badge = document.getElementById("catalog-badge");
  const countBadge = document.getElementById("catalog-count-badge");

  try {
    const res = await fetch("/api/trees");
    if (!res.ok) throw new Error("Catalog fetch failed");
    treesCatalog = await res.json();
    
    if (badge) badge.textContent = `${treesCatalog.length} Trees`;
    if (countBadge) countBadge.textContent = `คลังพรรณไม้: ${treesCatalog.length} ชนิด`;
    
    renderTreeList(treesCatalog);
  } catch (err) {
    console.error(err);
    if (listContainer) {
      listContainer.innerHTML = `<div style="font-size:12px;color:var(--text-dim);padding:10px;">ไม่สามารถโหลดรายการต้นไม้ได้</div>`;
    }
  }
}

function renderTreeList(trees) {
  const container = document.getElementById("tree-list-container");
  if (!container) return;
  container.innerHTML = "";

  trees.forEach((tree) => {
    const card = document.createElement("div");
    card.className = "tree-item-card";
    
    let scoreClass = "score-safe";
    if (tree.root_aggressiveness_score >= 8) scoreClass = "score-danger";
    else if (tree.root_aggressiveness_score >= 5) scoreClass = "score-warning";

    card.innerHTML = `
      <div class="tree-item-top">
        <span class="tree-item-name">${escapeHtml(tree.name_th)}</span>
        <span class="tree-item-score ${scoreClass}">ราก: ${tree.root_aggressiveness_score}/10</span>
      </div>
      <div class="tree-item-sub">
        ระยะปลอดภัย: ตัวบ้าน ${tree.min_foundation_distance_m} ม. | รั้ว ${tree.min_fence_distance_m} ม.
      </div>
    `;

    card.addEventListener("click", () => {
      const promptText = `ต้องการปลูกต้น "${tree.name_th}" (${tree.name_en}) ห่างจากตัวบ้านหรือรั้วเท่าใดจึงจะปลอดภัย และมีข้อควรระวังเรื่องระบบรากอย่างไร?`;
      sendMessage(promptText);
    });

    container.appendChild(card);
  });
}

// Send message and process SSE stream
async function sendMessage(text) {
  const messagesContainer = document.getElementById("messages-container");
  const sendBtn = document.getElementById("send-btn");

  // Append User Bubble
  appendUserMessage(text);
  conversationHistory.push({ role: "user", content: text });

  // Prepare Assistant Bubble
  const { row, contentEl } = createAssistantRow();
  messagesContainer.appendChild(row);
  scrollToBottom();

  sendBtn.disabled = true;

  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message: text,
        history: conversationHistory,
        temperature: 0.0
      })
    });

    if (!response.ok) {
      throw new Error(`HTTP error ${response.status}`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let accumulatedText = "";
    let buffer = "";
    let hasReceivedFirstToken = false;

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n\n");
      buffer = lines.pop(); // Keep unparsed part in buffer

      for (const block of lines) {
        if (!block.startsWith("data: ")) continue;
        const jsonStr = block.replace(/^data:\s*/, "").trim();
        if (!jsonStr) continue;

        try {
          const evt = JSON.parse(jsonStr);

          if (evt.type === "token") {
            if (!hasReceivedFirstToken) {
              hasReceivedFirstToken = true;
              contentEl.innerHTML = "";
            }
            accumulatedText += evt.token;
            contentEl.innerHTML = formatMarkdown(accumulatedText);
            scrollToBottom();
          } else if (evt.type === "done") {
            if (!hasReceivedFirstToken && accumulatedText) {
              contentEl.innerHTML = formatMarkdown(accumulatedText);
            }
            if (evt.structured) {
              renderStructuredCard(contentEl, evt.structured);
            }
            conversationHistory.push({ role: "assistant", content: accumulatedText });
            scrollToBottom();
          } else if (evt.type === "error") {
            contentEl.innerHTML = `<div style="color:var(--danger);margin-top:8px;">⚠️ ${escapeHtml(evt.content)}</div>`;
          }
        } catch (e) {
          console.warn("SSE JSON Parse error:", e, block);
        }
      }
    }
  } catch (err) {
    contentEl.innerHTML = `<div style="color:var(--danger)">เกิดข้อผิดพลาดในการรับข้อมูล: ${escapeHtml(err.message)}</div>`;
  } finally {
    sendBtn.disabled = false;
  }
}

function appendUserMessage(text) {
  const container = document.getElementById("messages-container");
  const row = document.createElement("div");
  row.className = "message-row user-row";
  row.innerHTML = `
    <div class="avatar">👤</div>
    <div class="message-bubble">${escapeHtml(text)}</div>
  `;
  container.appendChild(row);
}

function createAssistantRow() {
  const row = document.createElement("div");
  row.className = "message-row assistant-row";

  row.innerHTML = `
    <div class="avatar">🌿</div>
    <div class="message-bubble">
      <div class="message-content">
        <div class="thinking-loader">
          <span class="thinking-spinner"></span>
          <span class="thinking-text">กรุณารอสักครู่ ระบบกำลังประมวลผลข้อมูล...</span>
          <span class="thinking-dots"><span>.</span><span>.</span><span>.</span></span>
        </div>
      </div>
    </div>
  `;

  return {
    row,
    contentEl: row.querySelector(".message-content")
  };
}

function renderStructuredCard(targetEl, data) {
  const card = document.createElement("div");
  const verdict = data.verdict || "WARNING";
  card.className = `consultation-card verdict-${verdict}`;

  let fillClass = "hazard-fill-safe";
  let verdictThai = "ผ่านเกณฑ์ปลอดภัย (SAFE)";
  if (verdict === "PROHIBITED") {
    fillClass = "hazard-fill-danger";
    verdictThai = "ห้ามปลูกเด็ดขาด (PROHIBITED)";
  } else if (verdict === "WARNING") {
    fillClass = "hazard-fill-warning";
    verdictThai = "ต้องระวัง / มีเงื่อนไข (WARNING)";
  }

  const scorePct = Math.min(100, Math.max(10, data.hazard_score * 10));

  const recHtml = (data.recommended_trees && data.recommended_trees.length > 0)
    ? `<div class="recommendations-box">
         <span style="font-size:11px;color:var(--text-dim);width:100%;">พันธุ์ไม้แนะนำทดแทน:</span>
         ${data.recommended_trees.map(t => `<span class="rec-tag">${escapeHtml(t)}</span>`).join("")}
       </div>`
    : "";

  const citesHtml = (data.citations && data.citations.length > 0)
    ? `<div class="citations-box">
         <span>หลักฐานอ้างอิง:</span>
         ${data.citations.map(c => `<span class="cite-tag">${escapeHtml(c)}</span>`).join("")}
       </div>`
    : "";

  card.innerHTML = `
    <div class="card-header-row">
      <span class="verdict-badge">${verdictThai}</span>
      <div class="hazard-meter-container">
        <span>ความเสี่ยงราก: <strong>${data.hazard_score}/10</strong></span>
        <div class="hazard-bar-bg">
          <div class="hazard-bar-fill ${fillClass}" style="width: ${scorePct}%"></div>
        </div>
      </div>
    </div>
    <div class="card-stat-grid">
      <div class="stat-item">
        <span class="stat-label">ระยะร่นปลอดภัยขั้นต่ำ</span>
        <span class="stat-value">${data.safe_setback_meters} เมตร</span>
      </div>
      <div class="stat-item">
        <span class="stat-label">ข้อกฎหมายแนวรั้ว (ป.พ.พ. 1347)</span>
        <span class="stat-value" style="font-size:12px;font-weight:400;">${escapeHtml(data.legal_neighbor_risk_notes)}</span>
      </div>
    </div>
    ${recHtml}
    ${citesHtml}
  `;

  targetEl.appendChild(card);
}

function formatMarkdown(text) {
  // Strip raw JSON code blocks from main text rendering since we render the card
  let clean = text.replace(/```(?:json)?\s*\{[\s\S]*?\}\s*```/g, "").trim();
  
  clean = escapeHtml(clean);
  
  // Format bold and italics
  clean = clean
    .replace(/aggressive\\?_surface/gi, "รากลอยผิวดินรุกรานสูง (Aggressive Surface Roots)")
    .replace(/\\_/g, "_")
    .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
    .replace(/\*(.*?)\*/g, "<em>$1</em>");
    
  // Process line by line to detect headings & topic titles
  const lines = clean.split("\n");
  const processedLines = lines.map(line => {
    const trimmed = line.trim();
    if (!trimmed) return "";
    
    // Markdown headers ### or ## or #
    if (/^#{1,4}\s+/.test(trimmed)) {
      const heading = trimmed.replace(/^#{1,4}\s+/, "");
      return `<h4 class="chat-heading">${heading}</h4>`;
    }
    
    // Standalone topic header line ending with : (e.g. "คำแนะนำด้านระยะห่างและความเสี่ยง:", "คำเตือนจาก RootSafe Arborist:")
    if (trimmed.endsWith(":") && trimmed.length <= 80 && !trimmed.includes("<br>")) {
      if (/คำเตือน|ข้อควรระวัง/i.test(trimmed)) {
        return `<div class="chat-topic-title topic-warning"><span class="topic-icon">⚠️</span> ${trimmed}</div>`;
      } else if (/กฎเหล็ก|ห้ามปลูก|PROHIBITED|อันตราย/i.test(trimmed)) {
        return `<div class="chat-topic-title topic-danger"><span class="topic-icon">🛑</span> ${trimmed}</div>`;
      } else if (/คำแนะนำ|ระยะห่าง|การควบคุม|ความปลอดภัย/i.test(trimmed)) {
        return `<div class="chat-topic-title topic-info"><span class="topic-icon">📐</span> ${trimmed}</div>`;
      } else {
        return `<div class="chat-topic-title topic-default"><span class="topic-icon">📌</span> ${trimmed}</div>`;
      }
    }
    
    // Lines starting with specific topic prefixes followed by colon on the same line
    // e.g. "ตามกฎเหล็กของผม: หากต้นไม้..." or "คำเตือน: ..."
    let formattedLine = line;
    if (/^(คำเตือน|ข้อควรระวัง)([^:]*:)/i.test(formattedLine)) {
      formattedLine = formattedLine.replace(/^(คำเตือน|ข้อควรระวัง)([^:]*:)/i, '<strong class="topic-inline-tag tag-warning">$1$2</strong>');
    } else if (/^(ตามกฎเหล็ก[^\s:]*|กฎเหล็ก|ห้ามปลูก)([^:]*:)/i.test(formattedLine)) {
      formattedLine = formattedLine.replace(/^(ตามกฎเหล็ก[^\s:]*|กฎเหล็ก|ห้ามปลูก)([^:]*:)/i, '<strong class="topic-inline-tag tag-danger">$1$2</strong>');
    } else if (/^(คำแนะนำ|การควบคุม|ระยะร่น)([^:]*:)/i.test(formattedLine)) {
      formattedLine = formattedLine.replace(/^(คำแนะนำ|การควบคุม|ระยะร่น)([^:]*:)/i, '<strong class="topic-inline-tag tag-info">$1$2</strong>');
    } else if (/^(\d+\.\s*[^:\n]{2,35}:)/.test(formattedLine)) {
      // e.g. "1. ห้ามปลูกใกล้สิ่งปลูกสร้าง: ต้องปลูก..."
      formattedLine = formattedLine.replace(/^(\d+\.\s*[^:\n]{2,35}:)/, '<strong class="list-topic-highlight">$1</strong>');
    }
    
    return formattedLine;
  });
  
  return processedLines.join("<br>");
}

function escapeHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function scrollToBottom() {
  const container = document.getElementById("messages-container");
  if (container) {
    container.scrollTop = container.scrollHeight;
  }
}
