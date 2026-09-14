# BC0 — Architektur der Anwendung

**Projektgruppe KI-CoE-KMU · Bounded Context 0 (Baseline und Reifegrad)**
**Stand 19.08.2026 · Simeon Ehmer**

---

## 1. Einordnung

BC0 ist einer von fünf Bounded Contexts nach dem Domain-Driven-Design-Schnitt der Projektgruppe. Seine Aufgabe: die Baseline eines Mandanten erheben — Prozessstruktur, Rollen und Kostensätze, Personen- und Systemregister, den Bitkom-Reifegrad je Teilprozess — und sie den nachfolgenden Kontexten zur Verfügung stellen.

| Kontext | Aufgabe |
|---|---|
| **BC0** | Baseline und Reifegrad (dieses System) |
| BC1 | Interactive Context Discovery — vertieft die freigegebenen Prozesse im Interview |
| BC2 | Strategic Advisor — Wirtschaftlichkeit und Empfehlung |
| BC3 | Engineering und Architektur |
| BC4 | Autonomous Builder |

Zwischen BC0 und BC1 liegt ein Human-in-the-Loop-Schritt, das **Gate 0**.

---

## 2. Gesamtbild

```
Browser (PWA)
   │  fetch, JSON, Sitzungscookie
   ▼
Caddy  ── automatisches HTTPS (Let's Encrypt), Reverse-Proxy
   ▼
FastAPI / Uvicorn  ── Container "app"
   ├── AnmeldepflichtMiddleware        Boden: /api/* ohne Sitzung → 401
   ├── Depends(angemeldeter_benutzer)  Fachlogik: Mandantenfilter, Admin-Prüfung
   ├── app.py                          21 Endpunkte, Fachlogik, Berichtsrechnung
   └── bc0_auth/                       Anmeldung als eigenes Paket
          routen → dienst → repository → modelle
   ▼
_Cx  ── dünne Datenbankabstraktion, ein Platzhalterstil für beide Systeme
   ▼
PostgreSQL 17.6 (Supabase, eu-west-1)      SQLite (nur Entwicklung)
   ├── public   BC0, Single Source of Truth
   ├── bc1 … bc4  je Kontext ein Schema mit eigener Rolle
   └── Sichten   v_bewertung_aktuell, v_gate_*, v_reifegrad_*, …
```

Betrieb: Hetzner Cloud CX23, Nürnberg, Ubuntu 24.04, Docker Compose mit zwei Diensten (`app`, `caddy`) und drei benannten Volumes. Anwendung in Deutschland, Datenbank in der EU — **keine Drittlandsübermittlung im Betrieb**; der US-Mutterkonzern von Supabase ist über Auftragsverarbeitung und Standardvertragsklauseln abzudecken.

---

## 3. Die Oberfläche

**Eine Datei, 1.913 Zeilen, HTML und CSS und JavaScript zusammen. Kein Framework, keine Übersetzung, keine npm-Abhängigkeit.**

Das ist eine bewusste Entscheidung und die begründungsbedürftigste der ganzen Anwendung. Die Gründe:

- Die Anwendung soll **ohne Werkzeugkette lauffähig** sein. Wer die Datei öffnet, sieht den Quelltext, den der Browser ausführt — es gibt kein Übersetzat und keine Quellkarte dazwischen. Für ein Projekt, das über mehrere Semester von wechselnden Personen weitergeführt wird, ist das ein Vorteil, der schwerer wiegt als der Komfort eines Frameworks.
- **Keine Lieferkettenabhängigkeit.** Null npm-Pakete heißt: null Pakete, die kompromittiert werden können, und nichts, was in zwei Jahren nicht mehr baut.
- Der Umfang rechtfertigt kein Framework — es sind Formulare, Tabellen und SVG-Diagramme.

**Der Preis** ist ebenso klar zu benennen: keine Komponentengrenzen, keine Typprüfung, keine Oberflächentests, und eine Datei, die mit 1.913 Zeilen an der Grenze des Handhabbaren steht. Die Diagramme sind selbst gezeichnetes SVG (`spider()`, `cockpitSvg()`) — auch das eine Folge des Verzichts auf Bibliotheken.

**Struktur innerhalb der Datei:** Ansichten sind `<section class="view">` mit einer ID; `show(id)` schaltet um. Je Ansicht eine `render*`-Funktion, die ihren HTML-Baum als Zeichenkette baut und einhängt. Zustand liegt in wenigen Modulvariablen (`cur`, `META`, `RB`, `PD_SID`).

Eine Eigenheit, die aus einem Fehler entstand: `show()` prüft gegen `WS_ZIEL`, den zuletzt angeforderten Reiter. Ohne diese Sperre gewann der Renderer, der zufällig zuletzt fertig wurde — wer einen Reiter anklickte, während die Übersicht noch lud, landete wieder auf der Übersicht.

---

## 4. Die Anwendungsschicht

