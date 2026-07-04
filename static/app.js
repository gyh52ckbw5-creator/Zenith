const chat = document.getElementById("chat");
const form = document.getElementById("chat-form");
const input = document.getElementById("chat-input");
const councilToggle = document.getElementById("council-toggle");
const ttsToggle = document.getElementById("tts-toggle");
const resetBtn = document.getElementById("reset-btn");
const modelsBtn = document.getElementById("models-btn");
const micBtn = document.getElementById("mic-btn");

function addBubble(role, text) {
  const el = document.createElement("div");
  el.className = `bubble ${role}`;
  el.textContent = text;
  chat.appendChild(el);
  chat.scrollTop = chat.scrollHeight;
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

  const thinking = addBubble("assistant", "...");

  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, council: councilToggle.checked }),
    });
    const data = await res.json();
    thinking.textContent = data.reply;
    if (data.source === "council" && data.contributors?.length > 1) {
      addMeta(`konsey: ${data.contributors.length} model birlikte cevapladi`);
    } else if (data.source === "search") {
      addMeta("web aramasiyla cevaplandi");
    }
    speak(data.reply);
  } catch (err) {
    thinking.textContent = `[baglanti hatasi] ${err}`;
  }
});

resetBtn.addEventListener("click", async () => {
  await fetch("/api/reset", { method: "POST" });
  chat.innerHTML = "";
  addBubble("system", "Hafiza temizlendi.");
});

modelsBtn.addEventListener("click", async () => {
  const res = await fetch("/api/models");
  const data = await res.json();
  addBubble("system", data.models.join("\n"));
});

// Sesli giris: destekleyen tarayicilarda mikrofon butonunu goster.
// (iOS Safari'de ayrica klavyedeki dikte tusu her zaman calisir.)
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

// Acilista sunucu sagligini kontrol et: hic model hazir degilse kullaniciyi yonlendir.
(async () => {
  try {
    const res = await fetch("/api/health");
    const data = await res.json();
    if (data.status === "no_models") {
      addBubble("system", data.hint);
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
