# BC0 — Sicherheitskonzept

**Projektgruppe KI-CoE-KMU · Bounded Context 0 (Baseline und Reifegrad)**
**Stand 20.08.2026 · Simeon Ehmer**

Dieses Papier beschreibt, was gebaut ist, mit welcher Begründung — und was
fehlt. Der zweite Teil ist der wichtigere. Alle Aussagen sind am Quelltext
belegt, nicht aus der Erinnerung geschrieben.

---

## 1. Schutzbedarf

| Datenart | Beispiel | Schutzbedarf | Begründung |
|---|---|---|---|
| Personenbezogene Daten | Name, Funktion, E-Mail, Telefon von Beschäftigten der Mandanten | **hoch** | Art. 4 Nr. 1 DSGVO; nicht anonymisiert, sondern pseudonymisiert |
| Geschäftsgeheimnisse | Prozessstruktur, Kostensätze, eingesetzte Systeme | **hoch** | Betriebs- und Geschäftsgeheimnis der teilnehmenden KMU |
| Bewertungen | 30 Bitkom-Items je Teilprozess | mittel | ohne Kontext wenig aussagekräftig |
| Zugangsdaten | Passwort-Hashes, Sitzungsschlüssel | **sehr hoch** | Schlüssel zu allem Vorstehenden |
| Belegdokumente | hochgeladene Nachweise | **hoch** | Inhalt unbekannt, potenziell alles davon |

Das dominierende Schutzziel ist **Vertraulichkeit**, und zwar in zwei Richtungen:
gegen Außenstehende und **zwischen den Mandanten**. Ein Mandant darf einen
anderen nicht sehen; das ist keine Bequemlichkeitsfrage, sondern die
Voraussetzung dafür, dass mehrere KMU überhaupt teilnehmen.

Verfügbarkeit ist nachrangig — es ist ein Erhebungswerkzeug, kein
Produktivsystem. Integrität ist mittel, aber durch die Ereignisspeicherung
(Gate-Entscheidungen und Erhebungen werden überlagert, nie überschrieben)
strukturell gestützt.

---

## 2. Was gebaut ist

### 2.1 Passwörter

**Verfahren:** PBKDF2-HMAC-SHA256, **600.000 Durchläufe**, 16 Byte Zufallssalz
je Passwort aus `secrets.token_bytes`. Mindestlänge 12 Zeichen, keine
Zeichenklassenpflicht.

**Speicherformat** (Django-Konvention, vier Felder):

```
pbkdf2_sha256$600000$<salz-base64>$<abdruck-base64>
```

Verfahren und Kostenparameter stehen **im Datensatz selbst**. Das ist der Punkt
an dieser Formatwahl: Eine Erhöhung der Durchläufe oder ein Wechsel auf Argon2
ist ohne Migration und ohne Zwangs-Passwortwechsel möglich. Beim Anmelden
prüft `muss_neu_gehasht_werden()`, ob der Hash unter veralteten Parametern
entstand, und erneuert ihn im selben Zug (Test `test_auth.py` Nr. 6).

**Warum PBKDF2 und nicht bcrypt oder Argon2id.** Beide wären fachlich
vorzuziehen — Argon2id ist speicherhart und damit gegen GPU-Angriffe deutlich
robuster. Sie benötigen aber eine zusätzliche Abhängigkeit (`argon2-cffi`,
`passlib`), bei bcrypt eine kompilierte Erweiterung im Container. PBKDF2 liegt
in der Standardbibliothek, ist nach **BSI TR-02102-1** und **NIST SP 800-132**
zulässig, und 600.000 Durchläufe sind die aktuelle **OWASP-Empfehlung** für
PBKDF2-HMAC-SHA256. Für eine Anwendung mit einer zweistelligen Zahl von Konten
halte ich das für angemessen; ich würde es bei einem Produktivsystem mit
Kundenzugängen anders entscheiden. **Die Abhängigkeitsliste der Anwendung
umfasst fünf Pakete** — das ist selbst ein Sicherheitsargument.

