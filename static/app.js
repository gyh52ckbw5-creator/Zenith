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
  // Kod bloklarini ayir ki iclerine baska kural uygulanmasin.
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
  // Telefonda sisirmemek icin son 200 mesaji tut.
  localStorage.setItem(HISTORY_KEY, JSON.stringify(history.slice(-200)));
}

function addBubble(role, text, { skipSave = false, meta = null } = {}) {
  const el = document.createElement("div");
  el.className = `bubble ${role}`;
  if (role === "assistant") {
    el.innerHTML = renderMarkdown(text);
  } else {
    el.textContent = text;
  }
  chat.appendChild(el);
  if (meta) addMeta(meta);
  chat.scrollTop = chat.scrollHeight;
  if (!skipSave && role !== "system") saveEntry(role, text, meta);
  return el;
}

function addMeta(text) {
  const el = document.createElement("div");
  el.className = "meta";
  el.textContent = text;
  chat.appendChild(el);
  chat.scrollTop = chat.scrollHeight;
}

function autoGrow() {
  input.style.height = "auto";
  input.style.height = `${Math.min(input.scrollHeight, 120)}px`;
}

input.addEventListener("input", autoGrow);

function speak(text) {
  if (!ttsToggle.checked || !("speechSynthesis" in window)) return;
  speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = "tr-TR";
  speechSynthesis.speak(utterance);
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const message = input.value.trim();
  if (!message) return;

  addBubble("user", message);
  input.value = "";
  autoGrow();

  const thinking = addBubble("assistant", "...", { skipSave: true });

  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message,
        council: councilToggle.checked,
        model: modelSelect.value || null,
      }),
    });
    const data = await res.json();
    thinking.innerHTML = renderMarkdown(data.reply);
    let meta = null;
    if (data.source === "council" && data.contributors?.length > 1) {
      meta = `konsey: ${data.contributors.length} model birlikte cevapladi`;
    } else if (data.source === "search") {
      meta = "web aramasiyla cevaplandi";
    } else if (data.source === "model" && data.contributors?.length) {
      meta = data.contributors[0];
    }
    if (meta) addMeta(meta);
    saveEntry("assistant", data.reply, meta);
    speak(data.reply);
  } catch (err) {
    thinking.textContent = `[baglanti hatasi] ${err}`;
  }
});

resetBtn.addEventListener("click", async () => {
  await fetch("/api/reset", { method: "POST" });
  localStorage.removeItem(HISTORY_KEY);
  chat.innerHTML = "";
  addBubble("system", "Hafiza temizlendi.");
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

// Sesli giris: destekleyen tarayicilarda mikrofon butonunu goster.
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
  recognition.onerror = () => {
    listening = false;
    micBtn.classList.remove("recording");
  };

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

// Acilis: gecmisi geri yukle, model secicisini doldur, saglik kontrolu yap.
(async () => {
  for (const entry of loadHistory()) {
    addBubble(entry.role, entry.text, { skipSave: true, meta: entry.meta });
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
