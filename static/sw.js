const CACHE = "scm-shell-v2";
const SHELL = ["/", "/static/index.html", "/static/style.css", "/static/app.js", "/static/manifest.json"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)));
  self.skipWaiting();
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
  );
  self.clients.claim();
});

// Network-first with cache fallback: always try the network so updated assets
// show immediately; fall back to the cached copy when offline. Keeps offline
// viewing (the app shell + recently-viewed days) while avoiding the stale-asset
// problem that a cache-first shell causes during active development.
function networkFirst(request) {
  return fetch(request)
    .then(async (resp) => {
      if (resp && resp.ok) {
        const cache = await caches.open(CACHE);
        await cache.put(request, resp.clone());
      }
      return resp;
    })
    .catch(() => caches.match(request));
}

self.addEventListener("fetch", (e) => {
  const { request } = e;
  if (request.method !== "GET") return; // never intercept writes

  const url = new URL(request.url);
  if (url.origin !== location.origin) return;

  if (
    url.pathname === "/" ||
    url.pathname.startsWith("/static/") ||
    url.pathname.startsWith("/logs/day/")
  ) {
    e.respondWith(networkFirst(request));
  }
});
