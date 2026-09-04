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
/* HUELLE c72eba15 — Pruefsumme (SHA-256, acht Stellen) von static/index.html.
   Aendert sich die Huelle, aendert sich dieser Wert. Der Test
   test_cache_name_haengt_an_der_huelle schlaegt dann fehl und zwingt zu der
   Entscheidung, die am 01.09.2026 unterblieben ist: CACHE erhoehen — ja oder nein?
   Am 02.09.2026 nachgeruestet, weil kein Test den vergessenen Namenswechsel sah. */
const CACHE = "bc0-pwa-v11";  /* 04.09.2026, dritte Aenderung: Stand des Berichts und
                                 Vorher/Nachher im Reifegradbericht (v2.9). Davor v10:
                                 04.09.2026, zweite Aenderung: Block "Erhebung" im Self-Rating
                                 (Stand, abschliessen, neu — v2.8 Nacherhebung). Davor v9:
                                 04.09.2026: Uebergabe an BC2 je Anfrage, vollstaendig (v2.7), Widerruf,
                                 Stand vom Paketdatum) im Gate-0-Reiter — Schema v2.6.
                                 Davor v8 — 03.09.2026, zweite Aenderung des Tages:
                                 Volltextsuche ueber die Belege im Self-Rating
                                 (Beleg-Ingestion Stufe 2, Punkt 139). Ein
                                 Suchfeld, Treffer mit Fundstelle und
                                 Belastbarkeit. **Ausgerollt ist v7** — und der
                                 Name muss sich gegenueber dem AUSGELIEFERTEN
                                 Stand unterscheiden, deshalb v8 und nicht
                                 stehenbleiben.

                                 v7 (03.09.2026): Trichter 3 in der Anfrageliste —
                                 ein Knopf „Vorschlag holen" an jeder Anfrage
                                 ohne Prozessbezug, die Treffer daneben, und
                                 „Übernehmen" schreibt mit Herkunft
                                 vorschlag_bc0. Das ist Bedienung, nicht
                                 Kosmetik: Wer offline den alten Stand behielte,
                                 saehe den Knopf nicht und hielte den Trichter
                                 fuer nicht ausgerollt. Deshalb JA — erhoeht.

                                 v6 (02.09.2026) war ein Sprung von v5 aus, mit zwei
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