**Warum keine Zeichenklassenpflicht.** NIST SP 800-63B rät ausdrücklich davon
ab: Erzwungene Sonderzeichen führen zu kürzeren, schlechter merkbaren
Passwörtern und zu vorhersagbaren Mustern (`Passwort1!`). Die Länge ist der
wirksamere Hebel.

**Vergleich in konstanter Zeit.** `hmac.compare_digest`. Ein zeichenweiser
Vergleich würde über die Antwortdauer verraten, wie viele Zeichen bereits
stimmen. Das ist bei einem PBKDF2-Abdruck kein realistischer Angriff — der
Aufwand der Ableitung dominiert die Messung —, aber es kostet nichts und ist
die Gewohnheit, die man haben will.

**Beschädigte Hashes.** `hash_pruefen` gibt bei fehlerhaftem Aufbau `False`
zurück statt eine Ausnahme zu werfen. Ein `IndexError` beim Zerlegen des
Hash-Strings wäre über die Anmeldemaske als Denial of Service auslösbar
(Test `test_auth.py` Nr. 4).

### 2.2 Sitzungen

**Serverseitig, nicht als Token.** Beim Anmelden wird ein Schlüssel aus
`secrets.token_urlsafe(32)` — 256 Bit Entropie — erzeugt und dem Browser als
Cookie mitgegeben. In der Datenbank steht **nur der SHA-256-Abdruck**.

Warum nur ein einfacher SHA-256 und nicht wieder PBKDF2: Der Ausgangswert ist
bereits 256 Bit Zufall und nicht erratbar; ein Wörterbuchangriff ist nicht
möglich. Ein teures Verfahren würde nur jede einzelne Anfrage verlangsamen.

Die Eigenschaft, die das absichert: **Wer die Tabelle `sessions` liest, kann
keine Sitzung übernehmen.** Ein Datenbankleck kostet die Vertraulichkeit der
Inhalte, aber nicht zusätzlich die Konten (Test `test_auth.py` Nr. 22 — der
wichtigste Test dieser Datei).

**Warum serverseitig und nicht JWT.** Der entscheidende Unterschied ist der
**Widerruf**. Ein JSON Web Token ist bis zum Ablauf gültig; ein gesperrtes
Konto könnte weiterarbeiten. Hier wirken drei Vorgänge sofort:

- Passwortwechsel beendet **alle** Sitzungen des Kontos (Test Nr. 25)
- Sperren beendet die laufende Sitzung (Test Nr. 26)
- Rollen- und Mandantenänderungen wirken ohne Neuanmeldung, weil der Benutzer
  je Anfrage frisch geladen wird (Tests Nr. 27 und `test_mandantenfilter.py`
  Nr. 11)

Der Preis ist eine Datenbankabfrage je Anfrage. Bei dieser Nutzungsgröße
irrelevant.

**Cookie-Attribute** (`bc0_auth/routen.py`, Zeile 128 ff.):

| Attribut | Wert | Wirkung |
|---|---|---|
| `httponly` | `True` | kein Zugriff aus JavaScript — ein XSS kann den Schlüssel nicht auslesen |
| `secure` | `True` im Betrieb | nur über HTTPS; per `BC0_COOKIE_UNSICHER=1` nur für Tests abschaltbar |
| `samesite` | `lax` | keine Mitsendung bei fremdinitiierten POST-Anfragen |
| `max_age` | Sitzungsdauer | serverseitig ebenfalls geprüft, nicht nur im Browser |

Der Schlüssel steht **nicht** im Antwortkörper der Anmeldung, sondern
ausschließlich im Cookie (Test `test_app_zugriff.py` Nr. 8).

### 2.3 Anmeldepflicht als Boden

Der Schutz liegt in einer **Middleware**, nicht in `Depends` an jedem Endpunkt.
Die Begründung steht im Quelltext und ist der bessere Teil des Entwurfs:

