const chat = document.getElementById("chat");
const form = document.getElementById("chat-form");
const input = document.getElementById("chat-input");
const councilToggle = document.getElementById("council-toggle");
const resetBtn = document.getElementById("reset-btn");
const modelsBtn = document.getElementById("models-btn");

function addBubble(role, text) {
  const el = document.createElement("div");
  el.className = `bubble ${role}`;
  el.textContent = text;
  chat.appendChild(el);
  chat.scrollTop = chat.scrollHeight;
  return el;
}

function autoGrow() {
  input.style.height = "auto";
  input.style.height = `${Math.min(input.scrollHeight, 120)}px`;
}

input.addEventListener("input", autoGrow);

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

if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js").catch(() => {});
  });
}
