# Die Datenbank entlang des Ablaufs — acht Stationen, ihre IDs und ihre Abhängigkeiten

**BC0 · Simeon Ehmer · Stand 04.09.2026 (nachts, fünfte Fassung — Abschnitt 12: Übergabe nur vollständig, v2.7)**
**Ergänzt** `BC0_DB_Abhaengigkeiten_03-09-2026.html` (Anker, Rückführung, Ehen) und
`BC0_Rueckschreib_ID_03-09-2026.html` (die Ursprungs-ID) um die **zeitliche** Sicht: Was entsteht
wann, wer vergibt die ID, und woran hängt der nächste Schritt.

> **Geprüft gegen:** die Schemadateien `v1.1.1` bis `v2.5` und `app.py` im Klon `coe-factory`
> (Stand `c0dfb06`, 03.09.2026), `ROLLEN.md`, die Datenbankdokumentation v1.7, die Ausrollblätter
> vom 27.08. bis 03.09., das Drehbuch bis S-106 und beide ToDo-Fassungen. **Nicht** gegen die
> produktive Datenbank abgefragt — was auf dem Server läuft, ist der Stand des Ausrollblatts
> Trichter 3 (03.09., `app.py` 227.702 Bytes); der Klon ist seither um die Anmeldebremse weiter.
>
> **Zweite Fassung.** Die erste vom selben Abend war ohne Klon geschrieben und an vier Stellen
> falsch oder überholt: Der Erhebungs-Endpunkt existiert (Abschnitt 1), die Endpunkte für
> Zuordnung und Status existieren seit dem 02.09. (Abschnitte 3, 5, 6), der Statuslauf in
> `ck_anfrage_status` ist richtig geordnet (Abschnitt 3), und eine Freigabe ohne Anfrage ist
> **gewollt** (Abschnitt 7, Simeons Hinweis). Dafür kamen zwei Befunde dazu, die nur der Code
> zeigt: `abgeschlossen` sperrt eine Erhebung nicht (Abschnitt 1), und die Freigabe hält weniger
> Stand fest, als die Doku sagt (Abschnitt 7).

---

## 0. Wer vergibt welche ID — die Vergabetabelle

Alles, was im Ablauf eine Kennung bekommt, in der Reihenfolge des Entstehens. **Der Server vergibt
(ADR-004 R2), fortlaufend über das Maximum (R3), nie wiederverwendet.**

| ID | Muster · Prüfung | vergeben von | wann im Ablauf | Zähler |
|---|---|---|---|---|
| `company_id` | UUID · `gen_random_uuid()` | BC0-App, Admin | Station 1 | technisch |
| `KP-XX` | `^KP-[0-9]{2}$` | BC0-App | Station 1 (zehn aus der Vorlage) · Station 2 (`add_process`, **höchste + 1**, `app.py` 1433) | je Mandant, max. 99 |
| `KP-XX.TP-Y` | `^KP-[0-9]{2}\.TP-[0-9]+$`, `step_no` **1–9** (`ck_teilprozess_step_no`, v2.2) | BC0-App | Station 1 (fünf je KP) · Station 2 (`…/subprocess/add`, `step_no = max + 1`, `app.py` 1500) | je KP, **max. 9** — ADR-002, einstellig |
| `KP-XX.TP-Y.I-NN` | `^…\.I-[0-9]{2}$`, `item_nr` 1–30 | BC0-App, abgeleitet (`"%s.I-%02d"`, `app.py` 1584) | Station 1 / 2 beim Speichern der Bewertung | deterministisch aus TP + Item |
| `E-JJJJ-MM` | `^E-[0-9]{4}-[0-9]{2}$` | BC0-App, `_erhebung_offen()` (3116) oder `POST …/erhebungen` `aktion=neu` (3163) | Station 1 (beim ersten Speichern einer Bewertung) · Station 2 (Nacherhebung) | **eine je Mandant und Monat** — `neu` weist die zweite ab |
| `P-NN` · `S-NN` · `R-NN` · `MB-NNN` | je ein CHECK | BC0-App, `PUT …/entitaeten`, `…/rollen_kosten` | Station 1, Pflege in Station 2 | je Mandant, sperren statt löschen |
| `A-JJJJ-NN` | `^A-[0-9]{4}-[0-9]{2}$` | BC0-App, `POST …/anfragen` (höchste Nummer des Jahres + 1, `app.py` 4129) | Station 3 | je Mandant und Jahr, **max. 99** |
| `ereignis_id` | `BIGSERIAL` | Datenbank | Station 7 | global |
| `paket_id` | UUID | — **noch nicht vergeben** | Station 7, zweiter Schritt | geplant (22.08.) |
| `profil_version` | von BC1 festgelegt | **BC1** | Station 5/6 | die einzige Kennung im Ablauf, die **nicht** aus BC0 stammt — sie ist eine Version, keine Entität, und BC0 kopiert sie ins Gate |
| `SYS-<Kat>-<Kurz>` · `B-NN` · `item_nr` | global | BC0, Kataloge | vor allem | mandantenunabhängig |

**Zwei Zähler sind fachlich zu eng** (Drehbuch, Nachtrag 03.09.): `E-JJJJ-MM` kann zwei Erhebungen
im selben Monat nicht auseinanderhalten — der Endpunkt weist die zweite ab, `_erhebung_offen()`
schreibt in die bestehende. `A-JJJJ-NN` endet bei 99. Beides hält den Primärschlüssel formal
eindeutig, aber nicht das, was es fachlich gibt.

---

## Der Ablauf im Überblick

| # | Station | Was in der Datenbank entsteht | Was der nächste Schritt daraus braucht | Stand |
|---|---|---|---|---|
| 1 | Onboarding | Mandant, Landkarte (KP/TP), Register (P/S/R), Ersterhebung `E-JJJJ-MM` mit Bewertungen | die **Hülle** `KP-XX.TP-Y` — nicht die Vollbewertung | gebaut |
| 2 | Aktualisierung | neue Erhebung, neue KP/TP, `aktiv = false`, `prozess_herkunft` | dass Altes stehen bleibt und Neues eine neue ID trägt | Schema gebaut; `prozess_herkunft` ohne Bedienung (E8) |
| 3 | Anfrage | `A-JJJJ-NN`, Status `eingegangen`, Bezug optional | Prozessbezug, sonst „kein Fortschritt" | gebaut (v2.1–v2.3), Trichter 3 seit 03.09. |
| 4 | teilweise hinterlegt | — (Lesevorgang) | Lesesichten für `bc1_role` | gebaut, eine Zone offen (`ref_personen`) |
| 5 | BC1 baut aus | `bc1.prozessprofil` mit FK auf TP und Erhebung | `REFERENCES` (seit 02.09.) | Struktur geprüft, Tabelle leer (Stand 27.08.) |
| 6 | BC1 schließt ab | `status = 'fertig'`, `profil_version` | **ein lesbarer Zustand** — kein Signal | **offen — Punkt 82** |
| 7 | Gate 0 | `gate_ereignisse` + `gate_pruefpunkt_werte`; seit v2.6 die Historie als Stand | Übergabe-Ereignis mit `paket_id` | Freigabe gebaut; **Übergabe mit v2.6 am 04.09.** (Abschnitt 11) |
| 8 | Rückschreiben | `bc2.*`, `bc3.*`, `bc4.*` mit FK auf `KP-XX.TP-Y` | `REFERENCES` auf `ref_anfragen` — **nicht erteilt** | ADR-003; Anfrage-ID → ADR-006 |

---

## 1. Onboarding — der Mandant entsteht, und mit ihm die Hülle

**Reihenfolge, die die Fremdschlüssel erzwingen.** Es gibt genau einen Weg, in dieser Ordnung:

```
companies (company_id)
  └─ ref_prozesse (KP-XX)                    ← Pflicht: kategorie, process_name
       └─ ref_teilprozesse (KP-XX.TP-Y)      ← Pflicht: step_no, sub_process_name
            └─ ref_erhebungen (E-JJJJ-MM)    ← muss VOR der ersten Bewertung existieren
                 └─ bitkom_bewertungen       ← PK (company_id, erhebung_id, id), beleg NOT NULL
                      └─ bewertung_belege → beleg_dokumente   (Stufe 2 seit 03.09.)
  ├─ mandant_rollen (R-NN) → rollen_kostensaetze (gueltig_ab)
  ├─ ref_personen (P-NN, rolle_id optional) → prozess_personen (funktion im Schlüssel)
  ├─ mandant_systeme (S-NN, katalog_id optional) → teilprozess_systeme · medienbrueche
  ├─ prozess_schnittstellen (von_KP → nach_KP, art)
  └─ app_benutzer_mandanten                  ← ohne Zeile sieht kein Konto den Mandanten
```