`app.py`, 2.896 Zeilen, 21 Endpunkte unter `/api/`. Aufbau in Abschnitten: Konfiguration und Konstanten (die 30 Bitkom-Items stehen fest im Quelltext), Datenbankabstraktion, Schemainitialisierung, Endpunkte nach Fachgebieten, Berichtsrechnung, Textgenerierung.

**Was daran nicht Stand der Technik ist:** Bei dieser Größe wäre eine Aufteilung in Module üblich — etwa `prozesse.py`, `bewertungen.py`, `gate.py`, `bericht.py`, jeweils als FastAPI-`APIRouter`. Die Datei ist durch Abschnittsüberschriften und ausführliche Kommentare navigierbar, aber sie wächst weiter. **Empfehlung: aufteilen, bevor sie 3.500 Zeilen erreicht.**

### Die Datenbankabstraktion

Die Klasse `_Cx` ist bewusst dünn — **kein ORM**. Sie vereinheitlicht nur zwei Dinge: den Platzhalterstil (`?` wird für PostgreSQL zu `%s`) und die Zeilenform (Mapping in beiden Systemen). Alles andere ist SQL im Quelltext.

Warum kein SQLAlchemy: Das Schema **ist** seit der SSoT-Entscheidung vom 06.08. die Schnittstelle zwischen den Bounded Contexts (ADR-003). Vier Teams lesen und schreiben dieselbe Datenbank; drei davon nicht aus dieser Anwendung heraus. Ein objektrelationaler Abbilder in BC0 würde eine Modellebene erzeugen, die für BC1 bis BC4 nicht existiert — die Wahrheit stünde dann an zwei Orten. Sichtbares SQL ist hier die ehrlichere Lösung.

Der Preis: 138 `execute`-Aufrufe mit handgeschriebenem SQL und zwei Dialektzweigen (`if PG: … else: …`). Die SQL-Dateien werden im Gegenzug in der Testsammlung mit `pglast` gegen den echten PostgreSQL-Parser geprüft.

### Die Anmeldung als eigenes Paket

`bc0_auth/` ist das einzige Stück der Anwendung, das durchgehend geschichtet ist:

| Modul | Zeilen | Aufgabe |
|---|---|---|
| `routen.py` | 257 | HTTP-Schicht, FastAPI-Router — kennt Anfragen und Antworten |
| `dienst.py` | 216 | Fachlogik — anmelden, Sitzung auflösen, sperren, Rolle wechseln |
| `repository.py` | 482 | Datenzugriff — das einzige Modul mit SQL |
| `modelle.py` | 149 | Datenklassen und Aufzählungen |
| `passwoerter.py` | 148 | Ableitungsverfahren, Prüfung, Schlüsselerzeugung |
| `middleware.py` | 95 | Anmeldepflicht als Netz unter der API |
| `abhaengigkeiten.py` | 127 | `Depends`-Funktionen |

Diese Trennung ist kein Selbstzweck: Sie macht die Sicherheitsschicht einzeln testbar, und 27 der 130 Tests prüfen genau dieses Paket.

### Ein Entwurfsmuster, das erwähnenswert ist

Die Anmeldepflicht liegt in einer **Middleware**, nicht in `Depends` an jedem Endpunkt. Der Grund steht im Quelltext und ist der bessere Teil des Entwurfs:

> Würde der Schutz allein an `Depends` hängen, wäre ein neuer Endpunkt so lange offen, bis jemand daran denkt — der Fehler wäre still und von außen nicht sichtbar. Diese Middleware dreht die Vorgabe um: Alles unter `/api/` verlangt eine Anmeldung, es sei denn, der Pfad steht ausdrücklich in `OFFENE_PFADE`. Eine vergessene Absicherung führt damit nicht zu einem offenen Endpunkt, sondern zu einem, der 401 meldet — ein Fehler, der sofort auffällt.

`Depends` bleibt daneben in Gebrauch, aber für die Fachlogik: Mandantenfilter und Administratorprüfung. Die Middleware ist der Boden, `Depends` die Fachlogik.

---

## 5. Datenmodell und Schemaentwicklung

**Kern:** `companies` → `ref_prozesse` (zehn Kernprozesse) → `ref_teilprozesse` (fünf je Kernprozess) → `bitkom_bewertungen` (30 Items je Teilprozess). Dazu die Register `ref_personen`, `mandant_systeme`, `mandant_rollen` mit stabilen IDs nach ADR-004, die Verflechtung in `prozess_schnittstellen`, und die Freigabe in `gate_ereignisse`.

**Identität:** Jede benannte Entität trägt neben dem Klarnamen eine stabile ID — `P-01` für Personen, `S-03` für Systeme, `KP-02.TP-3` für Teilprozesse, `E-2026-05` für Erhebungen. Nach außen und an Sprachmodelle geht nur die ID (ADR-004). Der Klarname bleibt in der Datenbank; das ist Pseudonymisierung, nicht Anonymisierung, und im Papier ausdrücklich so benannt.

