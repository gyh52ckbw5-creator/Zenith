const chat = document.getElementById("chat");
const form = document.getElementById("chat-form");
const input = document.getElementById("chat-input");
const councilToggle = document.getElementById("council-toggle");
const ttsToggle = document.getElementById("tts-toggle");
const resetBtn = document.getElementById("reset-btn");
const exportBtn = document.getElementById("export-btn");
const modelSelect = document.getElementById("model-select");
const micBtn = document.getElementById("mic-btn");

const HISTORY_KEY = "zenith-history-v1";

// --- Guvenli mini-markdown: once HTML kaclanir, sonra sinirli bicimlendirme ---
function escapeHtml(text) {
  return text
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function renderMarkdown(text) {
  const escaped = escapeHtml(text);
  const blocks = [];
  let html = escaped.replace(/```([\s\S]*?)```/g, (_, code) => {
    blocks.push(`<pre><code>${code.replace(/^\w+\n/, "")}</code></pre>`);
    return `\u0000${blocks.length - 1}\u0000`;
  });
  html = html
    .replace(/`([^`\n]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*\n]+)\*\*/g, "<strong>$1</strong>")
    .replace(/^### (.+)$/gm, "<h4>$1</h4>")
    .replace(/^## (.+)$/gm, "<h3>$1</h3>")
    .replace(/^# (.+)$/gm, "<h3>$1</h3>")
    .replace(/^[-*] (.+)$/gm, "<li>$1</li>")
    .replace(/(<li>.*<\/li>\n?)+/g, (m) => `<ul>${m}</ul>`)
    .replace(/(https?:\/\/[^\s<]+)/g, '<a href="$1" target="_blank" rel="noopener">$1</a>')
    .replace(/\n/g, "<br>");
  return html.replace(/\u0000(\d+)\u0000/g, (_, i) => blocks[Number(i)]);
}

// --- Sohbet gecmisi: telefonun tarayicisinda kalici (localStorage) ---
function loadHistory() {
  try {
    return JSON.parse(localStorage.getItem(HISTORY_KEY)) || [];
  } catch {
    return [];
  }
}

function saveEntry(role, text, meta) {
  const history = loadHistory();
  history.push({ role, text, meta: meta || null, at: Date.now() });
  localStorage.setItem(HISTORY_KEY, JSON.stringify(history.slice(-200)));
}

function hideWelcome() {
  document.getElementById("welcome")?.remove();
}

function scrollDown() {
  chat.scrollTop = chat.scrollHeight;
}

function addCopyButton(bubble, getText) {
  const btn = document.createElement("button");
  btn.className = "copy-btn";
  btn.textContent = "kopyala";
  btn.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(getText());
      btn.textContent = "kopyalandi";
      setTimeout(() => (btn.textContent = "kopyala"), 1200);
    } catch {
      /* pano erisimi yoksa sessiz kal */
    }
  });
  bubble.appendChild(btn);
}

function addBubble(role, text, { skipSave = false, meta = null } = {}) {
  hideWelcome();
  const el = document.createElement("div");
  el.className = `bubble ${role}`;
  if (role === "assistant") {
    el.innerHTML = renderMarkdown(text);
    addCopyButton(el, () => text);
  } else {
    el.textContent = text;
  }
  chat.appendChild(el);
  if (meta) addMeta(meta);
  scrollDown();
  if (!skipSave && role !== "system") saveEntry(role, text, meta);
  return el;
}

function addMeta(text) {
  const el = document.createElement("div");
  el.className = "meta";
  el.textContent = text;
  chat.appendChild(el);
  scrollDown();
}

function autoGrow() {
  input.style.height = "auto";
  input.style.height = `${Math.min(input.scrollHeight, 120)}px`;
}

input.addEventListener("input", autoGrow);

// Enter ile gonder, Shift+Enter ile yeni satir (masaustu rahatligi).
input.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey && !e.isComposing) {
    e.preventDefault();
    form.requestSubmit();
  }
});

function speak(text) {
  if (!ttsToggle.checked || !("speechSynthesis" in window)) return;
  speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = "tr-TR";
  speechSynthesis.speak(utterance);
}

function metaFor(data) {
  if (data.source === "council" && data.contributors?.length > 1) {
    return `konsey: ${data.contributors.length} model birlikte cevapladi`;
  }
  if (data.source === "search") return "web aramasiyla cevaplandi";
  if (data.source === "summary") return "sayfa ozetlendi";
  if (data.source === "skill") return "yetenek";
  if (data.source === "model" && data.contributors?.length) return data.contributors[0];
  return null;
}

