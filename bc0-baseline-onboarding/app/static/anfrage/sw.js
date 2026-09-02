/* Anfrage-PWA — eigener Service Worker, eigener Geltungsbereich.
   Er liegt unter /anfrage/ und bedient deshalb NUR diese Anwendung. Der
   Service Worker von BC0 liegt unter / und wuerde /anfrage/ zwar formal
   mit abdecken — zwei Worker fuer denselben Pfad waeren aber genau die
   Sorte Verflechtung, die diese Trennung vermeiden soll. Der engere
   Geltungsbereich gewinnt; das ist hier Absicht und kein Zufall.

   Strategie wie bei BC0: /api/... nie cachen, die Huelle network-first,
   uebrige Dateien cache-first. Der Name wird bei jeder Aenderung an der
   Huelle erhoeht — sonst ueberlebt der Stand vom ersten Besuch ewig. */
/* HUELLE f5ce0c6b — Pruefsumme (SHA-256, acht Stellen) von static/anfrage/index.html.
   Aendert sich die Huelle, aendert sich dieser Wert. Der Test
   test_cache_name_haengt_an_der_huelle schlaegt dann fehl und zwingt zu der
   Entscheidung, die am 01.09.2026 unterblieben ist: CACHE erhoehen — ja oder nein?
   Am 02.09.2026 nachgeruestet, weil kein Test den vergessenen Namenswechsel sah. */
const CACHE = "coe-anfrage-v2";   /* 02.09.2026: eigene Symbole. Die Huelle ist
                                     unveraendert, aber SHELL zeigt auf andere
                                     Dateien — ohne neuen Namen lieferte der Cache
                                     weiter die BC0-Symbole aus. */
const SHELL = ["/anfrage/", "/anfrage/manifest.json",
               "/static/anfrage/icon-192.png", "/static/anfrage/icon-512.png"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys()
      /* Nur die eigenen Ablagen — der Service Worker von BC0 haelt seine
         unter "bc0-pwa-*", und `caches.keys()` liefert beide. Ohne diesen
         Filter loeschte jeder Worker beim Aktivieren die Ablage des anderen. */
      .then((keys) => Promise.all(
        keys.filter((k) => k.startsWith("coe-anfrage-") && k !== CACHE)
            .map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;
  if (url.pathname.startsWith("/api/")) return;

  const isShell = req.mode === "navigate" || url.pathname === "/anfrage/" || url.pathname === "/anfrage";
  if (isShell) {
    e.respondWith(
      fetch(req).then((res) => {
        const copy = res.clone();
        caches.open(CACHE).then((c) => c.put(req, copy)).catch(() => {});
        return res;
      }).catch(() => caches.match(req).then((hit) => hit || caches.match("/anfrage/")))
    );
    return;
  }

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
