# BC2 — Strategic Advisor · Guidance

> Für Claude Code **und** Menschen.

## Was BC2 ist

Erkennt aus BC0s Baseline **Automatisierungspotenziale**, bewertet ihren **Value**, priorisiert sie
und erzeugt eine entscheidungsreife Präsentation plus einen maschinenlesbaren Vertrag für BC3.
Zwischen Gate 0 und Gate 1. Verantwortlich: **Sergio, allein** — Eike ist seit dem 30.08.2026 raus.

**Stand (09.10.2026):** Vier Teile stehen. Der **Trigger-Endpunkt** (`app/app.py`, `app/eingang.py`)
läuft im Betrieb und nimmt BC0s Pakete an ([#190](https://github.com/pg-coe-kmu/coe-factory/issues/190),
[#205](https://github.com/pg-coe-kmu/coe-factory/issues/205)); das **Value- und Priorisierungsmodell**
(`app/modell/`) rechnet nach ADR-006 · BC2 ([#238](https://github.com/pg-coe-kmu/coe-factory/issues/238)),
seit [#288](https://github.com/pg-coe-kmu/coe-factory/issues/288) mit Messungen **je berührtem
Teilprozess** (Nachtrag 4 und 5); der **Erkennungsschritt** (`app/erkennung/`) schneidet die
Potenziale — ein Modellaufruf je Paket, deterministisch nachkontrolliert
([#194](https://github.com/pg-coe-kmu/coe-factory/issues/194) entschieden,
[#248](https://github.com/pg-coe-kmu/coe-factory/issues/248) gebaut). Dort liegt auch das Lesen auf
`stand_zum(uebergeben_am)`. Der **Bewertungsschritt** (`app/bewertung/`) urteilt Lage im Korridor,
Nutzwert, Überschreiben der Komplexität und den Umsetzungsaufwand — ein Aufruf je Lauf, bewacht,
**dreimal gestellt, je Feld der Median** ([#260](https://github.com/pg-coe-kmu/coe-factory/issues/260)
entschieden, #288 gebaut, [#299](https://github.com/pg-coe-kmu/coe-factory/issues/299) stabil gemacht). Die
**Gate-1-Oberfläche** (`app/static/index.html`, `app/oberflaeche.py`)
zeigt einen Lauf und nimmt die Freigabe entgegen ([#243](https://github.com/pg-coe-kmu/coe-factory/issues/243));
nach der Freigabe zeichnet `app/praesentation/` den Foliensatz als PPTX ([#257](https://github.com/pg-coe-kmu/coe-factory/issues/257),
entschieden in #244). **Schema `bc2`** trägt seit [#290](https://github.com/pg-coe-kmu/coe-factory/issues/290) Lauf,
Konzepte, Potenziale und die Gate-1-Entscheidung (`app/ablage.py`, `app/gate1.py`,
`app/migration_bc2.2_lauf.sql`; Entwurf ADR-008 · BC2, [#250](https://github.com/pg-coe-kmu/coe-factory/issues/250)).
Seit [#295](https://github.com/pg-coe-kmu/coe-factory/issues/295) **verknüpft** ein Lauf Potenziale
über Pakete hinweg (ADR-009 · BC2, Nachtrag 1): die Ablage liest die geltenden gelieferten
Potenziale über die Teilprozesse des Pakets, die Erkennung ordnet sie zu (fortgeschrieben,
gestrichen, unverändert), `app/nachfolge.py` prüft nach, und die Gate-1-Ansicht zeigt Vorgänger und
Streichliste. Seit [#301](https://github.com/pg-coe-kmu/coe-factory/issues/301) schreibt der
**Ausarbeitungsschritt** (`app/ausarbeitung/`, ADR-010 · BC2) **nach** der Rechnung die Texte der
Konzepte — ein Aufruf je Konzept, parallel, bewacht —, und Python setzt sie mit dem Gerechneten,
den Eingangswerten und der Ausgangslage zusammen. **Der echte Weg legt damit einen schemagültigen
Vertrag 3.1 ab** und trägt die Kette über Pakete.

⚠ **Die Oberfläche ist noch nicht betriebsfest**, und sie sagt das selbst an. Ihre Voreinstellung ist
weiter der **Messsatz**: der echte Weg — angenommenes Paket → Erkennung → Bewertung → Rechenkern →
Ausarbeitung (`laeufe.PaketLaufquelle`) — ist gebaut, aber ein **Schalter** (`BC2_LAUFQUELLE=pakete`), weil
keiner seiner Außenwege beim Bau gefahren werden konnte (lokal keine `DATABASE_URL`, `SdkModell`
nie gegen die API). Wer ihn umlegt, fährt den ersten echten Lauf (#206). Die Stabilitätsabnahme des Bewertungsschritts
ist seit #299 bestanden — als **Median aus drei Urteilen**, und genau auf der Grenze (95,0 % der
Paare). Beim ersten echten Lauf ist die Zehnermessung zu wiederholen
(`tools/bewertung_messen.py --n 10`, ADR-006 · BC2, 6.7); fällt sie unter 95 %, wird `URTEILE = 5`. **Die Entscheidung liegt seit #290 in Schema `bc2`**,
sobald `DATABASE_URL` gesetzt ist; ohne sie im Arbeitsspeicher, und die Oberfläche sagt das an. Die
`AblegendeLaufquelle` umhüllt die innere Quelle: gerechnet wird einmal, gezeigt wird danach das
abgelegte Dokument. Der Schalter tauscht nur die innere Quelle, nicht die Ablage — `PaketLaufquelle`
ist darum **zustandslos**, damit `neu_rechnen` nach einem Reject wirklich neu schneidet.

**Invarianten aus #290:** eine Fassung ist ein Lauf über dasselbe Paket, angestoßen von BC2 und nur
nach `rejected`; Gate 1 ist nach `approved`/`rejected` endgültig (`409`, kein Überschreiben); das
Ergebnis eines Laufs ist nach dem Schreiben unveränderlich. Alle drei setzt die **Datenbank** durch
(UNIQUE, partieller Index, Trigger) — ein grüner Doppelgängertest beweist sie nicht.
Owner-Angaben in den Alt-Issues (#84–#99) nennen teils Eike und sind damit hinfällig.
*(Korrigiert am 20.09.2026: die Vorgängerfassung sagte „Es gibt noch keinen BC2-Code. Der Bau
beginnt bei null" — ein Stand vom 30.08., der schon durch #190 überholt war.)*

## Erst lesen

- **[`CONTEXT.md`](./CONTEXT.md)** — das Glossar. Was Potenzial, Value, Nutzwert, Impact, Kategorie
  und Analyselauf bedeuten und wer sie setzt. Die Begriffe waren quer durch die Quellen unscharf;
  seit [#164](https://github.com/pg-coe-kmu/coe-factory/issues/164) stehen sie. Wer hier ein Wort
  anders verwendet als dort, hat entweder das Glossar zu ändern oder das Wort.
- **[Karte #158](https://github.com/pg-coe-kmu/coe-factory/issues/158)** — Ziel, getroffene Entscheidungen,
  Nebel. Wird pro Session einmal geladen. Die offenen Tickets sind ihre Sub-Issues; das nächste
  bearbeitbare ist das erste ohne offenen Blocker und ohne Assignee.
- **[Datenlage, Kommentar an #159](https://github.com/pg-coe-kmu/coe-factory/issues/159)** — was am
  30.08.2026 **gemessen** in der Datenbank lag. Maßgeblich gegenüber jedem Papier.

Arbeitsweise: ein Ticket je Session, Claim vor Arbeit (`gh issue edit <n> --add-assignee @me`),
Ergebnis als Kommentar, schließen, Zeiger an die Karte anhängen. Ein Issue = ein Branch = kleiner PR.

## Datenzugang

Gemeinsame PostgreSQL 17.6 bei Supabase (eu-west-1), **Session-Pooler Port 5432** — der
Transaction-Pooler auf 6543 hält keine Sitzung über die Anweisung hinaus.

```
host  aws-0-eu-west-1.pooler.supabase.com   port 5432   dbname postgres
user  bc2_role.<PROJEKTKENNUNG>             sslmode require
```

Kennung und Passwort stammen von Simeon (BC0), verteilt per SMS. Sie gehören **ausschließlich in
Umgebungsvariablen** — nicht in Repo, Issue, Code oder Kommentar (BC0-Regel 5).

Gegenprobe nach jedem Verbindungsaufbau: `current_user` liefert `bc2_role`, und ein `UPDATE` auf
`bitkom_bewertungen` scheitert mit `permission denied`. Scheitert es nicht, erst melden, dann weiterarbeiten.

## Was in den Altdokumenten überholt ist

Die BC2-Unterlagen sind über fünf Stände gewachsen und widersprechen sich. Maßgeblich ist die
Datenbank, danach die Karte. Diese Tabelle bewahrt davor, alte Schlüsse erneut zu ziehen:

| Aussage in Altdokumenten | Tatsächlich |
|---|---|
| Qdrant + fester Musterkatalog (Issues #84–#99, Vorbereitungsaufgabe) | verworfen — Potenziale werden offen erkannt |
| `use_cases[]` mit `empfohlenes_muster` (Schema v1.0) | `potenziale[]` (Schema **v3.0** seit 20.09.2026, #187) |
| vier Stufen `gering`…`sehr hoch` für Impact und Komplexität | **1–10**; `manueller_aufwand_heute` ist gar kein Urteil mehr, sondern gemessene Jahresstunden |
| `gate1` steht im Konzept | `gate1` steht in der **Priorisierung**, je Lauf (ADR-007 · BC2) |
| n8n als Orchestrierung | reines Python, Agenten selbst gebaut |
| Übergabe per JSON-Datei, GitHub-Ordner oder REST | gemeinsame Datenbank, Schema-Trennung (ADR-003) |
| „Rollen und Kostensätze sind leer" (BC0-Papier 23.08.) | gefüllt seit 17.08.: K1–K5, 40–140 EUR/h, alle `geschaetzt` |
| „4 Kernprozesse bewertet, 600 Bewertungen" | 6 Kernprozesse, 690 Bewertungen für NoroAI |
| Sprints S1–S6, Meilensteine M1–M4, KW 20–31 | Zeitpläne gelten nicht mehr |

`contracts/examples/mock_prozessprofil.json` beschreibt „Krankentagegeld, KP-07, Aurelia Krankenkasse".
Real ist KP-07 die Buchhaltung und nicht erhoben; NoroAI ist eine KI-Beratung. Der Mock dient als
**Schema-Fixture**; die fachliche Grundlage ist die Datenbank. *(Die Ausgabe-Fixtures tragen seit
v3.0 echten NoroAI-Inhalt aus BC3s Formatvorlage — der erfundene Fall liegt nur noch in
`contracts/examples/archiv-v2/`. Ihn auf v3.0 zu heben hätte geheißen, für einen erfundenen Prozess
Nutzwerte, Querschnitte und Eingangswerte zu erfinden.)*

## Wo BC2 liegt

Seit [#162](https://github.com/pg-coe-kmu/coe-factory/issues/162) an genau einem Ort — die drei
divergierenden Kopien unter `Projektgruppe/BC2/` sind aufgelöst und liegen dort nur noch in `_archiv/`.

| Was | Wo |
|---|---|
| Verträge an BC3 (**v3.1**, additiv seit #254 und #291; BC3-Bestätigung offen) | `contracts/bc2-to-bc3/` — **Endlage, wird nicht mehr verschoben**; `archiv/` hält v2.0 für die Lieferung vom 30.08. |
| Mocks / Fixtures | `contracts/examples/` |
| `migriere_bc3_vorlage.py`, `validate.py`, `kalibrierung.py` | `bc2-strategic-advisor/tools/` — aus dem Repo-Wurzelverzeichnis aufrufen |
| Systemarchitektur (27.06., teils überholt) | `bc2-strategic-advisor/architektur/` |
| Trigger-Endpunkt (läuft im Betrieb) | `bc2-strategic-advisor/app/app.py`, `app/eingang.py` |
| **Value- und Priorisierungsmodell** (ADR-006 · BC2) | `bc2-strategic-advisor/app/modell/` — `parameter.py` (Setzungen), `rechnen.py` (reiner Kern), `ausgabe.py` (Vertragsform, seit v3.1 auch die Ausgangslage des Laufs), `laden.py` (Messsatz lesen) |
| **Erkennungsschritt** (#194 / #248) | `bc2-strategic-advisor/app/erkennung/` — `bestand.py` (Leseseite), `nutzlast.py` (was das Modell sieht), `anweisung.py`, `modellruf.py` (Naht zum LLM), `pruefen.py` (Nachkontrolle) |
| **Bewertungsschritt** (#260 / #288) | `bc2-strategic-advisor/app/bewertung/` — `nutzlast.py` (ohne Stunden, Euro, Dauern; BC1-Profil → `Schrittmessung`), `anweisung.py`, `pruefen.py` (Wächter 6.5), `bewerten.py` |
| **Nutzwert-Anker** (Nachtrag 6) | `app/modell/parameter.py`, `nutzwert_anker` — Setzung, am ersten echten Lauf mitzuprüfen |
| **Ausarbeitungsschritt** (ADR-010 · BC2, #301) | `bc2-strategic-advisor/app/ausarbeitung/` — `nutzlast.py` (je Konzept, ohne Zahl aus der Rechnung), `anweisung.py` (zwei Platzhalter `{grad_min}`/`{grad_max}`), `pruefen.py` (Wächter: Schablonen, Systeme aus Bestand oder Tech-Stack, Rechenverbot), `ausarbeiten.py` (Ablauf und Zusammensetzen) |
| Ausarbeitung an echten Aufrufen messen (#301) | `bc2-strategic-advisor/tools/ausarbeitung_messen.py` — `--von /tmp/bewertung-299` nimmt Erkennung und Urteile einer früheren Erhebung |
| **Nachfolger über Pakete** (ADR-009 · BC2, #295) | `app/nachfolge.py` (Kandidat, Ausgang, Nachprüfung — rein), Kandidatensuche in `app/ablage.py`, Zuordnung im Wächter von `app/erkennung/` |
| **Gate-1-Oberfläche** (Fassung D, #167/#243) | `app/static/index.html` (eine Datei), `app/oberflaeche.py` (die Rufe), `app/gate1.py` (Entscheidung, Prüfung, Ablage), `app/laeufe.py` (Laufquelle) |
| **Präsentation** (#244 entschieden, #257 gebaut) | `app/praesentation/` — `folien.py` (reine Funktion: Konzepte + Priorisierung → PPTX), `formulierung.py` (wie Zahlen auf die Folie kommen), `zeichnen.py` (KIsult-Palette), `ablage.py` (Bytes für den Download — abgelegt wird sie seit #306 nicht mehr); das alte Template liegt in `architektur/archiv/` |
| **Lieferung an BC3** (#305 entschieden, #306 gebaut) | `app/lieferung.py` (welche Läufe geliefert sind: freigegeben **und** ohne Sperrgrund; `python -m lieferung` im Container, nur lesend) und `tools/lieferung_ziehen.py` (lokal: zieht über `ssh bc2`, ordnet nach Schema, schreibt neue Ordner, bricht bei Abweichung ab). Ablauf in `app/DEPLOY.md` |
| Oberfläche ansehen, ohne Datenbank | lokal `app/vorschau.py` — `python3 vorschau.py`, dann `http://127.0.0.1:8243/`; im Betrieb `https://bc2.02da.de/vorschau/` (eigener Container ohne Geheimnisse, Schlüssel `BC2_VORSCHAU_SCHLUESSEL`) |
| Messsätze für die Kalibrierung | `bc2-strategic-advisor/kalibrierung/` |
| Erkennung an einem echten Aufruf messen | `bc2-strategic-advisor/tools/erkennung_messen.py` |
| Bewertung messen, mit Stabilitätsprobe (#288) | `bc2-strategic-advisor/tools/bewertung_messen.py` |

Der Vertrag verlor beim Sprung v1→v2 die Felder `akzeptanzkriterien_geschaeftlich`,
`fachliche_anforderungen` und die Tiefe von `to_be_vision`. ✅ **Zurück seit v3.0**
([#187](https://github.com/pg-coe-kmu/coe-factory/issues/187), 20.09.2026) — in der Form aus BC3s
Vorlage vom 31.08.2026, dazu `user_story` (SOPHIST) und `messverfahren` je Kriterium, die BC2
verantwortet.

## Invarianten

- **Lesen** auf `public` und `bc1`…`bc4`, **schreiben ausschließlich in Schema `bc2`.** Die Datenbank
  setzt das durch (ADR-003).
- **Jede Ausgabe führt die Kernprozess-ID mit.** Ohne sie ist ein Ergebnis nicht zuordenbar und
  wird verworfen (Auflage BC0, 17.08.2026).
- **Ein Lauf ist ein Paket, kein Mandant.** Die Einheit ist `(company_id, paket_id)` — nur dafür gibt
  es einen reproduzierbaren Datenstand (`stand_zum(…, uebergeben_am)`) und einen einheitlichen
  Freigabestand. ADR-005, [#164](https://github.com/pg-coe-kmu/coe-factory/issues/164). *(Verengt die
  Festlegung vom 30.08.2026, die den Mandanten als Arbeitseinheit nannte — sie entstand, bevor es das
  Paket gab.)*
- **Gelesen wird auf Teilprozess-Ebene, ausgeliefert auf Kernprozess-Ebene.** Paketinhalt, Gate-0-
  Freigabe und `v_prozessautomatisierung` sind je `sub_process_id`; ein Konzept deckt genau einen
  Kernprozess ab. Der Kernprozess ist das Präfix der Teilprozess-ID, nicht eine eigene Erhebung.
- **Jede Abfrage filtert nach `company_id`.** Es liegen zwei Mandanten in derselben Datenbank, und die
  Datenbank trennt sie nicht. NoroAI ist `7c2d5ee9-2a9a-5990-810f-502ea2b2012d`; der zweite Mandant
  ist ein Übungsmandant und trägt keine auswertbaren Werte.
- **`v_bewertung_aktuell` statt `bitkom_bewertungen`** für jede Auswertung — sonst fließen
  überschriebene Stände mit ein.
- **Eine fehlende Bewertung ist eine Lücke, keine Null — und die Regel greift beim _Lesen_.**
  `erkennung.Teilprozess.bewertet` fragt nach dem **Vorhandensein**, nie nach `avg > 0`. Wer eine
  0 als Note liest, hält den unerhobenen Teilprozess für den am schlechtesten automatisierbaren
  im Bestand — dieselbe Falle wie `v_gate_prozessstand.tp_mit_medienbruch` (#163), dieselbe Regel
  wie #167. *(Auflage 4 aus [#248](https://github.com/pg-coe-kmu/coe-factory/issues/248).)*
  **Wo die Null herkommt, ist am 21.09.2026 berichtigt worden** ([#249](https://github.com/pg-coe-kmu/coe-factory/issues/249)):
  nicht aus der Datenbank. `v_prozessautomatisierung` hat 23 Zeilen und keine einzige Null — ein
  `GROUP BY` über Bewertungen kann keinen unbewerteten Teilprozess erzeugen. Die »27 von 50 mit
  `avg: 0`« aus #194 sind ein **Artefakt des Snapshot-Exports**. Die Lücke besteht trotzdem
  (27 von 50 sind unbewertet), und weil BC2s Fixtures auf dem Snapshot laufen, wiegt die Regel
  dort **schwerer** als im Produktionsweg, nicht leichter.
- **Die fünf Lösungsklassen werden wörtlich geschrieben** — `Regelwerk/Weiterleitung`,
  `Integration`, `Extraktion`, `Textgenerierung`, `Assistenz`. An ihnen hängt der Korridor des
  Automatisierungsgrads; eine andere Schreibweise hat keinen. Der Prototyp zu #194 bot dem Modell
  fünf **andere** an, und 10 von 10 seiner Potenziale wären am Vertrag gescheitert. Wer eine Liste
  dieser Namen braucht, liest sie aus `modell.parameter.STANDARD.korridore` statt sie zu wiederholen.
- **Das LLM bewertet qualitativ, rechnet aber nicht.** Zahlen entstehen deterministisch in Python,
  damit sie reproduzierbar und testbar bleiben. Es urteilt an **genau fünf** Stellen (ADR-006 · BC2,
  2.0 und Nachtrag 7): Lösungsansatz-Klasse, Lage im Korridor, die fünf Nutzwert-Kategorien, das
  begründete Überschreiben der Umsetzungskomplexität und der Umsetzungsaufwand in Personentagen.
  Urteile mit Zahl stehen in **Zahlenfeldern**; in Begründungstexten steht keine Zahl mit Einheit.
  Die **Konzepttexte** des Ausarbeitungsschritts sind Darstellung, kein Urteil, das rechnet, und
  tragen ebenfalls keine Zahl mit Einheit — mit genau zwei Platzhaltern, `{grad_min}` und
  `{grad_max}`, in die Python den gerechneten Automatisierungsgrad einsetzt (ADR-010 · BC2, 2.4).
- **Gemessen wird je berührtem Teilprozess, nicht je Potenzial** (ADR-006 · BC2, Nachtrag 4/5).
  Jahresstunden = Σ `(step_frequency_per_year ?? frequency_per_year) × focus_step_duration_minutes / 60`,
  Herkunft die schwächste, Komplexität das Maximum. `total_duration_minutes` beschreibt den ganzen
  Prozess (BC1-Vertrag I1) und geht **nicht** ein — `modell.Schrittmessung` kennt das Feld darum
  nicht. Fehlt einem berührten Teilprozess das Profil, gibt es **keine** Value-Zahl, keine Teilsumme.
- **`executions_per_run` ist KEIN Multiplikator** (Invariante I2 des BC1-Vertrags,
  [#184](https://github.com/pg-coe-kmu/coe-factory/issues/184)). Dauern gelten **je
  Prozessdurchlauf**; die Fallzahl multipliziert sie nicht. Wer es doch tut, erhält für die
  Reisebuchung ein Vielfaches der Gesamtkapazität eines Zehn-Personen-Betriebs, für *einen* Schritt.
  `modell.Potenzialeingang` kennt das Feld darum gar nicht.
- **Jede Annahme reist mit dem Ergebnis.** Stundensätze sind `geschaetzt`, Aufwandsgrößen fehlen
  teils ganz — die Ausgabe macht das sichtbar, statt Genauigkeit vorzutäuschen.
- **Es gilt die Checklisten-Skala** — `1 = 0–10 %` · `2 = >10–40 %` · `3 = >40–60 %` ·
  `4 = >60–90 %` · `5 = >90 %`. Von BC0 am 10.09.2026 an **allen 24 Bewertungsblättern zu
  KP-01…KP-04** nachgeprüft: die Bewerter hatten diese Kopfzeile vor sich, die Bänder des
  Leitfadens stehen in keinem Blatt. Erhoben und gerechnet wird damit auf derselben Skala.
  *(Korrigiert am 10.09.2026, [#171](https://github.com/pg-coe-kmu/coe-factory/issues/171). Die
  Vorgängerfassung führte die **Leitfaden**-Bänder als Invariante — 1 = 0 %, 2 = >0–40 %,
  3 = >40–50 %, 4 = >50–95 %, 5 = >95 % — und damit die falschen Grenzen.)*
  **Achtung, die alte Merkregel gilt nicht mehr:** dort war der Sprung 3→4 der größte im Modell.
  Bei den Checklisten-Bändern liegen die Bandmitten bei 5 / 25 / 50 / 75 / 95 %, also nahezu
  gleichmäßig. Was daraus für die Übersetzung in Nutzen folgt, entscheidet
  [#166](https://github.com/pg-coe-kmu/coe-factory/issues/166) — hier steht nur die Skala,
  nicht die Rechenregel.

## Stack & Sprache

Python 3.11+, FastAPI, `pytest`. Sprache durchgehend **Deutsch**, auch in Issues und Commits.

Tests sprechen die Anwendung über HTTP an (`fastapi.testclient.TestClient`), nicht über
Endpunktfunktionen — Vorbild ist `bc0-baseline-onboarding/app/tests/` samt
`TESTABDECKUNG.md`. Deren Lehre gilt auch hier: ein grüner Lauf gegen Fixtures ersetzt den Durchlauf
gegen das echte PostgreSQL nicht.

Die allgemeinen Coding-Prinzipien des Projekts stehen in `bc1-context-discovery/CLAUDE.md`
(Abschnitt „Sauber codieren") und gelten sinngemäß auch für BC2.
