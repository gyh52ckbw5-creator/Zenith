// Zenith service worker.
// ONCE AG (network-first): her zaman guncel surumu getirmeye calisir, boylece
// yeni bir deploy telefonda aninda gorunur. Ag yoksa cache'e duser (cevrimdisi).
// Sohbet API'si (/api/*) hic cache'lenmez.

const CACHE_NAME = "zenith-static-v9";
const STATIC_ASSETS = ["/", "/static/style.css", "/static/app.js", "/manifest.json"];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.addAll(STATIC_ASSETS)));
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key)))
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (url.pathname.startsWith("/api/") || event.request.method !== "GET") {
    return; // API ve GET olmayanlar dogrudan aga gider
  }
  // Once ag; basarili olursa cache'i tazele, basarisizsa cache'ten ver.
  event.respondWith(
    fetch(event.request)
      .then((response) => {
        const copy = response.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(event.request, copy)).catch(() => {});
        return response;
      })
      .catch(() => caches.match(event.request).then((cached) => cached || caches.match("/")))
  );
});
