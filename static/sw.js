// Zenith icin minimal service worker: statik dosyalari cache'ler, boylece
// iOS'ta "Ana Ekrana Ekle" ile acilan uygulama daha hizli yuklenir.
// Sohbet API'si (/api/*) her zaman aga gider, cache'lenmez.

const CACHE_NAME = "zenith-static-v4";
const STATIC_ASSETS = [
  "/",
  "/static/style.css",
  "/static/app.js",
  "/manifest.json",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(STATIC_ASSETS))
  );
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
  if (url.pathname.startsWith("/api/")) {
    return; // API cagrilarini asla cache'leme
  }
  event.respondWith(
    caches.match(event.request).then((cached) => cached || fetch(event.request))
  );
});
