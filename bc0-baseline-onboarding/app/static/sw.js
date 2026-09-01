/* BC0 Onboarding-Tool – Service Worker (PWA) v2
   Strategie:
   - /api/... wird NIE gecacht (immer live, POST/PUT sowieso nie).
   - Navigation & index.html: network-first (frische UI), Fallback Cache (offline).
   - Übrige statische Assets (Icons, Manifest): cache-first.
   Registriert unter Scope "/" (sw.js wird von app.py unter /sw.js ausgeliefert). */
/* v3 (28.08.2026): Der Name wird bei jeder Aenderung an der Shell erhoeht.
   Grund: "activate" loescht alle Caches, deren Name nicht CACHE ist. Blieb
   der Name gleich, ueberlebte der beim ERSTEN Besuch abgelegte Stand von
   /static/index.html beliebig lange und wurde offline weiter ausgeliefert
   — am 28.08.2026 nachgemessen: 41.292 Zeichen gegenueber 158.706 live. */
const CACHE = "bc0-pwa-v4";   /* 28.08.2026, zweite Aenderung des Tages: Passwortwechsel */
const SHELL = [
  "/",
  "/static/index.html",
  "/static/manifest.json",
  "/static/icon-192.png",
  "/static/icon-512.png"
];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET") return;               // POST/PUT etc. immer ans Netz
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return; // fremde Origins nicht anfassen
  if (url.pathname.startsWith("/api/")) return;    // API nie cachen

  const isShell = req.mode === "navigate" || url.pathname === "/" || url.pathname === "/static/index.html";

  if (isShell) {
    // network-first: frische App-Shell, offline aus dem Cache
    e.respondWith(
      fetch(req).then((res) => {
        const copy = res.clone();
        caches.open(CACHE).then((c) => c.put(req, copy)).catch(() => {});
        return res;
      }).catch(() =>
        caches.match(req).then((hit) => hit || caches.match("/static/index.html"))
      )
    );
    return;
  }

  // cache-first für statische Assets
  e.respondWith(
    caches.match(req).then((hit) =>
      hit || fetch(req).then((res) => {
        const copy = res.clone();
        caches.open(CACHE).then((c) => c.put(req, copy)).catch(() => {});
        return res;
      })
    )
  );
});