> Würde der Schutz allein an `Depends` hängen, wäre ein neuer Endpunkt so lange
> offen, bis jemand daran denkt — der Fehler wäre still und von außen nicht
> sichtbar. Diese Middleware dreht die Vorgabe um: **Alles unter `/api/`
> verlangt eine Anmeldung**, es sei denn, der Pfad steht ausdrücklich in
> `OFFENE_PFADE`. Eine vergessene Absicherung führt damit nicht zu einem
> offenen Endpunkt, sondern zu einem, der 401 meldet — ein Fehler, der sofort
> auffällt.

`OFFENE_PFADE` umfasst genau drei Einträge, jeder einzeln kommentiert:
`/api/auth/login` (sonst könnte sich niemand anmelden), `/api/auth/logout`
(muss auch mit abgelaufener Sitzung aufrufbar sein), `/api/auth/status` (die
Oberfläche fragt damit ab, ob jemand angemeldet ist). Offen bleibt außerdem die
PWA-Hülle selbst — sie enthält keine Mandantendaten.

Im Zweifel wird abgewiesen: `_sicher_aufloesen()` fängt jede Ausnahme beim
Auflösen der Sitzung ab und liefert `None`, also 401. Ein Datenbankfehler darf
nicht dazu führen, dass eine Anfrage als „angemeldet" durchgeht.

Test Nr. 3 in `test_app_zugriff.py` ist die Probe auf das Muster: ein Pfad, den
es gar nicht gibt, muss **401 statt 404** liefern.

### 2.4 Mandantentrennung

Zwei Ebenen, unabhängig voneinander:

**In der Anwendung.** `pruefe_mandant(benutzer, cid)` in jedem
mandantenbezogenen Endpunkt. Ein Admin sieht alles, ein Benutzer nur die ihm
zugeordneten Mandanten. Ein fremder Mandant liefert **404, nicht 403** — die
Existenz eines fremden Mandanten soll nicht erkennbar sein. Elf Tests in
`test_mandantenfilter.py`, dazu je ein Trennungstest in jeder weiteren
Testdatei.

Zwei Punkte, die häufig übersehen werden und hier geprüft sind:

- **Rechteausweitung über den Umweg.** Ein Benutzer darf keinen Mandanten
  anlegen und kein YAML importieren. Sonst wäre die Trennung wertlos: Wer sich
  selbst einen zweiten Mandanten anlegen kann, hebt sie auf (Tests Nr. 8, 9).
- **Unsichere direkte Objektreferenz.** Die Teilprozess-ID allein öffnet
  nichts; die Zugehörigkeit zum Mandanten wird mitgeprüft
  (`test_gate0.py` Nr. 17).

**In der Datenbank.** Je Bounded Context eine eigene Rolle (`bc1_role` bis
`bc4_role`) und ein eigenes Schema (`bc1` bis `bc4`), dazu die Gruppenrolle
`bc_leser`. Jeder liest alles, schreibt nur im eigenen Schema, **niemand
schreibt in `public`** — das ist BC0 vorbehalten (ADR-003). Diese Trennung
gilt auch für Zugriffe, die an der Anwendung vorbeigehen, etwa über einen
SQL-Client.

### 2.5 Pseudonymisierung an den Schnittstellen

Nach ADR-004 trägt jede benannte Entität neben dem Klarnamen eine stabile ID
(`P-01`, `S-03`, `KP-02.TP-3`, `E-2026-05`). **An BC1 bis BC4 und an
Sprachmodelle geht nur die ID.** Der Klarname bleibt in der Datenbank.

Das ist ausdrücklich **Pseudonymisierung, nicht Anonymisierung** — Art. 4 Nr. 5
DSGVO; die Daten bleiben personenbezogen, die Zuordnungstabelle existiert. Das
ist im Datenschutzpapier so benannt und wird nicht schöngeredet.

Abgesichert durch `test_entitaeten.py` Nr. 23: Der Test läuft über **alle**
`v_*`-Sichten und schlägt fehl, sobald eine davon eine Klarnamens- oder
Kontaktspalte aufnimmt — auch wenn das jemand später versehentlich tut. Das ist
die Art von Test, die eine Zusicherung über die Zeit trägt.

