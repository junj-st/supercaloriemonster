const CACHE = "scm-shell-v1";
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

self.addEventListener("fetch", (e) => {
  const { request } = e;
  if (request.method !== "GET") return; // never intercept writes

  const url = new URL(request.url);
  // network-first for day summaries so recently-viewed days work offline
  if (url.pathname.startsWith("/logs/day/")) {
    e.respondWith(
      fetch(request)
        .then((resp) => {
          const copy = resp.clone();
          caches.open(CACHE).then((c) => c.put(request, copy));
          return resp;
        })
        .catch(() => caches.match(request))
    );
    return;
  }
  // cache-first for the app shell / static assets
  if (url.origin === location.origin && (url.pathname === "/" || url.pathname.startsWith("/static/"))) {
    e.respondWith(caches.match(request).then((hit) => hit || fetch(request)));
  }
});