**Was das Onboarding liefern muss, damit die Kette später nicht steht** — das ist enger als
„alles ausfüllen" und weiter als „Mandant anlegen":

| Angabe | wofür | Folge, wenn sie fehlt |
|---|---|---|
| `KP-XX` und `KP-XX.TP-Y` **benannt** | Anfrage (3), BC1 (5), Gate (7) | ohne ID kein Bezug, kein Beleg, kein Messpunkt — *Pflicht vor der Anfrage* (22.08.) |
| `ref_prozesse.beschreibung`, `trigger_text` | Trichter 3, BC1-Bot | Vorschlag findet nichts; Auswahlliste ohne Erklärung. **Bei NoroAI 0 von 10** |
| ein **Eigner** je KP in `prozess_personen` | Gate-Vorbedingung `eigner_benannt` | Bogen nicht ausfüllbar |
| **≥ 27 von 30 Items** je Fokus-TP | Gate-Vorbedingung `vollstaendig_bewertet` | nicht freigabefähig — darf **nach** der Anfrage nachkommen |
| Rollen mit Klasse **und** Kostensatz | Prüfpunkt `kosten` (BC0), ROI (BC2) | Gate-Güte fehlt; Kostenachse leer. **Bei NoroAI: Rollen ja, Sätze K1–K5 offen** |
| `prozess_schnittstellen` | Prüfpunkt Kette (`kette_bestaetigt`) | seit 02.09. 16 Kanten bei NoroAI, acht belegt, acht angenommen |
| `input_text`/`output_text` | Crossfunktionale Matrix | `? → ?` im Bericht; **0 von 10** |

**Vier Beobachtungen zur Vergabe in Station 1:**

Erstens: Die Ersterhebung `E-JJJJ-MM` hängt nicht am Anlegen des Mandanten, sondern am ersten
Speichern einer Bewertung — `_erhebung_offen()` legt sie dann für den laufenden Monat an
(`app.py` 3116–3138). Ein Mandant ohne Bewertung hat keine Erhebung — richtig, aber
`v_erhebung_aktuell` ist dann leer. Beim ersten Speichern springt zugleich `companies.status`
von `neu` auf `laeuft` (1595); auf `abgeschlossen` setzt es nichts.

