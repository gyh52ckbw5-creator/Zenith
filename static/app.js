const chat = document.getElementById("chat");
const form = document.getElementById("chat-form");
const input = document.getElementById("chat-input");
const councilToggle = document.getElementById("council-toggle");
const ttsToggle = document.getElementById("tts-toggle");
const exportBtn = document.getElementById("export-btn");
const modelSelect = document.getElementById("model-select");
const micBtn = document.getElementById("mic-btn");
const voiceBtn = document.getElementById("voice-btn");
const menuBtn = document.getElementById("menu-btn");
const sidebar = document.getElementById("sidebar");
const sidebarOverlay = document.getElementById("sidebar-overlay");
const newChatBtn = document.getElementById("new-chat-btn");
const conversationList = document.getElementById("conversation-list");
const attachBtn = document.getElementById("attach-btn");
const imageInput = document.getElementById("image-input");
const imagePreview = document.getElementById("image-preview");
const imageThumb = document.getElementById("image-thumb");
const imageRemove = document.getElementById("image-remove");

const STORE_KEY = "zenith-conversations-v1";
const OLD_KEY = "zenith-history-v1";

let pendingImage = null;
let busy = false;
let voiceMode = false;

// --- Guvenli mini-markdown ---
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

// --- Konusma deposu (coklu sohbet) ---
function newId() {
  return `c_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`;
}

function deriveTitle(messages) {
  const firstUser = messages.find((m) => m.role === "user");
  const t = (firstUser?.text || "Yeni sohbet").trim();
  return t.length > 34 ? `${t.slice(0, 34)}...` : t;
}

function loadStore() {
  try {
    const raw = JSON.parse(localStorage.getItem(STORE_KEY));
    if (raw && Array.isArray(raw.conversations)) return raw;
  } catch {
    /* devam */
  }
  let convs = [];
  try {
    const old = JSON.parse(localStorage.getItem(OLD_KEY));
    if (Array.isArray(old) && old.length) {
      convs = [{ id: newId(), title: deriveTitle(old), messages: old, updated: Date.now() }];
    }
  } catch {
    /* yok say */
  }
  return { conversations: convs, activeId: convs[0]?.id || null };
}

let store = loadStore();

function saveStore() {
  localStorage.setItem(STORE_KEY, JSON.stringify(store));
}

function activeConv() {
  return store.conversations.find((c) => c.id === store.activeId) || null;
}

function ensureActive() {
  if (!activeConv()) {
    const conv = { id: newId(), title: "Yeni sohbet", messages: [], updated: Date.now() };
    store.conversations.unshift(conv);
    store.activeId = conv.id;
    saveStore();
  }
  return activeConv();
}

function addMessageToConv(role, text, meta, image) {
  const conv = ensureActive();
  conv.messages.push({ role, text, meta: meta || null, image: image || null });
  if (role === "user" && conv.title === "Yeni sohbet") {
    conv.title = deriveTitle(conv.messages);
  }
  conv.updated = Date.now();
  store.conversations = [conv, ...store.conversations.filter((c) => c.id !== conv.id)];
  saveStore();
  renderSidebar();
}

// --- DOM render ---
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
      /* pano yoksa sessiz */
    }
  });
  bubble.appendChild(btn);
}

function renderBubble(role, text, { meta = null, image = null } = {}) {
  const el = document.createElement("div");
  el.className = `bubble ${role}`;
  if (image) {
    const img = document.createElement("img");
    img.src = image;
    img.className = "bubble-img";
    el.appendChild(img);
  }
  if (role === "assistant") {
    const body = document.createElement("div");
    body.innerHTML = renderMarkdown(text);
    el.appendChild(body);
    addCopyButton(el, () => text);
  } else if (text) {
    const span = document.createElement("span");
    span.textContent = text;
    el.appendChild(span);
  }
  chat.appendChild(el);
  if (meta) addMeta(meta);
  scrollDown();
  return el;
}

function addMeta(text) {
  const el = document.createElement("div");
  el.className = "meta";
  el.textContent = text;
  chat.appendChild(el);
  scrollDown();
}

