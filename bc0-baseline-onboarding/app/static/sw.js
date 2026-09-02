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
/* HUELLE 535a45f0 — Pruefsumme (SHA-256, acht Stellen) von static/index.html.
   Aendert sich die Huelle, aendert sich dieser Wert. Der Test
   test_cache_name_haengt_an_der_huelle schlaegt dann fehl und zwingt zu der
   Entscheidung, die am 01.09.2026 unterblieben ist: CACHE erhoehen — ja oder nein?
   Am 02.09.2026 nachgeruestet, weil kein Test den vergessenen Namenswechsel sah. */
const CACHE = "bc0-pwa-v6";   /* 02.09.2026, ein Sprung von v5 aus, mit zwei
                                 Aenderungen an der Huelle: die Eignerspalte
                                 liest prozess_personen statt des leeren Feldes
                                 owner_name (die zwei Eingabefelder sind durch
                                 einen Hinweis ersetzt), und esc() maskiert
                                 zusaetzlich das Hochkomma.

                                 Der Name blieb bei der zweiten Aenderung auf
                                 v6 — ausgerollt ist v5, und der Name muss sich
                                 gegenueber dem AUSGELIEFERTEN Stand
                                 unterscheiden, nicht gegenueber jedem
                                 Zwischenstand. Sonst zaehlt er Arbeitsschritte
                                 statt Auslieferungen. */   /* 01.09.2026: Die Huelle hat sich geaendert — das
                                 Anfrageformular ist heraus, die Kachel fuehrt nach
                                 /anfrage/. Am 02.09. beim Ausrollen bemerkt, dass der
                                 Name dabei auf v4 stehen geblieben war: die Regel aus
                                 Zeile 7 war verletzt, ohne dass ein Test es merkte. */
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
      /* NUR die eigenen Ablagen aufraeumen. Seit dem 01.09.2026 gibt es eine
         zweite Anwendung unter /anfrage/ mit eigenem Cache. `caches.keys()`
         liefert die Ablagen des GANZEN Ursprungs — ein Filter auf
         "alles ausser meinem Namen" haette beim Aktivieren die Ablage der
         anderen Anwendung geloescht, und die andere beim naechsten
         Aktivieren diese hier. Zwei Worker, die sich gegenseitig ausraeumen. */
      .then((keys) => Promise.all(
        keys.filter((k) => k.startsWith("bc0-pwa-") && k !== CACHE)
            .map((k) => caches.delete(k))))
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