**Nachtrag 23.08.2026 — die Zusicherung reicht weniger weit, als dieser Abschnitt
behauptet hat.** Der Sichtentest prüft die Sichten. Er kann nicht prüfen, ob eine
nachgelagerte Rolle die **Tabelle** liest, an der Sicht vorbei. Genau das ist der Fall:
`bc1_role` hat ein direktes `SELECT` auf `ref_personen` und `prozess_personen`. Der Satz
„an BC1 bis BC4 geht nur die ID" gilt für den Weg über die Sichten und über den
Snapshot-Export — nicht für den direkten Datenbankzugang. Siehe 3.8.

### 2.6 SQL-Einschleusung

**138 parametrisierte `execute`-Aufrufe. Keine einzige Stelle, an der eine
Benutzereingabe per Zeichenkettenformatierung in SQL gerät.**

Die `%s`-Formatierungen, die im Quelltext vorkommen, setzen ausschließlich
konstante Tabellen- und Spaltennamen sowie den Dialektzweig zusammen
(`"::text" if PG else ""`). Nachgeprüft durch Durchsicht aller Fundstellen am
19.08.2026.

Die Klasse `_Cx` vereinheitlicht den Platzhalterstil — im Quelltext steht immer
`?`, für PostgreSQL wird daraus `%s`. Das ist nebenbei ein Sicherheitsvorteil:
Es gibt genau eine Stelle, an der Parameter das SQL erreichen.

### 2.7 Weitere Maßnahmen