function renderWelcome() {
  chat.innerHTML = `
    <div id="welcome">
      <span class="welcome-logo">Z</span>
      <h2>Merhaba, ben Zenith.</h2>
      <p>Birden fazla ucretsiz yapay zeka modelini birlikte calistiran kisisel asistaniniz. Ne yapmami istersiniz, efendim?</p>
      <div class="chips">
        <button class="chip" data-fill="wiki: kara delik">Wikipedia ozeti</button>
        <button class="chip" data-fill="hava: Istanbul">Hava durumu</button>
        <button class="chip" data-fill="kur: 100 dolar tl">Doviz kuru</button>
        <button class="chip" data-fill="haber: ">Son haberler</button>
        <button class="chip" data-fill="sifre: 20">Sifre uret</button>
        <button class="chip" data-fill="not: ">Not al</button>
        <button class="chip" data-send="__council__">Konseye sor</button>
      </div>
    </div>`;
}

function renderActive() {
  chat.innerHTML = "";
  const conv = activeConv();
  if (!conv || !conv.messages.length) {
    renderWelcome();
    return;
  }
  for (const m of conv.messages) {
    renderBubble(m.role, m.text, { meta: m.meta, image: m.image });
  }
}

function renderSidebar() {
  conversationList.innerHTML = "";
  for (const conv of store.conversations) {
    const row = document.createElement("div");
    row.className = "conv-row" + (conv.id === store.activeId ? " active" : "");
    const title = document.createElement("button");
    title.className = "conv-title";
    title.textContent = conv.title || "Yeni sohbet";
    title.addEventListener("click", () => {
      store.activeId = conv.id;
      saveStore();
      renderActive();
      renderSidebar();
      closeSidebar();
    });
    const del = document.createElement("button");
    del.className = "conv-del";
    del.textContent = "✕";
    del.title = "Sil";
    del.addEventListener("click", (e) => {
      e.stopPropagation();
      store.conversations = store.conversations.filter((c) => c.id !== conv.id);
      if (store.activeId === conv.id) store.activeId = store.conversations[0]?.id || null;
      saveStore();
      renderActive();
      renderSidebar();
    });
    row.appendChild(title);
    row.appendChild(del);
    conversationList.appendChild(row);
  }
}

// --- Composer ---
function autoGrow() {
  input.style.height = "auto";
  input.style.height = `${Math.min(input.scrollHeight, 120)}px`;
}
input.addEventListener("input", autoGrow);
input.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey && !e.isComposing) {
    e.preventDefault();
    form.requestSubmit();
  }
});

function speak(text) {
  return new Promise((resolve) => {
    const wants = ttsToggle.checked || voiceMode;
    if (!wants || !("speechSynthesis" in window)) return resolve();
    speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(text.slice(0, 500));
    u.lang = "tr-TR";
    u.onend = resolve;
    u.onerror = resolve;
    speechSynthesis.speak(u);
  });
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

function historyForApi() {
  const conv = activeConv();
  if (!conv) return [];
  return conv.messages.map((m) => ({ role: m.role, content: m.text }));
}

async function sendMessage(message, image) {
  if (busy) return "";
  if (!message && !image) return "";
  busy = true;

  const history = historyForApi();
  document.getElementById("welcome")?.remove();
  renderBubble("user", message, { image });
  addMessageToConv("user", message, null, image);
  input.value = "";
  autoGrow();

  const bubble = document.createElement("div");
  bubble.className = "bubble assistant streaming";
  const body = document.createElement("div");
  bubble.appendChild(body);
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
        history,
        image: image || null,
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
          body.innerHTML = renderMarkdown(full);
          scrollDown();
        } else if (event.type === "meta") {
          meta = metaFor(event);
        } else if (event.type === "error") {
          full = event.text;
          body.innerHTML = renderMarkdown(full);
        }
      }
    }
  } catch (err) {
    full = full || `[baglanti hatasi] ${err}`;
    body.innerHTML = renderMarkdown(full);
  }

  bubble.classList.remove("streaming");
  addCopyButton(bubble, () => full);
  if (meta) addMeta(meta);
  addMessageToConv("assistant", full, meta, null);
  busy = false;
  await speak(full);
  return full;
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  const message = input.value.trim();
  const image = pendingImage;
  clearImage();
  if (message || image) sendMessage(message, image);
});