**Mehrfacherhebungen:** Bewertungen hängen an einer Erhebung. Der maßgebliche Stand ist nicht die jüngste Erhebung, sondern eine **Zusammensetzung**: je Teilprozess und Item die Zeile aus der neuesten nicht verworfenen Erhebung, die sie überhaupt enthält. Wird im September nur ein Teil nacherhoben, behalten die übrigen Prozesse ihre Maiwerte. Umgesetzt als Fensterfunktion in `v_bewertung_aktuell`; in `app.py` steht dieselbe Unterabfrage noch einmal, damit der SQLite-Entwicklungsmodus sie hat.

Dieser Punkt ist der Grund für einen behobenen Bestandsfehler: `company_progress()` zählte über *alle* je geschriebenen Zeilen statt über den maßgeblichen Stand und meldete auf der Testkopie 1.650 statt 1.500 Bewertungen.

**Schemaentwicklung:** Additive Skripte v1.1 bis v2.0, jedes wiederholbar (`IF NOT EXISTS`, `ON CONFLICT DO NOTHING`), jedes mit Gegenproben am Dateiende, die die erwarteten Werte nennen. Es gibt kein Migrationswerkzeug wie Alembic — bei einer Datenbank, in die vier Teams schreiben, ist ein nachvollziehbares SQL-Skript pro Änderung die transparentere Lösung.

**Rechtetrennung auf Datenbankebene:** Je Kontext eine Rolle (`bc1_role` bis `bc4_role`) und ein Schema (`bc1` bis `bc4`), dazu die Gruppenrolle `bc_leser`. Jeder liest alles, schreibt nur im eigenen Schema, **niemand schreibt in `public`**. Die Trennung liegt damit nicht in der Anwendung, sondern in der Datenbank — sie gilt auch für Zugriffe, die an BC0 vorbeigehen.

---

## 6. Die Berichtsschicht

Der Reifegradbericht ist kein Ausdruck der Oberfläche, sondern ein eigenes Erzeugnis mit zwei Textquellen:

**Feste Bausteine** liegen in `ref_berichtstexte` mit Version und Gültigkeitsdatum, nicht im Quelltext. Grund: Ein Bericht ist erst reproduzierbar, wenn auch der erklärende Satz reproduzierbar ist. Steht der Text im Quelltext, ändert er sich mit jedem Deployment unbemerkt mit.

**Befundsätze** werden regelbasiert aus den Zahlen erzeugt — Satzschablonen mit Schwellwerten, **kein Sprachmodell**. Zweimal derselbe Bericht ergäbe sonst zwei verschiedene Texte. Bei Gleichstand entscheidet immer die ID, nie die Reihenfolge, in der die Datenbank Zeilen liefert.

Der Bericht weist zwei Prüfsummen aus: die **Textfassung** über alle aktiven Bausteine und die **Regelfassung** über den Quelltext der Generatorfunktionen samt der Konstanten, an denen sie hängen. Letztere ist bewusst nicht von Hand gepflegt — wer eine Zeile ändert, ändert die Kennung, ohne daran zu denken.

Nachgeprüft: Zweimaliger Abruf auf demselben Datenstand ergibt den vollständigen Report identisch, einzige Abweichung ist das Ausgabedatum.

---

## 7. Was bewusst nicht gebaut wurde

| Verzicht | Begründung |
|---|---|
| Frontend-Framework | keine Werkzeugkette, keine Lieferkettenabhängigkeit, Umfang rechtfertigt es nicht |
| ORM | das Schema ist die Schnittstelle zwischen vier Teams — eine Modellebene in BC0 wäre eine zweite Wahrheit |
| Migrationswerkzeug | nachvollziehbare SQL-Skripte mit Gegenproben statt generierter Migrationen |
| Sprachmodell im Bericht | Reproduzierbarkeit; ein Modell erzeugt zweimal verschiedenen Text |
| Zusätzliche Auth-Bibliothek | PBKDF2 liegt in der Standardbibliothek; bcrypt hätte eine kompilierte Erweiterung im Container bedeutet |
| Nur-Lesen-Rolle | bewusst nicht gebaut — stattdessen ein Übungsmandant, siehe Sicherheitspapier |

---

## 8. Bekannte Schwächen

1. **`app.py` ist ein Monolith** — 2.896 Zeilen. Aufteilen, bevor 3.500 erreicht sind.
2. **`static/index.html` ebenso** — 1.913 Zeilen, ohne Typprüfung und ohne Oberflächentests.
3. **Zwei Dialektzweige** in jedem datenbanknahen Abschnitt. Der SQLite-Modus dient nur der Entwicklung; er hat schon zweimal einen Fehler verdeckt, der erst im PostgreSQL-Lauf auffiel (in den Tests jeweils vermerkt).
4. **Kein Änderungsprotokoll.** `audit_log` ist seit dem 22.06. angelegt und leer.
5. **Keine Abdeckungsmessung der Tests.**

---

*Grundlage: ADR-001 bis ADR-005, `ROLLEN.md`, `AUTH.md`, `MIGRATION.md`, Datenbankdokumentation v1.3. Alle Zahlen am 19.08.2026 an der Arbeitskopie gemessen.*