Zweitens — **und das ist ein Befund, den nur der Code zeigt:** `abgeschlossen` sperrt eine
Erhebung nicht. `_erhebung_offen()` wählt *„die jüngste nicht verworfene"* — nach `stand DESC`,
**ohne auf `status = 'offen'` zu filtern** (3126–3128). `POST …/rating` prüft den Status ebenfalls
nicht (1581). Wer nach dem Abschließen einer Erhebung weiter bewertet, ohne vorher `aktion=neu`
zu rufen, schreibt in die abgeschlossene Erhebung hinein — per `ON CONFLICT … DO UPDATE` auch
**über bestehende Werte**. Damit ist der Stand, den eine Freigabe als `erhebung_id` festhält,
nachträglich veränderbar, und der Vorher/Nachher-Vergleich über `v_reifegrad_verlauf` mischt zwei
Zeitpunkte in einer Kennung. Die Doku v1.7 sagt zu Teil C *„abgeschlossen = Grundlage für
Freigaben"* — das stimmt nur, solange niemand danach bewertet. **Abhilfe:** in
`_erhebung_offen()` auf `status = 'offen'` filtern und ohne offene Erhebung abweisen (400: *„Keine
Erhebung offen — erst `neu`"*) oder automatisch eine neue anlegen; dazu ein CHECK-fähiger Trigger
in der Datenbank, der `INSERT`/`UPDATE` auf `bitkom_bewertungen` bei `abgeschlossen` abweist —
ADR-003 Regel 4, die Regel gehört in die Datenbank, nicht in den Weg dorthin. Bis dahin gilt
der Endpunkt `POST …/erhebungen` (`abschliessen` · `neu` · `verwerfen`, 3163) als gebaut, aber
sein Abschluss als Zusage ohne Sperre.

Drittens: `audit_log` ist weiterhin leer. Für BC1 bis BC4 gilt R3 als Bedingung; für BC0 selbst
ist sie nicht erzwungen. Das Onboarding hinterlässt keine Spur außer `created_at`/`bewertet_am`.

Viertens: `companies` hat kein `aktiv`, nur `status onboarding_status` mit den Werten `neu` ·
`laeuft` · `abgeschlossen` (v1.1.1, Zeile 36) — ein Erfassungsstand, kein Sperrmerkmal, und in der
Doku v1.7 nicht erklärt. Ein Mandant lässt sich nur löschen — mit `ON DELETE CASCADE` über alles,
einschließlich `bc1.*` (BC1 hat die Kaskade bewusst durchgelassen, 22.08.). Für die
DSGVO-Löschung ist das richtig; für „Mandant ruht" gibt es keinen Weg.

---

## 2. Aktualisierung des Onboardings — zwei verschiedene Dinge

Es gibt zwei Arten von Änderung, und sie laufen über zwei verschiedene Mechanismen. **Beide
folgen derselben Regel: Altes wird nicht überschrieben, Neues bekommt eine neue Kennung.**

### 2a — Die Werte ändern sich: Nacherhebung

| Mechanismus | Fundstelle | Wirkung |
|---|---|---|
| `erhebung_id` im Primärschlüssel von `bitkom_bewertungen` | v1.3 Teil C, §28 | dieselbe `KP-XX.TP-Y.I-NN` darf in `E-2026-09` erneut vorkommen; die Zeile aus `E-2026-05` bleibt |
| `v_bewertung_aktuell` | Teil C, §29.1 | je TP und Item die jüngste nicht verworfene Bewertung — **Zusammensetzung**, kein Filter auf die jüngste Erhebung |
| `v_reifegrad_verlauf` | Teil C | Vorher/Nachher je Erhebung |
| `quelle` an der Bewertung | v1.1 | `manuell` — für BC1-Interviews wäre `bc1_interview` nötig (ENUM-Erweiterung, offen) |

**Was eine Nacherhebung mit den nachgelagerten Stationen macht:**

| Station | Was passiert | Erkennbar? |
|---|---|---|
| Gate 0 (7) | Die Freigabe trägt `erhebung_id` **als kopierten Wert**. Sie bleibt gültig und bezieht sich weiter auf den alten Stand | **Nur durch Vergleich.** `v_gate_freigabe_aktuell.bc0_stand` gegen `v_erhebung_aktuell.erhebung_id` — es gibt keine Sicht, die „Freigabe beruht auf älterem Stand" ausweist |
| BC1 (5) | `bc1.prozessprofil.erhebung_id` als kopierter Wert (Antwort an Richard, 22.08., Punkt 1.2) | dito |
| BC2 (8) | rechnet auf dem übergebenen Paket, nicht auf dem aktuellen Stand | erst mit `paket_id` sauber |

**Vorschlag:** eine Sicht `v_stand_veraltet` je Teilprozess mit drei Spalten — `freigabe_stand`,
`profil_stand`, `aktueller_stand` — und einem Merkmal `veraltet`. Sie kostet eine halbe Stunde und
beantwortet die Frage, die nach der ersten Nacherhebung jeder stellt: *„Gilt die Freigabe noch?"*
Die Antwort bleibt bei einem Menschen; die Sicht sagt nur, dass die Frage ansteht.

### 2b — Die Struktur ändert sich: Landkarte

| Vorgang | Mechanismus (v2.2, `app.py`) | Was mit Bestand geschieht |
|---|---|---|
| Kernprozess ergänzen | `add_process` vergibt `KP-(max+1)`, Name und `kategorie` mitgegeben | fünf neue TP-Hüllen (`START_TP = 5`) |
| Teilprozess ergänzen | `step_no` bis 9 | unbewertet, **nicht freigabefähig** — richtig so (E4) |
| Stilllegen | `aktiv = false` an `ref_prozesse`, `ref_teilprozesse` | Bewertungen, Freigaben, BC-Verweise bleiben |
| Teilen / Zusammenlegen / Umhängen | **neue ID**, Eintrag in `prozess_herkunft` (n:m, `art`, `gueltig_ab`, `grund`) | Bewertungen bleiben an der alten ID (E4); Freigabe bleibt an der alten ID |
| Löschen | `DELETE` mit `ON DELETE CASCADE` | **nimmt Bewertungen und Belege mit** — nicht auf Admin beschränkt (E6, Sicherheitskonzept 3.5) |

**Drei Abhängigkeiten, die hier für BC1 bis BC4 entscheidend sind:**

`prozess_herkunft` hängt nur am Mandanten, **nicht per Fremdschlüssel** an `ref_teilprozesse`
(Abhängigkeiten-Papier, Abschnitt 3). Ein Tippfehler in `vorgaenger_id` fällt nicht auf. Solange
die Anwendung die Tabelle nicht füllt (E8), ist das eine theoretische Lücke; sobald sie es tut,
gehört der Fremdschlüssel dazu — auf `aktiv = false`-Zeilen zeigt er trotzdem, weil Stilllegen
nicht löscht.

**Löschen muss abgewiesen werden, sobald ein BC etwas angehängt hat.** BC1s Fremdschlüssel auf
`ref_teilprozesse` entscheidet das: `RESTRICT` blockiert die Löschung (gut), `CASCADE` nimmt BC1s
Profil stillschweigend mit (schlecht). Welches gesetzt ist, steht in BC1s DDL, nicht in unserer —
**zu prüfen, bevor der Löschweg auf Admin beschränkt wird.** Die sauberste Regel: Für KP und TP
gibt es keinen `DELETE`-Endpunkt mehr, nur `aktiv = false`. Das ist die Regel R4 aus ADR-004,
wörtlich.

**Die Ursprungs-ID** (Rückschreib-Papier von heute): Nach einer Teilung führt BC2 seine ROI-Zahl
weiter unter `KP-06.TP-2`, obwohl es jetzt `TP-6` und `TP-7` gibt. Das ist gewollt. Was dabei
fehlt, ist die Gegenrichtung: Wer `TP-6` aufschlägt, sieht nicht, dass unter `TP-2` ein ROI liegt.
Eine Sicht `v_herkunft_kette`, die je TP alle Vorgänger auflöst, schließt das — und wird in
demselben Moment nötig, in dem `prozess_herkunft` die erste Zeile bekommt.

### 2c — Die Register ändern sich

Personen, Systeme, Rollen: sperren statt löschen (`aktiv = false`), Kostensätze: neue Zeile mit
`gueltig_ab` statt Überschreiben. Beides ist gebaut. **Ein Verweis überlebt die Sperre** — eine
Anfrage von `P-07` bleibt lesbar, auch wenn `P-07` inzwischen ausgeschieden ist. Nur bei echtem
Löschen der Person setzt `fk_anfrage_steller` den Verweis auf `NULL`; der Originaltext bleibt.

---

## 3. Die Anfrage kommt herein — der Anker der Kette

**Seit dem 27.08. ist die Anfrage der Trigger für BC1** (Beschluss, ToDo-Liste). Sie entsteht
über `POST …/anfragen` — aus BC0 oder aus `/anfrage/` (seit 02.09., unterscheidbar nur über
`eingang_weg`).

| Feld | Regel | Fundstelle |
|---|---|---|
| `anfrage_id` | `A-JJJJ-NN`, je Mandant | v1.4 |
| `originaltext` | NOT NULL, **wird nie verändert** | v1.4 |
| `steller_id` | FK → `ref_personen`, `SET NULL` — kein Klarname in der Tabelle | v1.4 |
| `process_id` | FK → `ref_prozesse`, `RESTRICT` — nullable seit v2.3 | v2.1 + v2.3 |
| `sub_process_id` | FK → `ref_teilprozesse`, `SET NULL`; CHECK gehört zum KP | v2.1 |
| `zuordnung_quelle` | `anfrage` · `vorschlag_bc0` · `vorschlag_bc1` · `interview`; paarweise mit `process_id` | v2.1 + v2.3 |
| `status` | CHECK-Werteliste; `ck_anfrage_fortschritt_braucht_prozess`: **ohne Prozess kein Fortschritt** | v2.2 + v2.3 |
| `erhofftes_ziel` · `ausloeser` · `umfang_geschaetzt` (Freitext, bewusst) | — | v2.2 / v2.3 |

**Der Statuslauf**, wie er in `ck_anfrage_status` (v2.2) steht:

```
eingegangen → zugeordnet → im_interview → am_gate → bewertet → beauftragt → erledigt | abgelehnt
```

Das Konzept vom 26.08. hatte `bewertet (BC2)` noch **vor** `entschieden (Gate 0)` — das Skript
vom 27.08. hat es berichtigt und sagt es im Kommentar selbst: *„Gate 0 steht ZWISCHEN Interview
und ROI-Rechnung, nicht dahinter."* Der Widerspruch, den die erste Fassung dieses Papiers
vermutete, existiert im Schema nicht. `bewertet` heißt dort: BC2 hat gerechnet.

**Seit dem 02.09. gibt es drei Endpunkte, mit denen BC1 die Anfrage weiterbewegt** (Commit
`f5b4ada`, Punkte 65 und 98 erledigt, ausgerollt und gegengeprüft laut ToDo-DB):

| Endpunkt | tut | erzwingt |
|---|---|---|
| `PUT …/anfragen/{id}/zuordnung` (4475) | Prozessbezug nachtragen, **ändert den Status nicht** | `zuordnung_quelle` Pflicht (ADR-005); TP muss zum KP gehören |
| `PUT …/anfragen/{id}/status` (4552) | Status setzen, `status_seit` | Wertemenge; **kein Fortschritt ohne Bezug**; **kein Rücksprung** außer nach `abgelehnt` |
| `POST …/prozesskanten` (4620) | Kante zwischen Kernprozessen ergänzen | `art` Pflicht, Herkunft in der Beschreibung |

Alle drei laufen hinter `Depends(angemeldeter_benutzer)`. **Das ist eine Abhängigkeit, die
niemand aufgeschrieben hat:** BC1 braucht dafür kein Datenbankrecht, sondern ein
**Anwendungskonto** mit Mandantenzuordnung — eine Sitzung über `POST /api/auth/login`, ein Cookie,
und seit dem 02.09. die Anmeldebremse davor. Richards Bot ruft also HTTP mit einem
`app_benutzer`, nicht SQL mit `bc1_role`. Ob er ein solches Konto hat, steht in keinem Papier;
die Zugangsdaten vom 12.08. waren Datenbankzugänge. **Ohne Konto bleibt der Statuslauf für BC1
unerreichbar — nicht wegen fehlender Endpunkte, sondern wegen fehlender Anmeldung.**

**Die drei Grenzen dieser Station**, alle bereits benannt und terminiert:

| | Grenze | Punkt |
|---|---|---|
| a | **Ein Bezug je Anfrage.** Trichter 3 liefert bis zu drei, übernehmen lässt sich einer | 115 → `anfrage_prozesse` mit `rolle = 'haupt'` |
| b | **Die Anfrage-ID verlässt BC0 nicht.** Kein `REFERENCES ref_anfragen` für `bc1_role`–`bc4_role`; ADR-003 Regel 2 nennt sie nicht | 116 → ADR-006 |
| c | **BC1 liest nur `v_anfrage_prozessbezug`** (IDs, Status) — nicht den Originaltext. Wo der Text für das Interview herkommt, ist offen | Dreier-Termin |

---

## 4. Unternehmen und Prozesse sind teilweise hinterlegt — was BC1 vorfindet

„Teilweise" hat in der Datenbank drei messbare Formen, und `v_gate_vorbedingungen` zeigt alle:

| Form | woran erkennbar | Fall im Konzept vom 26.08. |
|---|---|---|
| Hülle mit Namen, bewertet | `items_bewertet ≥ 27`, `eigner_benannt` | Fall 1 — nur lesen |
| Hülle mit Namen, unbewertet | `items_bewertet < 27` | Fall 2 — BC1 ergänzt |
| Hülle ohne Inhalt | `sub_process_name` aus der Vorlage, `beschreibung IS NULL` | Fall 3 — BC1 hinterlegt, **ID stammt trotzdem aus BC0** |

**Was `bc1_role` lesen darf** (Doku v1.7, Abschnitt 11; v2.4 laut Drehbuch S-103):
`companies`, `company_profile`, `ref_items`, `ref_teilprozesse`, `bitkom_bewertungen` und alle
Reifegrad-Sichten, `v_prozesse_lesen` (statt `ref_prozesse` — entzogen 23.08.),
`v_prozess_personen_lesen`, `v_personen_abdeckung`, Rollen und Kostensätze, Systeme und
Medienbrüche, `v_gate_freigabe_aktuell`, `ref_gate_pruefpunkte`, `v_anfrage_prozessbezug`.

**Was `bc1_role` zusätzlich liest, an `bc_leser` vorbei:** `ref_personen` und `prozess_personen`
— die Klarnamen. Das ist nach v2.4 die einzige verbliebene Direktvergabe und bewusst stehen
gelassen, weil der Bot Menschen mit Namen anspricht. Die Frage, welche Felder er braucht
(`v_personen_interview` oder Freigabe mit Zweckangabe), ist offen und bleibt Richards.

**Eine Abhängigkeit, die an dieser Station unsichtbar ist:** BC1 liest die Baseline **ohne**
Erhebungsbezug, wenn er `bitkom_bewertungen` direkt liest statt `v_bewertung_aktuell`. Die
Rohtabelle enthält seit Teil C **alle** Erhebungen — für NoroAI 690 Zeilen, davon 90 Testdaten in
`E-2026-08`. Wer die Tabelle statt der Sicht liest, mittelt über zwei Zeitpunkte. Die Checkliste
vom 27.08. nennt den Filter; die Sicht wäre der sicherere Weg. **Empfehlung: `bitkom_bewertungen`
für `bc_leser` entziehen, `v_bewertung_aktuell` genügt.** Gleiche Logik wie bei `ref_prozesse`.

---

## 5. BC1 baut das aus — was er anlegt und woran es hängt

**Geprüfte Zielstruktur** (Antwort an Richard, 22.08., Abschnitt 1):

```
bc1.prozessprofil
  PK  (company_id, focus_step_id, profil_version)
  FK  (company_id, focus_step_id)  → ref_teilprozesse (company_id, sub_process_id)
  FK  (company_id, erhebung_id)    → ref_erhebungen                         ← kopierter Stand
  FK  (company_id)                 → companies, ON DELETE CASCADE
  status         in_erhebung | fertig
  duration_*, frequency_*, rollen mit zeitanteil, upstream/downstream als KP-XX
  profil_systeme als JSON mit S-NN — Auflage: gegen mandant_systeme prüfen
```

`REFERENCES` auf die fünf Zieltabellen ist seit dem 02.09. erteilt (`schema_v2.4_rechte_bc1.sql`,
laut Drehbuch S-103) — vorher hatte `bc1_role` **kein einziges**, und genau daran brach Richards
Einspielskript ab. **Ob die Tabelle seither angelegt und gefüllt wurde, ist nicht bekannt**; am
27.08. war sie für alle drei Use Cases leer, und die Frist für Richards Antwort läuft bis 07.09.

**Vier Dinge, die BC1 an der Baseline ergänzen will, und für jedes der Weg:**

| Was | Ziel in `public` | Weg (entschieden 22./26.08.) | gebaut? |
|---|---|---|---|
| Name und Inhalt einer Hülle (Fall 2/3) | `ref_teilprozesse` | (a) `bc1.*`-Vorschlag, BC0 übernimmt | **nein** |
| die 30 Items des Fokus-Schritts | `bitkom_bewertungen` (`quelle = bc1_interview`) | (a) `bc1.bewertungen_vorschlag`, BC0 übernimmt in eine Erhebung | **nein** — und `beleg_source` braucht den Wert |
| Prozessbezug der Anfrage | `ref_anfragen.process_id`, `zuordnung_quelle = interview` | Endpunkt der Anwendung (Weg A), **kein** `GRANT UPDATE` | **ja**, 02.09. — `PUT …/zuordnung` (Punkt 98) |
| Anfrage-Status `im_interview` | `ref_anfragen.status` | Endpunkt | **ja**, 02.09. — `PUT …/status` (Punkt 65) |
| fehlende Prozesskante | `prozess_schnittstellen` | Endpunkt | **ja**, 02.09. — `POST …/prozesskanten` |
| `medienbrueche.aufwand_min` | `medienbrueche` | nicht entschieden — Doku sagt „BC0 füllt das nicht, entsteht im BC1-Interview" | **nein** |

Das ist die vollständige Liste dessen, was BC1 **in BC0-Tabellen** verändern will. Für die drei
Anfrage-nahen gibt es seit dem 02.09. einen Schreibweg — als HTTP-Endpunkt hinter einer
Anmeldung, nicht als Grant (Abschnitt 3). Für die drei Baseline-nahen (Hüllen-Namen, 30 Items,
`aufwand_min`) gibt es keinen. **Das ist kein Versäumnis, sondern die Regel** — ADR-003 ohne
Ausnahme — aber es heißt: Solange die Übernahme für diese drei fehlt, bleibt alles, was BC1 im
Interview über die Baseline lernt, in `bc1.*` liegen. Das Gate liest es dort (gut), die Baseline
lernt nichts (schlecht), und beim nächsten Mandanten fängt BC1 mit derselben Hülle an.

**Die `bc1_*`-Spalten in `public`** aus ADR-003 Regel 3 gibt es nicht (#148). Das ist in Ordnung:
Regel 3 kennt zwei Formen, und die Tabellenform ist die, die gebaut wird. Die Spaltenform sollte
im ADR als „vorgesehen, nicht genutzt" markiert werden, sonst sucht sie jemand.

---

## 6. BC1 schließt ab — woher weiß BC0 das, wenn niemand in der App ist?

**Die kurze Antwort:** BC0 weiß es nicht — und muss es auch nicht *wissen*, sondern **lesen
können, wann immer jemand nachsieht.** Das ist dieselbe Regel, die für BC2 seit dem 10.08.
beschlossen ist: *Die Datenbank ist der Kanal. Ein Zustand ist wiederholbar lesbar, eine verpasste
Nachricht ist weg.* Was für BC0 → BC2 gilt, gilt für BC1 → BC0 nicht weniger.

**Die Vorbedingung dafür ist seit dem 22.08. vereinbart und seit dem 11.08. nicht erfüllt**
(Punkt 82, „letzte fehlende Angabe für 4d"):

| Was BC0 braucht | Stand |
|---|---|
| Tabelle `bc1.prozessprofil` | Struktur geprüft, Anlage bei BC1 |
| `status IN ('in_erhebung','fertig')` — *„fertig heißt: Interview abgeschlossen und Profil eingefroren, nicht: alle Angaben belegt"* | vereinbart 22.08. |
| `profil_version`, die sich **beim Nachschreiben ändert** | vereinbart |
| Leserecht von BC0 (`postgres`) auf `bc1.*` | `ROLLEN.md` Schritt 5/6: `GRANT bc1_role TO CURRENT_USER` und `ALTER DEFAULT PRIVILEGES … GRANT SELECT … TO bc_leser` — neue Tabellen von BC1 sind ohne Nacharbeit lesbar |
| `_bc1_angaben()` in `app.py` an die Tabelle anschließen | gibt heute `None` zurück; Test `test_entscheiden_ist_ohne_bc1_nicht_erreichbar` **soll fallen** |

**Zwei Bedingungen, nicht eine** (S-085): Das Statusfeld ist BC1s *Erklärung*, die Feldprüfung
ist BC0s *Tatsache*. Prüfte BC0 nur die Felder, griffe es in ein laufendes Interview; verließe es
sich nur auf den Status, vertraute es einer Absichtserklärung. Entscheidungsreif ist ein
Teilprozess, wenn **BC0-Vorbedingungen ∧ `status = 'fertig'` ∧ die vier Prüfpunkte aus BC1
gefüllt** — und noch keine Entscheidung auf dieser `profil_version` liegt.

**Und die Sorge „wir sind nicht immer aktiv drin"** zerfällt in zwei Teile, die man auseinanderhalten
muss:

**Der Mensch ist nicht immer da — die Anwendung schon.** `bc0-app-1` läuft seit dem 06.08. im
Dauerbetrieb. „BC0 ist nicht aktiv" heißt: der HitL sitzt nicht vor dem Reiter. Das ist für ein
Gate, an dem ohnehin ein Mensch entscheiden muss, kein Mangel: Nichts geht verloren, weil nichts
gesendet wird. Wenn er den Reiter öffnet, steht die Zeile oben, im Block „zu entscheiden". Die
Zweiteilung vom 17.08. war genau dafür gebaut: *„Sobald BC1 liefert, wandert eine Zeile von allein
nach oben."* — sobald `_bc1_angaben()` liest.

**Was also fehlt, ist nicht ein Signal, sondern drei Handgriffe in aufsteigender Reichweite:**

| Stufe | Bauform | Reichweite | Aufwand |
|---|---|---|---|
| **1 — Arbeitsliste** | `_bc1_angaben()` liest `bc1.prozessprofil`; eine Sicht `v_gate_bereit` je TP: Vorbedingungen ∧ `fertig` ∧ Felder ∧ nicht entschieden auf dieser Version | wer den Reiter öffnet, sieht es | ~2 h, sobald BC1s Tabelle steht |
| **2 — Zähler auf der Startseite** | dieselbe Sicht, gezählt, als Kachel „3 Teilprozesse warten auf Entscheidung" — auch für die Rolle `benutzer` sichtbar, nicht nur für Admins | wer sich anmeldet, sieht es ohne den Reiter | ~1 h |
| **3 — Mail aus dem Cron** | der Backup-Cron auf dem Server läuft täglich; ein zweiter Job fragt `v_gate_bereit`, schickt bei Änderung eine Mail. **Die Anwendung hat keinen Mailweg** (E2) — der Server hat ihn, oder bekommt ihn mit einer Zeile `msmtp` | wer nicht anmeldet, erfährt es trotzdem | ~2 h, plus E2 |
| *(4 — `LISTEN/NOTIFY`)* | Beschleuniger, kein Kanal; verpasste Benachrichtigung ist weg | — | **nicht als alleiniger Weg** (22.08.) |

**Stufe 1 ist der Gegenstand von Punkt 82, Stufe 2 und 3 sind die Antwort auf „nicht immer
aktiv".** Alle drei lesen denselben Zustand. Keine baut einen zweiten Kanal. Und keine ist von
Richard abhängig, sobald seine Tabelle existiert — der Rest ist BC0.

**Dazu das Spiegelbild:** Seit dem 02.09. kann BC1 den Anfrage-Status setzen und den
Prozessbezug nachtragen (Abschnitt 3). Damit ist `ref_anfragen.status` ein **zweiter, gröberer
Indikator** für „BC1 ist dran", der auch ohne `bc1.prozessprofil` funktioniert: `im_interview`
heißt, das Gespräch läuft; `am_gate` heißt, BC1 sieht sich fertig. Er ersetzt die Feldprüfung
nicht — er ist die Erklärung, nicht die Tatsache — aber er ist heute schon lesbar, während
`bc1.prozessprofil` noch auf Richard wartet. **Voraussetzung:** BC1 hat ein Anwendungskonto
(Abschnitt 3). Bei NoroAI steht heute jede Anfrage auf `eingegangen` — nicht, weil der Weg fehlt,
sondern weil ihn noch niemand gegangen ist.

**Eine Zusicherung, die BC1 geben muss und die in keinem Papier steht:** `fertig` ist **endgültig
für diese `profil_version`**. Wer nachschreibt, erhöht die Version. Sonst kann BC0 ein Profil
lesen, es als `fertig` einsortieren, und BC1 ändert es unter derselben Version — und die Freigabe
hat etwas anderes freigegeben als BC2 liest. Genau der Fall, gegen den `bc1_profil_stand` gebaut
ist. Er trägt nur, wenn die Version bei jeder Änderung wächst. **Das gehört in die Checkliste an
Richard, als Bedingung, nicht als Wunsch.** Richard hat es am 22.08. sinngemäß zugesagt
(„Profil eingefroren"); technisch erzwingen ließe es sich mit einem Freeze-Trigger in seinem Schema
— den hat er nach eigener Aussage.

---

## 7. Gate 0 wird freigegeben — was festgehalten wird und was noch fehlt

**Der erste Schritt ist gebaut** (v1.4, 17.08.). Je Teilprozess, Mensch entscheidet, Server prüft:

| Was die Datenbank erzwingt | Wo |
|---|---|
| Vorbedingung: Eigner benannt ∧ ≥ 27 Items | `v_gate_vorbedingungen`, Endpunkt lehnt sonst ab |
| Güte bei jedem rechnungsrelevanten Prüfpunkt, nur bei `freigegeben` | Trigger `gate_guete_pflicht` |
| Maßnahme bei Zurückweisung | `ck_gate_massnahme` |
| Prüfbogen und Ereignis in **einer** Transaktion | Anwendung |
| Kopierter Stand: `erhebung_id`, `bc1_profil_stand`, `anfrage_id` (FK, `SET NULL`) | Spalten an `gate_ereignisse` |
| Protokoll überlebt den Gegenstand: `objekt_id` **ohne** FK, bewusst | Kommentar v1.4 §16 |
| `bc_leser` liest **nur** `v_gate_freigabe_aktuell`, nie die Ereignistabelle | *„Ein Protokoll, das der Gelesene ändern kann, ist keines"* |

**Was `v_gate_freigabe_aktuell` an BC2 gibt:** je TP der letzte Stand, `bc0_stand`,
`bc1_profil_stand`, `anfrage_id`, die Zählung geraten/geschätzt/ohne Haken, die Güten als JSON
und `hinweis_an_bc2` (Punktwert · Bandbreite empfohlen · Bandbreite rechnen). **Das ist die Sicht,
mit der BC2 heute schon lesen könnte** — sie existiert seit dem 17.08.

**Der zweite Schritt fehlt** — die Übergabe (Beschluss 10.08., Vorlage 22.08.):

| Baustein | Stand |
|---|---|
| Ereignis `uebergeben` mit `paket_id` (CHECK vorhanden: Pflicht bei `uebergeben`) | Spalte und CHECK seit v1.2; **kein Endpunkt schreibt es** |
| `v_uebergabe_offen` mit `GRANT SELECT` an `bc2_role` | nicht gebaut |
| Knopf „Paket an BC2 übergeben" mit Anzeige des Inhalts **vor** dem Übergeben | nicht gebaut |
| Nachzügler → neues Paket (Position BC0) | nicht entschieden |

**Was die Freigabe tatsächlich als Stand festhält — weniger, als die Doku sagt.** Der Endpunkt
`POST …/gate/{sub_process_id}` (`app.py` 3922 ff.) schreibt `erhebung_id = _erhebung_offen()`
— also **die jüngste nicht verworfene Erhebung des Mandanten**, nicht die Erhebungen, aus denen
die 30 Werte tatsächlich stammen. Nach einer Teil-Nacherhebung (`aktion=neu`, KP-05 bis KP-10)
trägt eine Freigabe von `KP-02.TP-3` die Kennung `E-2026-09`, obwohl alle dreißig Werte aus
`E-2026-05` sind. `grundlage` (JSONB, laut Doku *„der Datenstand, auf den sich die Freigabe
bezieht"*) wird **nicht geschrieben**; `bc1_profil_stand` ebenfalls nicht — es gibt noch keine
Quelle. **Reproduzierbar ist die Freigabe damit nur über `v_bewertung_aktuell` zum Zeitpunkt
`am`**, und das ist eine Rechnung, kein Beleg. Abhilfe in einer Zeile: beim Freigeben die dreißig
`(item_nr, erhebung_id, stufe)` des Teilprozesses als `grundlage` mitschreiben. Zusammen mit dem
Befund aus Abschnitt 1 (`abgeschlossen` sperrt nicht) ist das der Punkt, an dem
Reproduzierbarkeit heute am dünnsten ist.

**Eine Freigabe ohne Anfrage ist gewollt** — Simeons Hinweis vom 03.09.: Ein Unternehmen kann
sagen *„schaut mal, was wir besser machen und was wir automatisieren können"*, ohne ein konkretes
Anliegen. Das ist Vorschlag 5 aus dem Papier vom 22.08. (BC0 stößt aus dem Dashboard an,
Portfolio-Weg) und Richards „Weg 2". `gate_ereignisse.anfrage_id` bleibt deshalb **nullable**,
und der Endpunkt nimmt sie optional entgegen (3922+81). Die erste Fassung dieses Papiers hatte
hier eine Pflicht vorgeschlagen — **zurückgenommen.**

**Für die Übergabe folgt daraus etwas Konkretes.** Es gibt zwei Wege in die Kette, und beide
müssen im Paket darstellbar sein:

| Weg | Auslöser | Gegenstand von BC2 | Paket trägt |
|---|---|---|---|
| **anfragegetrieben** | `A-JJJJ-NN` | die Prozesse **dieser Anfrage** (S-106) | `anfrage_id` — mit 115 auch mehrere KP/TP je Anfrage |
| **portfoliogetrieben** | Dashboard, Zustand `wartet_bc1`/`entscheiden` | alle freigegebenen TPs des Mandanten | keine Anfrage — `anfrage_id IS NULL` |

Die **Übergabe-Einheit vom 22.08. („je Unternehmen") bleibt damit richtig**, weil sie beide Wege
trägt; „je Anfrage" allein täte es nicht. Was dazukommt: **Das Paket muss die Anfrage-IDs
mitführen**, die in seinen Freigaben stecken — `v_uebergabe_offen` bekommt je TP die
`anfrage_id` (oder `NULL`), und BC2 gruppiert selbst: eine ROI-Rechnung je Anfrage, eine je
Portfolio-Freigabe. Das ist genau der Grund, warum die Anfrage-ID in ADR-006 gehört (116): Ohne
`REFERENCES ref_anfragen` kann BC2 seine Rechnung nicht an die Anfrage hängen, die im Paket steht.

**Der zweite Schritt bleibt nicht mehr an einer Grundsatzfrage hängen**, sondern an drei
Handgriffen: Ereignis `uebergeben` mit `paket_id` schreiben, `v_uebergabe_offen` mit
`anfrage_id` je Zeile, Knopf mit Vorschau. Offen ist allein die Nachzügler-Regel (neues Paket —
Position BC0, nicht entschieden).

---

## 8. Zurückschreiben der Ergebnisse auf diese ID

**Die Regel** (ADR-003 R1–R3, Rückschreib-Papier von heute): Kein BC schreibt in `public`. Jeder
legt in seinem Schema eine Tabelle an, mit Fremdschlüssel auf `(company_id, sub_process_id)` —
die **Ursprungs-ID**, nicht die heutige. Zurück kommt das Ergebnis durch Lesen: `bc_leser` sieht
`bc1` bis `bc4`.

**Woran das heute hängt, je BC:**

| BC | Tabelle (Beispiel) | FK auf | zusätzlich mitzuführen | `REFERENCES` erteilt? |
|---|---|---|---|---|
| BC1 | `bc1.prozessprofil` | `ref_teilprozesse`, `ref_erhebungen`, `companies`, `mandant_rollen` | `profil_version`, `erhebung_id` (kopiert) | **ja**, 02.09. |
| BC2 | `bc2.roi_rechnung` | `ref_teilprozesse` | `paket_id`, `bc1_profil_stand`, `erhebung_id`, **`anfrage_id`** | `ref_anfragen`: **nein** |
| BC3 | `bc3.ticket` | `ref_teilprozesse` | Ursprungs-ID auch nach Teilung, `anfrage_id` | nein |
| BC4 | `bc4.bauteil` | `ref_teilprozesse` | dito | nein |

**Was BC2 bis BC4 brauchen und heute nicht bekommen können:**

Erstens `GRANT REFERENCES ON ref_anfragen TO bc2_role, bc3_role, bc4_role` — ohne ihn kann
niemand sein Ergebnis an die Anfrage hängen (Punkt 116, ADR-006). Und `bc2_role` bis `bc4_role`
haben **kein** `REFERENCES` auf `ref_teilprozesse`: `schema_v2.4_rechte_bc1.sql` erteilt die fünf
Rechte ausschließlich an `bc1_role` (Zeilen `GRANT REFERENCES … TO bc1_role`), ein Skript für die
anderen drei gibt es nicht. Sie stehen damit heute genau da, wo Richard am 02.09. stand — ihr
erstes `CREATE TABLE … REFERENCES ref_teilprozesse` bricht ab.

Zweitens `paket_id` — existiert als Spalte, wird nirgends vergeben (Station 7).

Drittens die vier Herkunftsspalten je Wert (ADR-005 R2: wer · wann · woher · wie belastbar).
Die Spalten sind verbindlich, die Werteliste je BC frei; BC0 sammelt sie ein (Punkt 96, 07.09.).
**Ohne sie ist ein zurückgeschriebener Wert nachvollziehbar zuzuordnen, aber nicht bewertbar.**

**Was in BC0 nach dem Rückschreiben zu lesen ist — und wer es liest:**

| Leser | Sicht | Stand |
|---|---|---|
| BC0 (Gate) | `bc1.prozessprofil` über `_bc1_angaben()` | nicht angeschlossen (Station 6) |
| BC2 | `v_gate_freigabe_aktuell` + `v_uebergabe_offen` | erste gebaut, zweite nicht |
| BC3/BC4 | `bc2.*` über `bc_leser` | sobald BC2 schreibt |
| Mensch | ein Reiter „Ergebnisse der BCs" je TP — **gibt es nicht** | BC0 zeigt heute nur seine eigenen Daten; was BC1 bis BC4 zurückgeschrieben haben, ist in der Anwendung unsichtbar |

Der letzte Punkt ist der, den man leicht übersieht: **Die Datenbank hält die Rückführung, die
Anwendung zeigt sie nicht.** Für den HitL am Gate ist das ab Station 6 gelöst (er sieht BC1s
Angaben im Bogen). Für alles danach — ROI, Tickets, Bau — hat BC0 keine Oberfläche. Ob es sie
braucht, ist eine Frage an das Team; dass sie fehlt, sollte niemand überraschen.

---

## 9. Die Abhängigkeitskette, zusammengefasst — was wovon blockiert ist

```
Station 1  Hülle KP/TP + Eigner            ─┐
Station 3  Anfrage A-JJJJ-NN               ─┤
Station 5  bc1.prozessprofil (BC1 legt an) ─┼─► Station 6  status='fertig' + Felder   ← Punkt 82 (Richard)
Station 2  Erhebung ≥ 27 Items je Fokus-TP ─┘        │                                  + _bc1_angaben() (BC0)
                                                     ▼
                                            Station 7a  Freigabe je TP            ← gebaut
                                                     │
                                            Station 7b  Übergabe je ?             ← Einheit neu bestätigen (07.09.)
                                                     │   paket_id, v_uebergabe_offen
                                                     ▼
                                            Station 8   bc2.* mit FK auf TP       ← REFERENCES für bc2–bc4 unbelegt
                                                        + anfrage_id              ← ADR-006, GRANT fehlt
```

**Drei Dinge blockieren die Kette, in dieser Reihenfolge:**

| | Blocker | wer | wann |
|---|---|---|---|
| 1 | `bc1.prozessprofil` existiert nicht oder ist leer; Status/Version nicht bestätigt | Richard — oder BC0 setzt Ersatzwerte (Weg b) | Frist 07.09. |
| 2 | `_bc1_angaben()` nicht angeschlossen; kein Zähler, keine Mail | BC0 | nach 1, ~5 h |
| 3 | Übergabe: Paket, `v_uebergabe_offen`, Knopf — **gebaut, v2.6, Ausrollen 04.09.**; offen bleibt `REFERENCES` für bc2–bc4 auf `ref_teilprozesse` und `ref_anfragen` | BC0 · Team bestätigt die Einheit am 07.09. | 04.09. / 07.09. |

Alles andere in diesem Papier — Erhebung sperren, `grundlage` schreiben, Nacherhebungs-Sicht,
Herkunftskette, `DELETE` abschaffen, `bitkom_bewertungen` für `bc_leser` entziehen — ist
Härtung, kein Blocker. Zwei davon (Erhebung, `grundlage`) betreffen die Reproduzierbarkeit und
sollten vor der ersten echten Nacherhebung (#143) erledigt sein.

---

## 10. Was ins Meeting am 07.09. gehört — Ergänzung zu 115 und 116

| | Punkt | Art |
|---|---|---|
| 115 | Eine Anfrage, mehrere Prozesse → `anfrage_prozesse` | Richtung |
| 116 | Anfrage-ID → ADR-006, `GRANT REFERENCES` an bc1–bc4 | Entscheidung |
| **neu a** | **Übergabe-Einheit bestätigen:** „je Unternehmen" (22.08.) bleibt, **das Paket führt je TP die `anfrage_id` mit** (oder `NULL` für den Portfolio-Weg); Nachzügler → neues Paket | Bestätigung, dann BC0 |
| **neu b** | Zusicherung BC1: `fertig` ist endgültig je `profil_version`; Nachschreiben erhöht die Version | Bestätigung Richard |
| **neu c** | `REFERENCES` auf `ref_teilprozesse` (und mit 116 auf `ref_anfragen`) auch für `bc2_role`–`bc4_role` — `schema_v2.4` erteilt es nur `bc1_role` | BC0, ohne Beschluss möglich |
| **neu d** | **BC1 braucht ein Anwendungskonto** für `…/zuordnung`, `…/status`, `…/prozesskanten` — die Datenbankrolle reicht nicht | Absprache mit Richard, BC0 legt an |
| **neu e** | **Historie statt Sperre** (Abschnitt 11): v2.6 wird am 04.09. eingespielt — R9, Paket, Zeitreise. Das Team soll wissen: BC2 liest mit `stand_zum()` zum Paketdatum, Nachzügler bekommen ein neues Paket | Information, kein Beschluss |

*Entfallen gegenüber der ersten Fassung:* „`anfrage_id` bei `freigegeben` Pflicht" (Freigabe ohne
Anfrage ist gewollt) und „Statuslauf prüfen" (v2.2 ist richtig geordnet).

---

## 11. Müssen Prozesse, die BC2 anfasst, gesperrt werden? — Nein: Historie statt Sperre

**Frage Simeons vom 03.09.:** *Müssen Prozesse, die von BC2 angefasst werden, gesperrt oder
eingefroren werden?* — und, nach der ersten Antwort: *BC2 liest nicht nur Zahlen, sondern das ganze
Portfolio. Dann brauchen wir ein Datum, mit dem wir das Paket zurück anzeigen können. Und dann
macht ein Foto der Werte keinen Sinn — sondern sofort R9.*

**Antwort, entschieden am 03.09.:** Nicht den Prozess sperren. Nicht ein Foto der Werte ins
Paket legen. Sondern **jede Änderung mit Zeitstempel und Zeilenbild festhalten** (R9 aus #148),
dann sagt das Datum am Paket alles: Das Paket sagt, *was* BC2 bekommen hat; die Historie sagt,
*wie es zu diesem Datum aussah*. Was BC2 darüber hinaus liest — Systeme, Rollen, Kette, das ganze
Portfolio — entscheidet er selbst, aus dem Paket heraus.

### Warum kein Sperren, und warum kein Foto

Ein Prozess, den BC2 rechnet, lebt weiter: Nacherhebung, Landkarte, zweite Anfrage. Eine Sperre
würde den Echtbetrieb blockieren, für den ADR-003 ausgelegt ist. Und BC2 rechnet nicht auf dem
Prozess, sondern auf dem **Paket** — wie ein Periodenabschluss: Man schließt den Monat, man sperrt
nicht das Konto.

Das Foto der dreißig Werte (erste Fassung dieses Abschnitts, `gate_stand_kopieren()`) war zu
klein: BC2 liest den ganzen Mandanten. Ein Foto des ganzen Mandanten je Paket wäre eine
Datenkopie je Übergabe — und würde später durch R9 ersetzt. **Zwischenschritte, die man wieder
ausbaut, sind der falsche Weg.** R9 stand seit Juni auf der Liste und ist die geforderte
Endform (ADR-003 Konsequenzen: *„Änderungshistorie ebenso — Pflicht statt Kür"*; ADR-005 R2/R3).

### Was gebaut ist — `schema_v2.6_historie_und_paket.sql`

| | Baustein | Mechanismus |
|---|---|---|
| **R9** | **Historie mit Zeilenbildern** | `audit_log` (seit v1.1, leer) bekommt `pk`, `alt`, `neu`, `txid`. Ein generischer Trigger `historie` auf **allen** Fachtabellen in `public` (dynamisch aus dem Katalog, 27 Tabellen; ausgenommen `app_benutzer`, `app_sitzungen`, `app_anmeldeversuche`, `audit_log`). `actor` aus der Sitzungsvariable `bc0.benutzer`, sonst der Datenbankbenutzer. **Klarnamen nie:** `historie_pii_entfernen()` streicht `name`, `email`, `telefon` aus `ref_personen`. Beim Einspielen eine **Bestandsaufnahme** jeder Zeile (`action = bestand`) — ab da ist die Historie vollständig |
| **ZR** | **Zeitreise** | `stand_zum(tabelle, datum[, mandant])` — je Zeile der letzte Eintrag vor dem Datum, gelöschte fehlen; vor `historie_beginn()` eine Fehlermeldung statt einer Schätzung. `bewertung_aktuell_zum()` und `reifegrad_tp_zum()` wenden die Regel von `v_bewertung_aktuell` auf einen Zeitpunkt an |
| **A** | **Erhebung einfrieren** | Trigger `erhebung_eingefroren`: kein INSERT/UPDATE/DELETE in eine abgeschlossene Erhebung; `erhebung_status_vorwaerts`: kein Wiederöffnen — verwerfen und neu beginnen |
| **B** | **Paket = Datum + Liste** | `gate_pakete` (`uebergeben_am`), `gate_paket_inhalt` (je TP: Freigabe-Ereignis, `anfrage_id` oder `NULL`, `bc1_profil_stand`, Hinweis), beide append-only per Trigger; `gate_paket_schnueren()` als eine Transaktion; Ereignis `uebergeben` am Unternehmen; Sichten `v_uebergabe_kandidaten` (Nachzügler) und `v_uebergabe_offen` (für BC2) |
| **D** | **Sichtbar statt verboten** | `v_stand_veraltet`: Änderungen seit Freigabe / seit Paket, gezählt aus der Historie (ohne `gate_*`), betroffene Tabellen, `stillgelegt`, `struktur_geaendert` |
| **F** | **Löschsperre** | `stilllegen_statt_loeschen` auf `ref_prozesse`/`ref_teilprozesse`; Kaskade vom Mandanten (DSGVO) läuft durch — die Historie bleibt, ohne Klarnamen |

**Und die App** (Patch `patch_v2.6.py`, nachvollziehbar Zeile für Zeile): `_erhebung_offen()`
schreibt nur noch in offene Erhebungen und sagt mit 400, warum nicht; das Gate liest den Stand
über `_erhebung_massgeblich()` ohne Nebenwirkung; die Middleware gibt den Benutzer über eine
Kontextvariable an die Verbindung, die ihn als `bc0.benutzer` setzt; sechs Endpunkte (Übergabe
lesen/schnüren, veraltet, widerrufen, Stand zum Datum, Historie); im Gate-0-Reiter der Block
**„Übergabe an BC2"** mit Kandidaten, Änderungen seit Freigabe, Knopf, Widerruf mit Grund,
bisherigen Paketen und **„Stand vom Paketdatum"**.

### Geprüft, nicht behauptet

PostgreSQL 16.13, komplette Schemafolge `v1.1.1` … `v2.5` aus dem Klon, dann v2.6 (zweimal —
wiederholbar, Bestand nicht doppelt), dann `pruefung_v2.6_historie_und_paket.sql` mit **20
Erwartungswerten, alle getroffen:**

| Probe | Ergebnis |
|---|---|
| Bestandsaufnahme | 105 Zeilen, `ref_personen` ohne `name`; Trigger auf 27 (+2 Pakettabellen) |
| Name und Stufe ändern, Stand zu t0 | `T1 alt`, 30 Zeilen aus **einer** Erhebung — heute `T1 neu`, 31 aus zwei; `actor = u1` |
| Zuordnung löschen | zu t0 da, heute nicht |
| Klarname ändern | **0** Klarnamen in der Historie; vor Historiebeginn: Fehlermeldung; `app_benutzer`: keine Historie |
| Erhebung abschließen, bewerten / wieder öffnen | beides abgewiesen, mit Satz |
| Freigabe → Paket → `v_uebergabe_offen` | Kandidat 1 → 0, Rang 1, `anfrage_id NULL`; `v_gate_freigabe_aktuell` unberührt |
| BC2 liest zum Paketdatum | Ø **3,07** über `reifegrad_tp_zum()` — heute wäre es 3,00 |
| Paket ändern, leeres Paket | abgewiesen |
| `v_stand_veraltet` nach einer Nacherhebung | 1 Änderung seit Freigabe, Tabelle `bitkom_bewertungen` |
| TP/KP löschen | abgewiesen; stilllegen geht |
| Mandant löschen | Kaskade läuft durch; Historie bleibt: 92 Zeilen, 44 `DELETE` |

Dazu die App: **254 Tests grün** (243 bestehende + 11 neue in `test_v26_einfrieren.py`, SQLite),
und ein Durchlauf über HTTP gegen PostgreSQL mit Anmeldung — Rating, Abschließen (400 mit Satz),
Freigabe, Paket, Stand zu t0 = 3,0 / zum Paketdatum = 3,07, Historie mit `actor` =
`benutzer_id`, Widerruf. Bildschirmfoto des Blocks im Gate-0-Reiter liegt bei S-108.

**Ein Fehler aus dem ersten Entwurf, den die Löschprobe fand:** Die FKs des Pakets auf
`gate_ereignisse` brauchten `ON DELETE CASCADE`, sonst scheitert die DSGVO-Löschung am Paket.
**Eine Löschprobe gehört in jedes Freeze-Skript.**

### Was bleibt

**C — das Profil** ist Richards Teil: `fertig` endgültig je `profil_version`, Nachschreiben legt
eine neue Version an, Freeze-Trigger in `bc1`. Unsere Historie reicht nicht in sein Schema; seine
Versionsnummer ist dort die Historie. Dazu ein **Anwendungskonto** für die drei Endpunkte vom
02.09.

**Für BC2 heißt es ab v2.6:** `v_uebergabe_offen` lesen, `uebergeben_am` nehmen, und dann
`stand_zum('<tabelle>', uebergeben_am, company_id)` für jede Tabelle, die er braucht — oder
`bewertung_aktuell_zum()` für die Bewertungen. Nachzügler kommen als neues Paket; ob er neu
rechnet, entscheidet er.

**Ausrollen:** `AUSROLLEN_v2.6_R9_04-09-2026.md` — Schritt 0 misst, Schritt 2 spielt ein, die
dritte Kontrollprobe (`stand_zum(now())` = `count(*)`) entscheidet, ob es weitergeht.

---

## 12. Nachtrag, spätabends — kann das Paket später ergänzt werden? Nein: die Anfrage wird nur vollständig übergeben

**Frage Simeons:** *Können wir das Paket, das wir nach Gate 0 an BC2 übermitteln, später noch
ergänzen? Eine Anfrage kann x Kernprozesse und y Teilprozesse beinhalten.*

Meine erste Antwort — Teillieferungen je Anfrage, mehrere Pakete, BC2 ergänzt — hat Simeon
zurückgewiesen: **BC2 würde den ROI falsch berechnen; die Freigabe erfolgt erst, wenn alles
vorhanden ist (Gate 0), und das ist grundlegende Voraussetzung.**

**Die Regel, wie sie jetzt gilt und gebaut ist (v2.7):** Übergeben wird eine Anfrage nur
**vollständig** — alle Teilprozesse, die zu ihr gehören, sind freigegeben; sonst gibt es kein
Paket. Nachzügler gibt es bei einer Anfrage nicht. Ändert sich der Umfang nach der Übergabe,
entsteht ein neues Paket der ganzen Anfrage, und BC2 rechnet neu. Der Portfolio-Weg ohne Anfrage
bleibt, dort bestimmt der Mensch die Liste ausdrücklich.

**Was das voraussetzt — und warum Punkt 115 damit kein Meeting-Punkt mehr ist:** Die Datenbank
muss wissen, welche Teilprozesse zu einer Anfrage gehören. Das ist `anfrage_prozesse` (n:m, genau
ein Hauptbezug, `NULL` im Teilprozess = ganzer Kernprozess), die SOLL-Liste der Übergabe. Ohne sie
keine Prüfung „7 von 7", ohne Prüfung kein Paket. Gebaut, gegen die Kette geprüft (17 Proben),
in der App (`PUT …/zuordnung` mit `bezuege`), in der Oberfläche („3 von 7 · es fehlen …", Knopf
nur bei vollständig). Dazu der Status **`uebergeben`** zwischen `am_gate` und `bewertet` — auf
Simeons Ansage („ja definitiv mit einbauen").

**Was offen bleibt:** Die Anfragemaske kennt `bezuege` noch nicht — mehrere Bezüge gehen heute
nur über den Endpunkt, also über BC1 im Interview. Und die Übernahme des Bestands macht aus einem
Bezug „nur Kernprozess" die Regel „alle fünf Teilprozesse" — bei NoroAI zu prüfen, ob das für
A-2026-01 bis -03 stimmt oder ob dort der eine zugeordnete Teilprozess gemeint war (dann `soll = 1`,
das ist bereits so übernommen).

---

## Belege

| Aussage | Fundstelle |
|---|---|
| ID-Regeln R1–R6, Muster, Mandantentrennung | `BC0_Datenbank_Dokumentation.md` v1.7, Abschnitt 2 |
| `erhebung_id` im PK, `v_bewertung_aktuell`, `v_erhebung_aktuell`, Status ohne Endpunkt | `schema_v1.3_teil_c_erhebungen.sql` §25–29 |
| `ref_anfragen`, `gate_ereignisse`-Spalten, `fk_gate_anfrage`, `ck_gate_massnahme`, Trigger, drei Sichten, Rechte | `schema_v1.4_gate0.sql` §14–20 |
| `objekt_id` ohne FK, `erhebung_id` als kopierter Wert — Begründung | ebenda, Kommentare §16 |
| v2.1: FKs `fk_anfrage_prozess` (RESTRICT), `fk_anfrage_teilprozess` (SET NULL), `ck_anfrage_tp_gehoert_kp`, `ck_anfrage_zuordnung_quelle`, `v_anfrage_prozessbezug` | `schema_v2.1_anfrage_prozessbezug.sql` |
| v2.2: `ck_teilprozess_step_no` 1–9, `aktiv`, `prozess_herkunft` (ohne FK auf TP), `ck_anfrage_status` mit `am_gate` vor `bewertet` | `schema_v2.2_landkarte_und_status.sql` |
| v2.3: `NOT NULL` zurück, `ck_anfrage_fortschritt_braucht_prozess`, `ck_anfrage_bezug_paarweise`, `umfang_geschaetzt`, `status` in der Sicht | `schema_v2.3_anfrage_ohne_prozessbezug.sql` |
| v2.4: fünf `REFERENCES` **nur an `bc1_role`**, Entzug der Doppelvergaben, Prüfung auf `bc_leser`-Mitgliedschaft | `schema_v2.4_rechte_bc1.sql` |
| v2.5: `app_anmeldeversuche` (Anmeldebremse) | `schema_v2.5_anmeldebremse.sql` |
| `_erhebung_offen()` ohne Statusfilter; `POST …/rating` ohne Statusprüfung; `companies.status` → `laeuft` | `app.py` 3116–3138, 1581–1595 |
| `POST …/erhebungen` (`abschliessen` · `neu` · `verwerfen`) | `app.py` 3163–3218 |
| `_bc1_angaben()` → `None`; `_gate_am_zug()` mit `wartet_bc1`, sperrt nichts | `app.py` 3699–3748 |
| Freigabe: `anfrage_id` optional, `erhebung_id = _erhebung_offen()`, kein `grundlage`, kein `bc1_profil_stand`; `Depends(admin)` | `app.py` 3922–4030 |
| `A-JJJJ-NN` höchste + 1 je Jahr | `app.py` 4129–4133 |
| `PUT …/zuordnung`, `PUT …/status` (kein Rücksprung, kein Fortschritt ohne Bezug), `POST …/prozesskanten` — alle `angemeldeter_benutzer` | `app.py` 4475, 4552, 4620; Commit `f5b4ada` 02.09. |
| `_bc1_angaben()` gibt `None`, Zweiteilung, „zwei Bedingungen" | Drehbuch S-085 |
| `bc1.prozessprofil` Zielstruktur, `status`, `profil_version`, Kaskade | `BC0_an_BC1_Antwort_22-08-2026.md`, Abschnitte 1–2 |
| Übergabe-Einheit Unternehmen, Poll statt Push, Nachzügler | `BC0_Trigger_an_BC2.md` (22.08.) |
| BC2 rechnet anhand der Anfrage; vier Berichtigungen | Drehbuch S-106, Abschnitt 2 |
| Weg (a) für Items und Zuordnung, kein `GRANT UPDATE` | `BC0_Prozessbezug_der_Anfrage.md` 2a, `BC0_Konzept_Anfrage_in_der_PWA.md` Hindernis 2 |
| E1–E8 der Landkarte, Ursprungs-ID, Bewertungen wandern nicht | `BC0_Prozesslandkarte_veraenderbar.md` |
| Zähler-Grenzen `E-JJJJ-MM`, `A-JJJJ-NN` | Drehbuch, Nachtrag 03.09. |
| elf Fremdschlüssel, vier lose Verbindungen, `REFERENCES ref_anfragen` fehlt | `BC0_DB_Abhaengigkeiten_03-09-2026.html` (berichtigte Fassung) |
| Punkte 65, 82, 96, 98, 115, 116 | `ToDo_Liste_aktuell.md`, `ToDoListe_PG-KI-CoE-KMU_DB.md` |
| v2.6 Historie und Paket, Szenario mit 20 Proben gegen PostgreSQL 16.13 | `schema_v2.6_historie_und_paket.sql`, `pruefung_v2.6_historie_und_paket.sql`, `patch_v2.6.py`, `tests/test_v26_einfrieren.py` im Klon |
| v2.7 Anfrage als Klammer, 17 Proben, 266 App-Tests, zwei HTTP-Durchläufe | `schema_v2.7_anfrage_prozesse_und_uebergabe.sql`, `pruefung_v2.7_anfrage_klammer.sql`, `patch_v2.7.py`, `tests/test_v27_anfrage_klammer.py` im Klon |

**Eine Berichtigung am Rande:** Der Abschnitt „Nebenbefund" in der ToDo-Liste vom 03.09. und
S-106 Abschnitt 4 nennen `ref_anfragen.process_id` und `gate_ereignisse → ref_anfragen` als
„nur Text" bzw. „existiert nicht". **Beides ist überholt** — die berichtigte Fassung der Grafik
vom selben Tag (12:30) weist beide als echte Fremdschlüssel nach (`fk_anfrage_prozess`,
`fk_anfrage_teilprozess`, `fk_gate_anfrage`); `fk_gate_anfrage` steht wörtlich in v1.4 §16. Die
Zahl der losen Verbindungen ist vier, nicht fünf. ToDo-Liste und S-106 sollten nachgezogen werden,
sonst geht der Fehler ins Meeting.