// --- Oneri cipleri ---
document.addEventListener("click", (e) => {
  const chip = e.target.closest(".chip");
  if (!chip) return;
  if (chip.dataset.send === "__council__") {
    councilToggle.checked = true;
    input.value = "Kuantum bilgisayarlari basit bir dille anlatir misin?";
  } else {
    input.value = chip.dataset.fill || "";
  }
  autoGrow();
  input.focus();
});

// --- Sidebar / yeni sohbet ---
function openSidebar() {
  sidebar.hidden = false;
  sidebarOverlay.hidden = false;
  renderSidebar();
}
function closeSidebar() {
  sidebar.hidden = true;
  sidebarOverlay.hidden = true;
}
menuBtn.addEventListener("click", openSidebar);
sidebarOverlay.addEventListener("click", closeSidebar);
newChatBtn.addEventListener("click", () => {
  const conv = { id: newId(), title: "Yeni sohbet", messages: [], updated: Date.now() };
  store.conversations.unshift(conv);
  store.activeId = conv.id;
  saveStore();
  renderActive();
  renderSidebar();
  closeSidebar();
  input.focus();
});

exportBtn.addEventListener("click", () => {
  const conv = activeConv();
  if (!conv || !conv.messages.length) return;
  const lines = conv.messages.map((m) => `**${m.role === "user" ? "Sen" : "Zenith"}:** ${m.text}`);
  const blob = new Blob([`# ${conv.title}\n\n${lines.join("\n\n")}\n`], { type: "text/markdown" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "zenith-sohbet.md";
  a.click();
  URL.revokeObjectURL(a.href);
});

// --- Gorsel yukleme ---
attachBtn.addEventListener("click", () => imageInput.click());
imageInput.addEventListener("change", () => {
  const file = imageInput.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = () => {
    pendingImage = reader.result;
    imageThumb.src = pendingImage;
    imagePreview.hidden = false;
  };
  reader.readAsDataURL(file);
  imageInput.value = "";
});
function clearImage() {
  pendingImage = null;
  imagePreview.hidden = true;
  imageThumb.src = "";
}
imageRemove.addEventListener("click", clearImage);

// --- Sesli giris + sesli konusma modu ---
const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
let recognition = null;
if (SpeechRec) {
  micBtn.hidden = false;
  voiceBtn.hidden = false;
  recognition = new SpeechRec();
  recognition.lang = "tr-TR";
  recognition.interimResults = false;
}

function startListening() {
  if (!recognition) return;
  micBtn.classList.add("recording");
  try {
    recognition.start();
  } catch {
    /* zaten calisiyor */
  }
}

if (recognition) {
  micBtn.addEventListener("click", () => {
    voiceMode = false;
    voiceBtn.classList.remove("active");
    startListening();
  });

  voiceBtn.addEventListener("click", () => {
    voiceMode = !voiceMode;
    voiceBtn.classList.toggle("active", voiceMode);
    if (voiceMode) {
      startListening();
    } else {
      try {
        recognition.stop();
      } catch {
        /* yok say */
      }
      if ("speechSynthesis" in window) speechSynthesis.cancel();
    }
  });

  recognition.onresult = async (event) => {
    const transcript = event.results[0][0].transcript;
    micBtn.classList.remove("recording");
    if (voiceMode) {
      await sendMessage(transcript, null);
      if (voiceMode) startListening();
    } else {
      input.value = transcript;
      autoGrow();
      input.focus();
    }
  };
  recognition.onend = () => micBtn.classList.remove("recording");
  recognition.onerror = () => {
    micBtn.classList.remove("recording");
    if (voiceMode) {
      voiceMode = false;
      voiceBtn.classList.remove("active");
    }
  };
}

// --- Acilis ---
(async () => {
  renderActive();
  renderSidebar();

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
    /* otomatik modda kal */
  }

  try {
    const res = await fetch("/api/health");
    const data = await res.json();
    if (data.status === "no_models" && !activeConv()?.messages.length) {
      addMeta(data.hint);
    }
  } catch {
    /* sessiz */
  }
})();

if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js").catch(() => {});
  });
}