let busy = false;

async function sendMessage(message) {
  if (busy || !message) return;
  busy = true;

  addBubble("user", message);
  input.value = "";
  autoGrow();

  hideWelcome();
  const bubble = document.createElement("div");
  bubble.className = "bubble assistant streaming";
  chat.appendChild(bubble);
  scrollDown();

  let full = "";
  let meta = null;

  try {
    const res = await fetch("/api/chat/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message,
        council: councilToggle.checked,
        model: modelSelect.value || null,
      }),
    });

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const parts = buffer.split("\n\n");
      buffer = parts.pop();
      for (const part of parts) {
        const line = part.trim();
        if (!line.startsWith("data:")) continue;
        const event = JSON.parse(line.slice(5).trim());
        if (event.type === "delta") {
          full += event.text;
          bubble.innerHTML = renderMarkdown(full);
          scrollDown();
        } else if (event.type === "meta") {
          meta = metaFor(event);
        } else if (event.type === "error") {
          full = event.text;
          bubble.innerHTML = renderMarkdown(full);
        }
      }
    }
  } catch (err) {
    full = full || `[baglanti hatasi] ${err}`;
    bubble.innerHTML = renderMarkdown(full);
  }

  bubble.classList.remove("streaming");
  addCopyButton(bubble, () => full);
  if (meta) addMeta(meta);
  saveEntry("assistant", full, meta);
  speak(full);
  busy = false;
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  const message = input.value.trim();
  if (message) sendMessage(message);
});

// Welcome ekranindaki oneri cipleri.
document.addEventListener("click", (e) => {
  const chip = e.target.closest(".chip");
  if (!chip) return;
  if (chip.dataset.send === "__council__") {
    councilToggle.checked = true;
    input.value = "Kuantum bilgisayarlari basit bir dille anlatir misin?";
    autoGrow();
    input.focus();
    return;
  }
  input.value = chip.dataset.fill || "";
  autoGrow();
  input.focus();
});

resetBtn.addEventListener("click", async () => {
  await fetch("/api/reset", { method: "POST" });
  localStorage.removeItem(HISTORY_KEY);
  location.reload();
});

exportBtn.addEventListener("click", () => {
  const history = loadHistory();
  if (!history.length) return;
  const lines = history.map((h) => `**${h.role === "user" ? "Sen" : "Zenith"}:** ${h.text}`);
  const blob = new Blob([`# Zenith sohbeti\n\n${lines.join("\n\n")}\n`], {
    type: "text/markdown",
  });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "zenith-sohbet.md";
  a.click();
  URL.revokeObjectURL(a.href);
});

// --- Sesli giris ---
const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
if (SpeechRec) {
  micBtn.hidden = false;
  let listening = false;
  const recognition = new SpeechRec();
  recognition.lang = "tr-TR";
  recognition.interimResults = false;

  recognition.onresult = (event) => {
    input.value = event.results[0][0].transcript;
    autoGrow();
    input.focus();
  };
  recognition.onend = () => {
    listening = false;
    micBtn.classList.remove("recording");
  };
  recognition.onerror = recognition.onend;

  micBtn.addEventListener("click", () => {
    if (listening) {
      recognition.stop();
      return;
    }
    listening = true;
    micBtn.classList.add("recording");
    recognition.start();
  });
}

// --- Acilis: gecmisi yukle, model secicisini doldur, saglik uyarisi goster ---
(async () => {
  const history = loadHistory();
  if (history.length) {
    hideWelcome();
    for (const entry of history) {
      addBubble(entry.role, entry.text, { skipSave: true, meta: entry.meta });
    }
  }

  try {
    const res = await fetch("/api/models");
    const data = await res.json();
    for (const m of data.detail || []) {
      if (!m.ready) continue;
      const opt = document.createElement("option");
      opt.value = m.name;
      opt.textContent = m.name;
      modelSelect.appendChild(opt);
    }
  } catch {
    /* model listesi alinamazsa otomatik modda kal */
  }

  try {
    const res = await fetch("/api/health");
    const data = await res.json();
    if (data.status === "no_models") {
      addBubble("system", data.hint, { skipSave: true });
    }
  } catch {
    /* saglik kontrolu basarisizsa sessiz kal */
  }
})();

if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js").catch(() => {});
  });
}