| Maßnahme | Umsetzung |
|---|---|
| **XSS** | Die Oberfläche baut HTML als Zeichenketten. Eine Escape-Funktion `esc()` ist definiert und **156-mal** verwendet; Statuswerte gehen über `textContent`. |
| **YAML-Import** | `yaml.safe_load`, nicht `yaml.load` — keine Objektinstanziierung aus der Datei. Zusätzlich Admins vorbehalten. |
| **Datei-Upload** | Größenbegrenzung 15 MB, Dateiname wird auf `[\w.\-äöüÄÖÜß ]` gefiltert und auf 120 Zeichen gekürzt, Ablageschlüssel enthält eine UUID — kein Pfaddurchstieg möglich. |
| **Transport** | Caddy mit automatischem Let's-Encrypt-Zertifikat unter `bc0.perspektivwechsel.ai`; die Anwendung selbst ist nicht nach außen veröffentlicht (`expose`, nicht `ports`). |
| **Netz** | Hetzner-Firewall vor der VM; nur 80, 443 und SSH offen (Issue #133.3). |
| **Geheimnisse** | `.env` ausschließlich auf dem Server, in `.gitignore`, nie im Repository. Passwörter für Benutzerkonten werden über `getpass` erfragt, nie als Kommandozeilenargument (sonst stünden sie in der Shell-Historie). |
| **Standort** | Anwendung in Nürnberg, Datenbank in Irland — **keine Drittlandsübermittlung im Betrieb**. |
| **Konto-Selbstschutz** | Ein Admin kann sich nicht selbst herabstufen; sonst könnte der letzte Admin die Anwendung führungslos machen (Test `test_app_zugriff.py` Nr. 12). |

---

## 3. Was fehlt

Nach Gewicht geordnet. Die Reihenfolge ist meine Einschätzung, nicht die
Reihenfolge der Umsetzung.

### 3.1 Kein Schutz gegen wiederholte Anmeldeversuche — **hoch**

Es gibt weder eine Ratenbegrenzung noch eine Kontosperre nach N Fehlversuchen
noch eine Verzögerung. Ein Angreifer kann Passwörter so schnell durchprobieren,
wie der Server PBKDF2 rechnet.

**Was das relativiert:** 600.000 Durchläufe kosten je Versuch rund 200 ms
Rechenzeit auf dem Server — das begrenzt die Rate faktisch auf wenige Versuche
pro Sekunde und Kern. Das ist Nebenwirkung, nicht Absicht, und es ist zugleich
der Angriffsvektor: **Dieselbe Eigenschaft macht die Anmeldemaske zum
Denial-of-Service-Hebel.** Zwanzig gleichzeitige Anmeldeversuche legen die CPU
der VM lahm.

**Empfehlung:** Zähler je E-Mail und je IP, Verzögerung ab dem fünften
Fehlversuch, Sperre ab dem zehnten. Aufwand ~4 h, Tabelle ist trivial.
**Vor Freigabe an externe Mandanten.**

### 3.2 Keine Sicherheitskopfzeilen — **hoch, aber billig**

Das Caddyfile umfasst sechs Zeilen: Domain, `encode gzip`, `reverse_proxy`.
Es fehlen:

| Kopfzeile | Wirkung |
|---|---|
| `Content-Security-Policy` | die wirksamste zweite Verteidigungslinie gegen XSS |
| `Strict-Transport-Security` | erzwingt HTTPS auch beim ersten Aufruf |
| `X-Content-Type-Options: nosniff` | verhindert MIME-Raten |
| `X-Frame-Options` / `frame-ancestors` | Clickjacking |
| `Referrer-Policy` | keine Pfadweitergabe an Dritte |

Eine CSP ist hier ungewöhnlich einfach umzusetzen, weil die Anwendung **keine
externen Ressourcen lädt** — keine CDN, keine Schriften, keine Analytik. `script-src 'self'`
würde ohne Anpassung greifen, sofern die Inline-Skripte in eine eigene Datei
wandern oder ein Nonce bekommen.

**Aufwand: ~1 h.** Das ist die Maßnahme mit dem besten Verhältnis von Nutzen zu
Aufwand in dieser Liste.

### 3.3 Kein CSRF-Token über `SameSite=Lax` hinaus — **mittel**

`SameSite=Lax` verhindert, dass das Sitzungscookie bei fremdinitiierten
POST-Anfragen mitgeht, und deckt damit den Regelfall ab. Es ist aber die
einzige Schicht. Zusammen mit einer fehlenden CSP und der Tatsache, dass die
API JSON erwartet (was ein einfaches Formular-CSRF ohnehin erschwert), halte
ich das Restrisiko für vertretbar — aber es ist eines.

**Empfehlung:** Double-Submit-Token bei den schreibenden Endpunkten.
Aufwand ~4 h.

### 3.4 Kein Änderungsprotokoll — **mittel bis hoch, je nach Maßstab**

Die Tabelle `audit_log` ist seit dem 22.06.2026 angelegt und **leer**. `app.py`
schreibt an keiner Stelle hinein. Es ist also nicht nachvollziehbar, wer wann
was geändert oder gelöscht hat.

Für ein Erhebungswerkzeug in einer Projektgruppe ist das hinnehmbar. Für den
Nachweis nach Art. 5 Abs. 2 DSGVO (Rechenschaftspflicht) und für die
Protokollierungspflicht nach Art. 12 EU AI Act — sobald hier Hochrisiko-Anteile
entstehen — ist es das nicht.

Das ist zugleich der Grund, warum 3.5 noch offen ist.

### 3.5 Löschen nicht auf Admins beschränkt — **mittel**

`delete_document` steht jedem Angemeldeten mit Zugriff auf den Mandanten offen.
Die Anmerkung im Quelltext benennt die Abhängigkeit:

> Die Beschränkung auf Admins kommt mit Etappe 4c, zusammen mit dem
> Änderungsprotokoll — **ein Löschrecht ohne Protokoll wäre die schlechtere
> Hälfte der Lösung.**

Das halte ich weiter für richtig. Beides gehört in einen Schritt.

### 3.6 Keine Nur-Lesen-Rolle — **niedrig, aber bewusst**

Es gibt genau zwei Rollen: `benutzer` und `admin`. Wer den Reifegradbericht nur
ansehen soll, braucht dennoch ein Konto mit Schreibrecht auf seinen Mandanten.

**Der gewählte Ersatz:** ein eigener Übungsmandant mit zwölf Konten, alle mit
Rolle `benutzer` und ausschließlich diesem Mandanten zugeordnet. Wer dort etwas
kaputt macht, macht nur Übungsdaten kaputt. Das löst den Anwendungsfall
„ausprobieren", nicht den Anwendungsfall „ansehen dürfen, ohne ändern zu
können". Für die Halbzeitpräsentation reicht es.

### 3.7 Datenschutz-Folgenabschätzung und AVV offen — **organisatorisch, hoch**

Issue #144. Offen sind: Auftragsverarbeitungsverträge mit Hetzner und Supabase
(bei Supabase samt Standardvertragsklauseln wegen des US-Mutterkonzerns —
die Datenhaltung selbst liegt in Irland), Verarbeitungsverzeichnis,
Löschkonzept, Informationspflichten nach Art. 13 gegenüber den erfassten
Beschäftigten der Mandanten. Rechtsgrundlage der Verarbeitung ist zu bestimmen
(Art. 6 Abs. 1 lit. f mit Interessenabwägung, ggf. § 26 BDSG bei
Beschäftigtendaten).

Das ist kein Programmierfehler, sondern die Lücke mit dem größten realen
Risiko, sobald echte KMU-Daten eingehen.

### 3.8 Direkte Tabellenrechte laufen an der Sammelrolle vorbei — **hoch**

Gefunden am 23.08.2026 beim Einspielen der Rechteumstellung — durch die Gegenprobe,
nicht durch das Skript. Das Skript meldete Vollzug und hatte damit recht; die Wirkung
blieb trotzdem aus.

`bc_leser` **sieht aus wie** die Steuerung der Leserechte und ist es nicht. Neben der
Gruppenrolle bestehen **direkte** Berechtigungen an `bc1_role`:

| Befund | Tabellen |
|---|---|
| `bc1_role=r` **ohne** `bc_leser` | `ref_personen`, `prozess_personen` |
| `bc1_role=r` **und** `bc_leser=r` (doppelt) | `ref_anfragen`, `ref_berichtstexte`, `ref_erhebungen`, `ref_gate_pruefpunkte`, `ref_items`, `ref_systeme_katalog`, `ref_teilprozesse` |

Zwei Folgen. **Erstens:** Jeder Entzug über `bc_leser` läuft ins Leere — belegt an
`ref_prozesse`, wo das Skript `bc_leser` korrekt entzog und `bc1_role` die Tabelle
danach weiterhin las (20 Zeilen). **Zweitens:** `ref_personen` enthält Klarnamen und
seit Schema v1.5 dienstliche E-Mail und Telefon, mandantenübergreifend und ohne den
Filter, den nur die Anwendung setzt.

**Nicht kurzerhand entzogen**, weil BC1s Interview-Bot den Gesprächspartner mit Namen
anspricht und BC0 die Stelle ist, die weiß, wer je Teilprozess zuständig ist. Offen ist
deshalb nicht *ob* eingegrenzt wird, sondern *worauf*: eine zugeschnittene Sicht
`v_personen_interview` oder eine ausdrückliche Freigabe mit Zweckangabe im ADR. Beides
verlangt von BC1 die Antwort auf eine Frage — welche Felder braucht der Bot?

`ref_prozesse` ist seit dem 23.08. geschlossen, für `bc_leser` **und** für `bc1_role`.

---

## 4. Bedrohungen und ihre Abdeckung

| Bedrohung | Abdeckung | Rest |
|---|---|---|
| Unbefugter Zugriff ohne Konto | Middleware, 401 als Vorgabe | — |
| Passwortdiebstahl aus der Datenbank | PBKDF2, 600 k, Salz je Passwort | Argon2id wäre robuster |
| Sitzungsübernahme aus der Datenbank | nur SHA-256-Abdruck gespeichert | — |
| Sitzungsübernahme über das Netz | HTTPS, `Secure`, `HttpOnly` | HSTS fehlt |
| Erraten von Passwörtern | Mindestlänge 12 | **keine Ratenbegrenzung** (3.1) |
| Zugriff über die Mandantengrenze | zwei Ebenen, 22 Tests | — |
| SQL-Einschleusung | durchgehend parametrisiert | — |
| XSS | `esc()`, 156 Verwendungen | **keine CSP** (3.2) |
| CSRF | `SameSite=Lax` | kein Token (3.3) |
| Rechteausweitung durch Selbst-Herabstufung | geprüft und verhindert | — |
| Schadhafter Datei-Upload | Größe, Name, UUID-Schlüssel | keine Virenprüfung, kein MIME-Abgleich |
| Denial of Service | Firewall | Anmeldemaske ist ein Hebel (3.1) |
| Innentäter | Rollentrennung in der DB | **kein Protokoll** (3.4) |
| Datenabfluss an Sprachmodelle | nur IDs nach außen (ADR-004), Sichtentest | Pseudonymisierung, nicht Anonymisierung |
| Klarnamen an nachgelagerte Kontexte | Sichten und Snapshot-Export geben nur IDs aus | **direkte Tabellenrechte umgehen beides (3.8)** |
| Lieferkettenangriff | 5 Python-Pakete, 0 npm-Pakete | keine automatische Prüfung auf bekannte Schwachstellen |

---

## 5. Bewertung

Nach dem Stand der Technik im Sinne von Art. 32 DSGVO — angemessene Maßnahmen
unter Berücksichtigung von Stand der Technik, Kosten, Art und Zweck der
Verarbeitung — ist der **Kern belastbar**: Anmeldepflicht als sichere Vorgabe,
zeitgemäße Passwortableitung, widerrufbare Sitzungen, doppelte
Mandantentrennung, durchgehend parametrisiertes SQL, und 51 von 130 Tests
prüfen genau diese Eigenschaften.

**Nicht belastbar sind vier Dinge**, und ich halte sie für die Bedingungen
einer Freigabe an externe Mandanten:

1. der fehlende Schutz gegen wiederholte Anmeldeversuche (3.1),
2. die fehlenden Sicherheitskopfzeilen (3.2) — eine Stunde Arbeit,
3. die direkten Tabellenrechte an `bc1_role` (3.8) — sie machen eine Zusicherung
   ungültig, die dieses Papier bis zum 23.08.2026 geführt hat,
4. der fehlende Nachweis nach DSGVO (3.7) — organisatorisch, nicht technisch.

Das fehlende Änderungsprotokoll (3.4) ist die Lücke, die mit dem Einsatzzweck
wächst: Für die Projektgruppe hinnehmbar, für einen Nachweis nach Art. 5 Abs. 2
DSGVO oder Art. 12 EU AI Act nicht.

**Was ich bewusst anders entschieden habe als ein Lehrbuch:** PBKDF2 statt
Argon2id (Abhängigkeitsfreiheit gegen Speicherhärte), serverseitige Sitzungen
statt JWT (Widerrufbarkeit gegen Zustandslosigkeit), zwei Rollen statt eines
Rechtemodells (Übungsmandant als Ersatz), kein ORM (das Schema ist die
Schnittstelle zwischen vier Teams). Jede dieser Entscheidungen hat einen Preis,
der oben benannt ist. Die erste würde ich bei einem Produktivsystem mit
Kundenzugängen umkehren.

---

*Grundlage: `bc0_auth/` (passwoerter.py, middleware.py, routen.py,
abhaengigkeiten.py), `app.py`, `Caddyfile`, `docker-compose.yml`, `AUTH.md`,
`ROLLEN.md`, ADR-003 bis ADR-005, Testsammlung `tests/`. Alle Zahlen am
19./20.08.2026 an der Arbeitskopie gemessen; der Rechtestand am 23.08.2026 an der
produktiven Datenbank nachgeprüft.*
