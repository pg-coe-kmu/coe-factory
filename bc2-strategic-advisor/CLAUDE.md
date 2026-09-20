# BC2 — Strategic Advisor · Guidance

> Für Claude Code **und** Menschen.

## Was BC2 ist

Erkennt aus BC0s Baseline **Automatisierungspotenziale**, bewertet ihren **Value**, priorisiert sie
und erzeugt eine entscheidungsreife Präsentation plus einen maschinenlesbaren Vertrag für BC3.
Zwischen Gate 0 und Gate 1. Verantwortlich: **Sergio, allein** — Eike ist seit dem 30.08.2026 raus.

**Stand (21.09.2026):** Drei Teile stehen. Der **Trigger-Endpunkt** (`app/app.py`, `app/eingang.py`)
läuft im Betrieb und nimmt BC0s Pakete an ([#190](https://github.com/pg-coe-kmu/coe-factory/issues/190),
[#205](https://github.com/pg-coe-kmu/coe-factory/issues/205)); das **Value- und Priorisierungsmodell**
(`app/modell/`) rechnet nach ADR-006 · BC2 ([#238](https://github.com/pg-coe-kmu/coe-factory/issues/238));
die **Gate-1-Oberfläche** (`app/static/index.html`, `app/oberflaeche.py`) zeigt einen Lauf und nimmt
die Freigabe entgegen ([#243](https://github.com/pg-coe-kmu/coe-factory/issues/243)).
Offen sind Potenzial-Erkennung ([#194](https://github.com/pg-coe-kmu/coe-factory/issues/194) — dort
liegt auch das Lesen auf `stand_zum(uebergeben_am)`), Präsentation
([#244](https://github.com/pg-coe-kmu/coe-factory/issues/244)) und der **Tabellenentwurf für Schema
`bc2`** ([#250](https://github.com/pg-coe-kmu/coe-factory/issues/250)).

⚠ **Die Oberfläche ist noch nicht betriebsfest**, und sie sagt das selbst an: ihre Läufe kommen aus
einem Messsatz statt aus der Datenbank (das ist #194), und ihre Entscheidung liegt im
**Arbeitsspeicher**, weil Schema `bc2` dafür keinen Ort hat (das ist #250). Beides hängt hinter je
einem Protokoll — `Laufquelle` und `Gate1Buch` —, die Umsetzungen werden getauscht, nicht die
Oberfläche.
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
| Verträge an BC3 (**v3.0**) | `contracts/bc2-to-bc3/` — **Endlage, wird nicht mehr verschoben**; `archiv/` hält v2.0 für die Lieferung vom 30.08. |
| Mocks / Fixtures | `contracts/examples/` |
| `migriere_bc3_vorlage.py`, `validate.py`, `kalibrierung.py` | `bc2-strategic-advisor/tools/` — aus dem Repo-Wurzelverzeichnis aufrufen |
| Systemarchitektur (27.06., teils überholt) | `bc2-strategic-advisor/architektur/` |
| Trigger-Endpunkt (läuft im Betrieb) | `bc2-strategic-advisor/app/app.py`, `app/eingang.py` |
| **Value- und Priorisierungsmodell** (ADR-006 · BC2) | `bc2-strategic-advisor/app/modell/` — `parameter.py` (Setzungen), `rechnen.py` (reiner Kern), `ausgabe.py` (Vertragsform), `laden.py` (Messsatz lesen) |
| **Gate-1-Oberfläche** (Fassung D, #167/#243) | `app/static/index.html` (eine Datei), `app/oberflaeche.py` (die vier Rufe), `app/gate1.py` (Entscheidung, Prüfung, Ablage), `app/laeufe.py` (Laufquelle) |
| Oberfläche ansehen, ohne Datenbank | `app/vorschau.py` — `python3 vorschau.py`, dann `http://127.0.0.1:8243/` |
| Messsätze für die Kalibrierung | `bc2-strategic-advisor/kalibrierung/` |

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
- **Das LLM bewertet qualitativ, rechnet aber nicht.** Zahlen entstehen deterministisch in Python,
  damit sie reproduzierbar und testbar bleiben. Es urteilt an **genau vier** Stellen (ADR-006 · BC2,
  2.0): Lösungsansatz-Klasse, Lage im Korridor, die fünf Nutzwert-Kategorien und das begründete
  Überschreiben der Umsetzungskomplexität.
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
