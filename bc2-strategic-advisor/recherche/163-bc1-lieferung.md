# Was BC1 liefert — und was BC2 tut, wenn es ausbleibt

> **Recherche zu [#163](https://github.com/pg-coe-kmu/coe-factory/issues/163)** · Teil von [#158](https://github.com/pg-coe-kmu/coe-factory/issues/158) · **Stand: 30.08.2026**
> Datenbankstand gemessen am 30.08.2026 als `bc2_role` (PostgreSQL 17.6, Session-Pooler).
> Mandantenfilter durchgängig `company_id = 7c2d5ee9-2a9a-5990-810f-502ea2b2012d` (NoroAI).

## Kennzeichnung

| Marke | Bedeutung |
|---|---|
| **[gemessen]** | Aus der gemeinsamen Datenbank oder dem Dateisystem des Repos direkt abgefragt. Maßgeblich. |
| **[behauptet]** | Aussage eines Dokuments oder Issues. Nicht maßgeblich, wenn eine Messung widerspricht. |
| **[unsicher]** | Meine Deutung, nicht durch eine Messung gedeckt. Ausdrücklich als solche gekennzeichnet. |

## Kernbefund in drei Sätzen

BC1 liefert derzeit **nichts** — nicht über die Datenbank, nicht über `contracts/`, nicht als Code —
und ist unter den heutigen Rechten technisch **außerstande**, irgendwo außerhalb des leeren Schemas
`bc1` zu schreiben. Gleichzeitig hat BC0 in `ref_gate_pruefpunkte` **maschinenlesbar hinterlegt**,
dass genau die vier von BC2 benötigten Größen — `dauer`, `haeufigkeit`, `menge`, `rollen`
(Zeitanteil) — Pflicht sind und **aus BC1** kommen sollen. Und BC1s eigener Implementierungsplan
sieht für den MVP **ausdrücklich keine Datenbank vor**: selbst ein vollständig abgearbeitetes
`#120`–`#126` erzeugt einen In-Memory-Prototypen, der nichts persistiert.

---

## Frage 1 — Was liegt im Schema `bc1`?

**Antwort: nichts. Und BC1 schreibt auch nicht ersatzweise nach `public`.**

**[gemessen]** Das Schema `bc1` existiert, ist aber **vollständig leer** — nicht nur ohne Tabellen
und Views, sondern ohne jedes Objekt überhaupt:

```sql
select c.relkind, c.relname from pg_class c
  join pg_namespace n on n.oid = c.relnamespace where n.nspname = 'bc1';
-- 0 Zeilen  (keine Tabellen, Views, Sequenzen, Indizes, Typen)

select p.proname from pg_proc p
  join pg_namespace n on n.oid = p.pronamespace where n.nspname = 'bc1';
-- 0 Zeilen  (keine Funktionen)
```

Das Schema ist also **angelegt und zugeteilt, aber nie benutzt worden**. Eigentümer und Rechte
stehen bereit:

```sql
select nspname, pg_get_userbyid(nspowner), nspacl::text from pg_namespace
 where nspname in ('bc1','bc2','public');
```

| Schema | Eigentümer | ACL |
|---|---|---|
| `bc1` | `postgres` | `bc1_role=UC`, `bc_leser=U` |
| `bc2` | `postgres` | `bc2_role=UC`, `bc_leser=U` |
| `public` | `pg_database_owner` | `bc1_role=**U**`, `bc_leser=U` |

### Der eigentliche Fund: BC1 *kann* nicht nach `public` schreiben

Die Vermutung aus dem Auftrag, BC1 schreibe vielleicht in `public` statt ins eigene Schema, ist
**widerlegt** — und zwar strukturell, nicht nur empirisch:

**[gemessen]** `bc1_role` hat auf `public` nur `USAGE`, **kein `CREATE`** (ACL oben) — kann dort also
keine Tabelle anlegen. Und auf allen 26 vorhandenen Basistabellen hat es ausschließlich `SELECT`:

```sql
select t.table_name,
  has_table_privilege('bc1_role','public.'||quote_ident(t.table_name),'SELECT') as sel,
  has_table_privilege('bc1_role','public.'||quote_ident(t.table_name),'INSERT') as ins,
  has_table_privilege('bc1_role','public.'||quote_ident(t.table_name),'UPDATE') as upd
from information_schema.tables t
where t.table_schema='public' and t.table_type='BASE TABLE';
```

Ergebnis: **26 von 26 Tabellen `sel=true, ins=false, upd=false`** — ausnahmslos, auch
`medienbrueche`. `bc1_role` ist Mitglied von `bc_leser` und erbt von dort ausschließlich Leserechte
(`pg_auth_members`). BC1 ist damit unter der heutigen Rechtevergabe **technisch außerstande**,
irgendetwas in `public` zu erzeugen oder zu ändern. Der einzige Ort, an dem BC1 überhaupt schreiben
dürfte, ist das leere Schema `bc1`.

### Gibt es Spuren, dass BC1 je geschrieben hat?

**[gemessen]** Nein. Sämtliche Tabellen, die eine BC1-Aktivität anzeigen würden, sind leer:

| Tabelle | Zeilen | Bedeutung |
|---|---|---|
| `gate_ereignisse` | **0** | trägt `bc1_profil_stand` — der einzige BC1-Slot in `public` |
| `gate_pruefpunkt_werte` | **0** | die Prüfpunktwerte, die BC1 füllen soll (s. Frage 3) |
| `medienbrueche` | **0** | s. Frage 5 |
| `audit_log` | **0** | keinerlei protokollierte Schreibvorgänge |
| `prozess_herkunft` | 0 | |
| `prozess_schnittstellen` | 0 | |
| `profile_documents`, `beleg_dokumente`, `bewertung_belege` | 0 | |

### Sieht irgendetwas in `public` inhaltlich nach BC1 aus?

**[gemessen]** Ich habe alle Spalten in `public` nach BC1-typischen Begriffen durchsucht:

```sql
select table_name, column_name from information_schema.columns
where table_schema='public'
  and column_name ~* 'profil|interview|konfidenz|confidence|session|vollstaend
                      |ungeloest|schema_version|discovery|bc1|chat|dialog|extrakt';
```

Sieben Treffer — **keiner davon ist ein BC1-Erzeugnis**:

| Treffer | Einordnung |
|---|---|
| `gate_ereignisse.bc1_profil_stand` (text) | **der einzige vorgesehene BC1-Slot.** Freitext, kein strukturiertes Profil. Tabelle leer. |
| `company_profile.profile_json` (jsonb) | **von BC0**, nicht BC1 — s. u. |
| `beleg_dokumente.ocr_confidence` | BC0s OCR-Pfad, Tabelle leer |
| `v_gate_bogen.vollstaendig_bewertet`, `v_gate_vorbedingungen.vollstaendig_bewertet`, `v_gate_freigabe_aktuell.bc1_profil_stand` | abgeleitete Views |

`company_profile.profile_json` weist sich selbst als BC0-Erzeugnis aus:

```json
"meta": { "quelle": "NoroAI_Unternehmensprofil_v6.0.md", "version": "v6.0",
          "konvertiert_am": "2026-06-28T...", "konvertiert_von": "BC0 / convert_v6_to_json.py" }
```

Es ist die maschinelle Konversion des Unternehmensprofil-Markdowns, **kein Interview-Ergebnis**.

**Fazit Frage 1:** Im Schema `bc1` liegt nichts, in `public` liegt nichts von BC1, und es gibt keine
Spur, dass je etwas geschrieben wurde. Die Datenbank hält für BC1 genau **einen** Platz frei —
`gate_ereignisse.bc1_profil_stand`, eine Freitextspalte in einer leeren Tabelle.

---

## Frage 2 — Was sagen BC1s Dokumente, und deckt sich das mit der DB?

**Antwort: Die Dokumente beschreiben einen anderen Ablieferungsweg als die Datenbank — und der MVP-Plan sieht überhaupt keine Datenbank vor.**

### Was die Dokumente behaupten

**[behauptet]** `bc1-context-discovery/README.md` (Z. 11) und `design/Design-Spec.md` (Z. 12):

> **Produced:** Prozessprofil (JSON), Confidence-Report, Prozessdoku → `contracts/bc1-to-bc2/`

**[behauptet]** `design/Design-Spec.md` B3 (Z. 73–75): Der Output trägt
`{ profil, vollstaendigkeit, ungeloeste_felder[], schema_version }` und geht über **Gate 0** an BC2.

**[behauptet]** `architektur/BC1_Systemarchitektur.md` (Z. 20, Mermaid): `n8n --> DB[("DB · Platform")]`
— die Persistenz liegt bei n8n/Platform, ausdrücklich **nicht** bei BC1
(`B8`: *„Liegt NICHT bei BC1: DB-Tabellen/Infra … → Platform"*).

### Was gemessen ist

**[gemessen] Der Ablageort existiert nicht.** `find contracts -type f` liefert:

```
contracts/README.md
contracts/bc3 - bc4/…   (7 Dateien)
```

Es gibt **kein Verzeichnis `contracts/bc1-to-bc2/`**. Der in README und Design-Spec zugesagte
Ablieferungsort ist nie angelegt worden.

**[gemessen] BC1 hat keinen Code.** Unter `bc1-context-discovery/` liegen genau fünf Dateien, alle
Markdown (README, CLAUDE.md, Design-Spec, Implementierungsplan, Systemarchitektur). Kein `.py` im
gesamten Verzeichnis; die einzigen Python-Dateien im Repo gehören BC0.
Letzte Commits am Verzeichnis: `bf51a47` und `0eaebad` — beide `docs(bc1)`, reine Dokumentation.

### Der schwerwiegendste Punkt: der MVP schreibt bauartbedingt nichts

**[behauptet, aber entscheidend]** `design/Implementierungsplan-MVP-Kern.md` legt fest (Z. 8):

> **Architecture:** … **Keine n8n-, Netz- oder DB-Abhängigkeit im MVP.**

und in der Dateiliste (Z. 30):

> `bc1_core/store.py` — `StateStore` (abstrakt) + **`InMemoryStateStore`** (versioniert)

Der persistente Store steht ausdrücklich außerhalb des Plans (Z. 920–924,
*„Roadmap-Anker (NICHT Teil dieses Plans)"*):

> - **n8n-Hülle** vor `process_turn` (Chat-Trigger, Persistenz an die geteilte Platform-DB …)
> - **Persistenter `StateStore`** (Platform-DB) statt In-Memory.
> - **BC1→BC2-Vertrag** in `contracts/bc1-to-bc2/` …

**Konsequenz für BC2:** Die neun Tasks des Plans entsprechen den Issues **#120–#126**. Selbst wenn
BC1 **alle** davon vollständig und fehlerfrei abarbeitet, ist das Ergebnis ein
**In-Memory-CLI-Prototyp**, der weder in die Postgres noch nach `contracts/` schreibt. Der Weg in
die gemeinsame Datenbank ist ein *nachgelagertes, ungeplantes, unticketiertes* Vorhaben.

**Fazit Frage 2:** Die Dokumente decken sich **nicht** mit der DB — nicht weil sie veraltet sind,
sondern weil sie einen anderen Übergabeweg (Datei in `contracts/`, Persistenz durch Platform/n8n)
beschreiben als den, den BC0 inzwischen gebaut hat (gemeinsame Postgres, Prüfpunkte am Gate).
Beide Wege sind heute unbenutzt.

---

## Frage 3 — Liefert BC1 die Aufwandsgrößen überhaupt?

**Antwort: Die Datenbank verlangt sie ausdrücklich von BC1. BC1s eigene Dokumente sagen sie nirgends zu.**

### Was die Datenbank von BC1 verlangt — der wichtigste Fund dieser Recherche

**[gemessen]** Die Tabelle `ref_gate_pruefpunkte` (9 Zeilen) ist BC0s **maschinenlesbarer Vertrag**
darüber, wer welche Größe schuldet. Sie wird in keinem BC2-Dokument erwähnt:

```sql
select pruefpunkt, bezeichnung, quelle_bc, guete_noetig, pflicht, aktiv
from ref_gate_pruefpunkte order by reihenfolge;
```

| Prüfpunkt | Bezeichnung | quelle_bc | guete_noetig | pflicht | aktiv |
|---|---|---|---|---|---|
| **`dauer`** | Dauer je Ausführung | **BC1** | true | true | true |
| **`haeufigkeit`** | Ausführungen je Zeitraum | **BC1** | true | true | true |
| **`menge`** | Menge je Ausführung | **BC1** | true | true | true |
| **`rollen`** | Beteiligte Rollen mit Zeitanteil | **BC1** | true | true | true |
| `kosten` | Kostensatz je beteiligter Rolle | BC0 | true | true | true |
| `prozessbeschreibung` | Prozessbeschreibung | BC0 | false | true | true |
| `medienbrueche` | Medienbrüche erfasst | **BC0** | false | true | true |
| `ansprechpartner` | Ansprechpartner bei Rückfragen | BC0 | false | true | true |
| `zulaessigkeit` | Zulässigkeit der Automatisierung | BC0 | false | true | **false** |

Das sind **exakt die vier Größen**, die #163 als BC2s Bedarf nennt — Häufigkeit, Dauer, Menge,
Zeitanteil je Rolle — und sie sind alle vier `pflicht = true`, `guete_noetig = true` und
`quelle_bc = BC1`. Die Erläuterungen sind unmissverständlich:

> `dauer`: „Bearbeitungszeit eines Durchlaufs. **Ohne sie gibt es keinen Jahresaufwand und damit
> keinen ROI.**"
> `rollen`: „Welche Rolle wie lange beteiligt ist. **Paare (rolle_id, zeitanteil)**, nicht
> Namensliste."

BC0 hat die Abhängigkeit also gesehen, benannt und im Schema verankert. **Die zugehörige Wertetabelle
`gate_pruefpunkt_werte` ist leer (0 Zeilen).**

### Was BC1s Dokumente zusagen

**[gemessen an den Dokumenten]** Nichts davon. Die Design-Spec beschreibt ein „strukturiertes
Prozessprofil", **ohne die Felder zu benennen** — bewusst:

> *B6:* „Die Plug-Stelle ist ein **deklaratives Use-Case-Paket**: Zielfelder + Typen, …"
> *Leitprinzip 4:* „**Generisch bis die Use Cases feststehen**, dann lokal spezialisieren."

Die Felderliste ist also **absichtlich leer gelassen** und in ein Use-Case-Paket ausgelagert, das es
noch nicht gibt (Design-Spec B8, Zeile „Use Cases definiert → Use-Case-Paket(e) befüllen").

**[gemessen]** `haeufigkeit` kommt im gesamten Implementierungsplan vor — aber **ausschließlich in
einer Spielzeug-Fixture** (Z. 204–213):

```python
TOY_PROZESS = UseCasePackage(
    name="toy_prozess", schema_version="0.1",
    fields=[ FieldSpec("prozess_name", "Wie heißt der Prozess?"),
             FieldSpec("ausloeser",   "Was löst den Prozess aus?"),
             FieldSpec("haeufigkeit", "Wie oft kommt er vor?",
                       validator=lambda v: any(c.isdigit() for c in v)),
             FieldSpec("notiz", "Sonstige Hinweise?", required=False) ])
```

Alle 13 Fundstellen (Z. 160, 167, 209, 348, 353, 361, 364, 519, 524, 626, 636, 744, 892) liegen in
Tests oder in dieser Fixture. Der Validator prüft lediglich, ob **irgendeine Ziffer** vorkommt —
„100 mal" gilt als gültig. Das ist ein Platzhalter zum Beweis der Generik-Naht, **keine fachliche
Zusage**.

**[gemessen]** `dauer`, `menge` und `zeitanteil` kommen in **keinem** BC1-Dokument vor
(Volltextsuche über alle fünf Dateien).

**Fazit Frage 3:** Die Antwort auf „steht dort explizit Frequenz/Dauer/Menge drin?" lautet **nein**.
BC1 hat sich nie verpflichtet, diese Größen zu liefern; sein Design ist bewusst feldfrei. Die
Verpflichtung existiert nur auf BC0s Seite, in `ref_gate_pruefpunkte`. **[unsicher]** Ob BC1 diese
Tabelle überhaupt kennt, kann ich nicht feststellen — sie wird in keinem BC1-Dokument erwähnt, und
die BC1-Dokumente sind vom 23.06., die Prüfpunkte deutlich jünger.

---

## Frage 4 — Ist der F1-Widerspruch aus #95 noch relevant?

**Antwort: Er ist innerhalb BC1s Dokumenten längst entschieden, praktisch gegenstandslos — aber die gemeinsame Datenbank hat ihn nicht *überholt*, sondern durch einen anderen Mechanismus *ersetzt*.**

**[behauptet]** Die Design-Spec entscheidet die Frage selbst, in B8:

> **Liegt NICHT bei BC1:** … · **F1 → Offline-Gütemaß, kein Laufzeit-Gate.**

und hält den Abgleich mit BC2 als offenen Punkt fest (B8-Tabelle, Bezug #95):
*„Confidence-Semantik — finaler Abgleich mit BC2 (Status + Vollständigkeit; F1 offline)"*.

**[gemessen]** Im Implementierungsplan kommt „F1" **kein einziges Mal** vor. Die dort gebaute
Vollständigkeit ist eine gezählte Quote (`erfüllte Pflichtfelder / Pflichtfelder gesamt`) plus
Status-Enum — kein F1, keine Wahrscheinlichkeit. Die Architektur-Invariante in
`bc1-context-discovery/CLAUDE.md` (Z. 57) bekräftigt: *„Keine erfundenen Confidence-Zahlen"*.

**[gemessen]** In der Datenbank gibt es **keine F1-, Score- oder Confidence-Spalte** für Prozesse.
Die einzige `confidence`-Spalte ist `beleg_dokumente.ocr_confidence` (BC0s OCR-Pfad, Tabelle leer).

### Was die Datenbank stattdessen eingeführt hat

**[gemessen]** BC0 hat am Gate einen **anderen** Güte-Mechanismus gebaut:

```sql
-- gate_pruefpunkt_werte (0 Zeilen)
ereignis_id bigint NOT NULL      -- hängt an gate_ereignisse (ebenfalls 0 Zeilen)
pruefpunkt   text   NOT NULL
vorhanden_pct numeric            -- „wie viel liegt vor" in Prozent
guete         text               -- Güte-Flag, FREITEXT ohne Enum-Zwang
bestaetigt    boolean NOT NULL   -- der Mensch bestätigt
anmerkung     text
```

Das ist der Form nach **dasselbe Konzept** wie BC1s `vollstaendigkeit` + Status: eine gezählte
Vollständigkeit plus eine Güteangabe plus menschliche Bestätigung. Beide Seiten sind kompatibel
gedacht, aber **niemand hat sie verdrahtet**.

**[gemessen]** Bemerkenswert: `guete` ist **reiner Text ohne Enum**. Die vier Enums in `public`
(`beleg_source`, `doc_status`, `onboarding_status`, `process_category`) enthalten kein
Güte-Vokabular. Das Vokabular `belegt/geschaetzt/geraten` ist also **Konvention, nicht Schema** —
belegt durch `rollen_kostensaetze.quelle = 'geschaetzt'` (Text). Für BC2 heißt das: **`geraten` als
Güte-Flag ist frei verwendbar, kein Constraint steht dagegen.**

**Fazit Frage 4:** Der ursprüngliche Widerspruch (F1 als Laufzeit-KPI pro Anfrage vs. Offline-Gütemaß)
ist **nicht mehr die relevante Frage**. Er ist dokumentenseitig zugunsten „offline" entschieden und
mangels Laufzeitpfad ohnehin gegenstandslos. Die relevante Nachfolgefrage lautet: **Wie füllt sich
`gate_pruefpunkt_werte`, wenn BC1 nicht liefert?** — das gehört zu #166 und #165, nicht mehr zu F1.
Die Formulierung „hat die gemeinsame Datenbank die Frage überholt" trifft es nur halb: die Datenbank
hat die Frage **ausgetauscht**.

---

## Frage 5 — Wie füllt BC1 `medienbrueche`?

**Antwort: Gar nicht. BC1 darf es nicht, und laut Datenbank ist es auch gar nicht BC1s Aufgabe.**

Hier weicht der gemessene Befund **von der Prämisse der Frage ab**. Die Frage unterstellt
(#163, Frage 5): *„BC0 hat die Tabelle angelegt, füllt sie aber nicht — laut BC0 ist das BC1s
Aufgabe."*

**[gemessen] Die Datenbank sagt das Gegenteil.** In `ref_gate_pruefpunkte`:

| pruefpunkt | quelle_bc | guete_noetig | erlaeuterung |
|---|---|---|---|
| `medienbrueche` | **BC0** | false | „Register aus Schema v1.3 Teil B. **Leer kann richtig sein — dann bestätigt der Mensch die Null.**" |

BC0 ordnet den Prüfpunkt also **sich selbst** zu, nicht BC1 — und sieht ausdrücklich vor, dass eine
leere Tabelle ein **gültiger Zustand** ist, den ein Mensch bestätigt. **[unsicher]** Möglicherweise
gab es eine frühere mündliche Aussage von BC0, die #163 zitiert; maßgeblich ist die Tabelle.

**[gemessen] BC1 könnte es ohnehin nicht.** `has_table_privilege('bc1_role','public.medienbrueche','INSERT')`
= **false** (s. Frage 1). Ein Schreibvorgang von BC1 in diese Tabelle ist unter den heutigen Rechten
ausgeschlossen.

**[gemessen] Die Tabelle ist leer, für beide Mandanten:**

```sql
select * from medienbrueche;  -- 0 Zeilen
```

Ihre Struktur ist für BC2 dennoch bemerkenswert:

| Spalte | Typ |
|---|---|
| `company_id`, `bruch_id`, `sub_process_id` | Schlüssel |
| `von_system_id`, `nach_system_id`, `art`, `beschreibung` | Beschreibung |
| **`aufwand_min`** | **numeric** |
| `aktiv` | boolean |

**`medienbrueche.aufwand_min` ist die einzige numerische Aufwandsspalte in ganz `public`.**
Vollständige Spaltensuche über alle 26 Tabellen und 22 Views nach
`haeufig|frequenz|dauer|menge|volumen|zeitanteil|aufwand|umfang|fte|stunden|minuten` ergab genau
vier Treffer: `medienbrueche.aufwand_min` (numeric, leer),
`ref_anfragen.umfang_geschaetzt` (text), `ref_anfragen.erhofftes_ziel` (text) und
`v_prozess_personen_lesen.kostenklasse` (text). **Es gibt in der gesamten Datenbank keine gefüllte
numerische Aufwandsgröße.**

### Ein Widerspruch *innerhalb* der Datenbank — Falle für BC2

**[gemessen]** Zwei Views beantworten dieselbe Frage unterschiedlich:

| View | Spalte | KP-01…04 | KP-05/06 |
|---|---|---|---|
| `v_gate_prozessstand` | `tp_mit_medienbruch` | **5** | 0 |
| `v_system_abdeckung` | `anz_medienbrueche` | **0** | 0 |

Der Grund steht in den View-Definitionen (`pg_get_viewdef`):

```sql
-- v_system_abdeckung: zählt Zeilen der (leeren) Tabelle
LEFT JOIN medienbrueche mb ON mb.company_id = tp.company_id
     AND mb.sub_process_id = tp.sub_process_id AND mb.aktiv
COALESCE(z.anz_brueche, 0) AS anz_medienbrueche

-- v_gate_prozessstand: prüft nur, ob eine FREITEXTSPALTE nicht leer ist
rt.medienbrueche IS NOT NULL AND length(btrim(rt.medienbrueche)) > 0 AS hat_medienbruch
count(*) FILTER (WHERE tp.hat_medienbruch) AS tp_mit_medienbruch
```

`v_gate_prozessstand` zählt also **keine Medienbrüche**, sondern nur, ob jemand in
`ref_teilprozesse.medienbrueche` (Text) etwas hineingeschrieben hat. Und der Inhalt sagt teilweise
das **Gegenteil** dessen, was gezählt wird:

**[gemessen]** `ref_teilprozesse` für NoroAI, Füllgrad: 50 Zeilen, davon `notation` 50,
`tools` 20, `medienbrueche` 20, `schnittstellen` 20, `api` **0**. Der Text ist **pauschal je
Kernprozess** — alle fünf Teilprozesse von KP-01 tragen wortgleich:

> `medienbrueche` = **„Wenige Medienbrüche im Standard-Fall"**

Diese Aussage wird von `v_gate_prozessstand` als „hat Medienbruch" gezählt — für alle fünf
Teilprozesse. **Wer `tp_mit_medienbruch = 5` für bare Münze nimmt, rechnet mit einer Zahl, die das
Gegenteil ihrer Quelle behauptet.** `v_system_abdeckung` markiert die Lage korrekt mit dem Befund
`„nur pauschal je kernprozess"`.

**Fazit Frage 5:** `medienbrueche` wird nicht gefüllt, BC1 darf es nicht und soll es laut
`ref_gate_pruefpunkte` auch nicht. Die einzige vorhandene Medienbruch-Information ist unstrukturierter,
pauschaler, teils gegenteiliger Freitext bei 20 von 50 Teilprozessen. Für BC2 ist
`v_gate_prozessstand.tp_mit_medienbruch` **nicht verwendbar** ohne Blick in den Quelltext.

---

## Frage 6 — Realistischer Stand und Plan B

> Frage 6 ist laut Ticket die wichtigste. **Sie ist eine Entscheidung, keine Recherchefrage — ich
> entscheide sie hier ausdrücklich nicht.** Was folgt, ist die Grundlage dafür: was fehlt, welche
> Optionen es gibt, was jede kostet.

### 6a. Der realistische Stand von BC1 — [gemessen]

| Beleg | Befund |
|---|---|
| Issues `#120`–`#126` („BC1-Kern") | **7 von 7 offen**, angelegt 23.06.2026, seither unverändert |
| Issues `#48`–`#53` (KI-Interviewer, Voice/OCR, PII, JSON-Compiler, Doku, Mapper) | **6 von 6 offen** |
| BC1-Issues gesamt (`gh issue list --label bc1 --state all`) | 14, davon **13 offen**; die eine geschlossene (#95) wurde **von BC2** geschlossen |
| Code unter `bc1-context-discovery/` | **0 Zeilen** — fünf Markdown-Dateien, sonst nichts |
| Letzte Commits am Verzeichnis | `bf51a47`, `0eaebad` — beide reine `docs(bc1)` |
| Schema `bc1` | **0 Objekte** |
| Schreibrechte außerhalb `bc1` | **keine** |
| Ablageort `contracts/bc1-to-bc2/` | **existiert nicht** |
| Selbst bei voller Fertigstellung von #120–#126 | In-Memory-CLI, **keine DB-Persistenz** (Plan: „Roadmap-Anker, NICHT Teil dieses Plans") |

**[unsicher]** Zu Personen und Terminen sage ich nichts: die Zeitpläne aller Altdokumente sind laut
#158 ungültig, und ich habe keine Quelle zum aktuellen Arbeitsstand des BC1-Teams außerhalb des
Repos. Der Repo- und DB-Befund lässt aber nur einen Schluss zu: **BC2 muss für seine Planung von
null Lieferung ausgehen.**

### 6b. Was BC2 konkret fehlt — [gemessen]

Für die **sechs bewerteten Kernprozesse** KP-01 … KP-06 (die vier übrigen sind nicht erhoben):

| Größe | Prüfpunkt | Wo sie stehen müsste | Gemessener Zustand |
|---|---|---|---|
| **Häufigkeit** (Ausführungen/Zeitraum) | `haeufigkeit` (BC1, Pflicht) | `gate_pruefpunkt_werte` | **leer** · einziger Wert überhaupt: `ref_anfragen.umfang_geschaetzt = "5x pro Monat"` — **Freitext**, an **einer** Anfrage (A-2026-04), die **keinem Prozess zugeordnet** ist |
| **Dauer** (je Ausführung) | `dauer` (BC1, Pflicht) | `gate_pruefpunkt_werte` | **leer** · einzige numerische Aufwandsspalte `medienbrueche.aufwand_min` ist **0 Zeilen** |
| **Menge** (je Ausführung) | `menge` (BC1, Pflicht) | `gate_pruefpunkt_werte` | **leer** · nirgends vorhanden |
| **Zeitanteil je Rolle** | `rollen` (BC1, Pflicht) | `gate_pruefpunkt_werte` | **leer** · `v_prozess_personen_lesen` liefert *wer* + Kostenklasse, **aber keinen Zeitanteil** |

Drei Gegenproben, damit die Lücke belegt und nicht bloß behauptet ist:

1. **[gemessen] Die 30 Bitkom-Items messen keine davon.** `select * from ref_items` — alle 30 sind
   ordinale Reifegradfragen („Inwieweit …", „In welchem Maß …") zu Technologie, Prozessdaten,
   Prozessqualität, Kunden, Skills. **Keine einzige** fragt nach Häufigkeit, Dauer, Menge oder
   Zeitanteil. Die 690 Bewertungen für NoroAI lassen sich daher **nicht** in Aufwand umrechnen.
2. **[gemessen] Das Unternehmensprofil enthält sie nicht.** In
   `company_profile.profile_json → profil → „4. Interne Geschäftsprozesse von NoroAI"` (17.717 Zeichen)
   ergab die Suche nach `pro (Tag|Woche|Monat|Quartal|Jahr)` **null Treffer**. Die Zeitangaben im
   Gesamtprofil („15 Min", „4 h", „40 h") sind Reaktions-SLAs, Meeting-Takte und Schulungsumfänge —
   **keine Prozessdurchlaufzeiten**. **[unsicher]** Ich habe stichprobenartig geprüft, nicht jede der
   15 Fundstellen einzeln fachlich eingeordnet.
3. **[gemessen] `ref_anfragen` trägt die Größen nur rudimentär.** Von vier Anfragen hat **eine**
   (A-2026-04, `eingang_weg='pwa'`) überhaupt `umfang_geschaetzt`, `erhofftes_ziel`, `ausloeser`
   gefüllt; die drei Testdaten-Anfragen haben alle drei Felder **leer**. A-2026-04 hat zudem
   `process_id = NULL` — die eine echte Häufigkeitsangabe hängt an keinem Prozess.

### 6c. Was BC2 dagegen *hat* — [gemessen]

Die Wertrechnung ist **Menge × Zeit × Satz**. Der **Satz** liegt vor, die **Mengen- und Zeitachse
fehlt vollständig**:

| Vorhanden | Inhalt |
|---|---|
| `v_rollen_kostensaetze_aktuell` | K1–K5 = 40 / 55 / 68 / 95 / 140 EUR/h · `quelle = geschaetzt` · gültig ab 17.08.2026 |
| `mandant_rollen` | 6 Rollen R-01…R-06 mit Kostenklasse |
| `v_prozess_personen_lesen` | Person ↔ Prozess ↔ Rolle ↔ Kostenklasse (ohne Zeitanteil) |
| `v_prozessautomatisierung` | 43 Zeilen, je Teilprozess 6 Dimensionen als Dezimalwert (`technologiebasis`, `tools_im_prozess`, `systemintegration`, `prozessbeschreibung`, `ausfuehrung`, `compliance`) |
| `v_gate_prozessstand` | Reifegrad je KP, schwächster TP, `items_unter_3`, BC0-Sperre |
| `ref_teilprozesse` | 50 TP mit `notation` (Aktivitätsfolgen) durchgängig gefüllt; `tools`/`schnittstellen` für KP-01…04 |

**Wichtige Einschränkung [gemessen]:** Die Erhebung `E-2026-08`, die KP-05 und KP-06 nachgezogen hat,
trägt `status = 'offen'`, `methode = 'gesetzt'` und den Hinweis: *„Keine Erhebung im fachlichen Sinn.
Die Stufen sind **gesetzt**, damit die drei Fokus-Teilprozesse die im Team genannten Reifegrade
tragen."* KP-05/KP-06-Werte sind also **gesetzt, nicht erhoben**.

### 6d. Optionen für Plan B — mit Kosten und geopferter Aussagekraft

Vier Optionen aus dem Ticket plus eine fünfte, die mir beim Lesen aufgefallen ist.
**Nicht entschieden — zur Entscheidung vorgelegt.**

---

**Option A — Eigene Erfassungsmaske in BC2**
*Der Mensch trägt die vier Größen je Kernprozess selbst ein; BC2 speichert sie in Schema `bc2`.*

- **Machbar?** Ja. `has_schema_privilege('bc2','CREATE') = true` (#159). Die Zielstruktur ist bereits
  vorgezeichnet: `gate_pruefpunkt_werte` (`pruefpunkt`, `vorhanden_pct`, `guete`, `bestaetigt`,
  `anmerkung`) lässt sich in `bc2` spiegeln — dann ist der spätere Umzug nach `public`, falls BC0
  Schreibrechte gewährt, ein reines Kopieren.
- **Kosten:** Frontend-Aufwand (Maske, Validierung, Persistenz) + Schema-Entwurf in `bc2` +
  **Bedienzeit eines Menschen**: 4 Größen × 5 Teilprozesse × 6 Kernprozesse = **120 Eingaben**;
  beschränkt auf die drei BC0-sauberen Prozesse (KP-02/03/04) sind es 60.
- **Geopfert:** BC2 übernimmt eine **Erhebungsaufgabe, die fachlich BC1 gehört** — Doppelarbeit,
  wenn BC1 doch liefert, und ein Zuständigkeitskonflikt an der Kontextgrenze. Die Zahlen sind zudem
  nur so gut wie der Ausfüller; ohne Beleg bleiben sie `geschaetzt`.
- **Nebenwirkung:** BC2 wäre damit **autonom lauffähig** und nicht mehr von BC1 blockiert.

---

**Option B — Annahmen mit Güte-Flag `geraten`**
*BC2 setzt Standardwerte je Prozesstyp und kennzeichnet sie durchgängig.*

- **Machbar?** Ja, und **schemaseitig ungehindert**: `guete` ist Freitext ohne Enum (Frage 4), das
  Vokabular ist bereits durch `rollen_kostensaetze.quelle = 'geschaetzt'` etabliert. `geraten` fügt
  sich nahtlos ein.
- **Kosten:** Am geringsten — nur eine Annahmentabelle und die konsequente Weitergabe des Flags bis
  in Präsentation und `contracts/bc2-to-bc3/`.
- **Geopfert:** **Die Belastbarkeit der Value-Aussage.** Ein ROI aus geratener Häufigkeit **und**
  geratener Dauer **und** geratener Menge multipliziert drei Ratewerte — der Fehler multipliziert
  sich mit. Gegenüber Prof. Dorka und BC3 ist das nur vertretbar, wenn das Flag **nirgends**
  verlorengeht.
- **Risiko:** Verstößt gegen den Geist von BC1s Leitprinzip *„Keine erfundenen Zahlen"* — dort
  allerdings für BC1 formuliert, nicht für BC2.

---

**Option C — Bandbreiten statt Punktwerten**
*Min/Max je Größe, so weit gespannt, dass sie ehrlich bleiben.*

- **Machbar?** Ja — und **bereits entschieden**: #158 hält fest *„Bandbreiten statt Punktwerten,
  gestützt auf BC0s Güte-Flags"*. Die Option ist damit nicht neu, sondern die geltende Linie.
- **Der Haken [gemessen]:** Die Entscheidung stützt sich auf „BC0s Güte-Flags" — und
  `gate_pruefpunkt_werte` ist **leer** (0 Zeilen bei 9 Prüfpunkten). **Die Stütze, auf die #158 baut,
  existiert nicht.** Bandbreiten brauchen einen Anker; ohne Häufigkeit/Dauer/Menge ist auch die
  untere Grenze frei erfunden.
- **Kosten:** Rechenwerk auf Intervallen statt Skalaren (deterministisch in Python, passt zur
  LLM-Rolle aus #158) + Darstellung von Intervallen in der Präsentation.
- **Geopfert:** **Priorisierbarkeit.** Wenn die Bandbreiten breit genug sind, um ehrlich zu sein,
  überlappen sie sich — dann lässt sich nicht mehr sagen, welches Potenzial das größere ist. Das ist
  genau die Frage, die BC2 beantworten soll. **Bandbreiten allein lösen das Problem nicht**, sie
  machen es sichtbar.

---

**Option D — Top-down aus Rollenkapazität** *(nicht im Ticket genannt; beim Lesen aufgefallen)*
*Statt bottom-up je Prozessdurchlauf zu rechnen, den Jahresaufwand von oben verteilen.*

- **Idee:** `v_prozess_personen_lesen` sagt, **wer** an welchem Kernprozess beteiligt ist und mit
  welcher Kostenklasse; das Unternehmensprofil nennt **zehn Mitarbeitende** mit Funktionen. Aus
  Kopfzahl × Jahresarbeitszeit × Kostensatz ergibt sich ein **Gesamtpersonalaufwand**, der sich über
  einen geschätzten Zeitanteil auf die Kernprozesse verteilen lässt.
- **Vorteil:** Braucht **nur eine** geschätzte Größe (den Zeitanteil je Rolle und Prozess) statt
  drei — die Fehlerfortpflanzung ist deutlich kleiner als bei Option B. Und der Zeitanteil ist genau
  der Prüfpunkt `rollen`, den BC1 ohnehin schuldet: was BC2 hier schätzt, ist später **1:1 durch
  BC1s Wert ersetzbar**.
- **Kosten:** Verteilungsmodell + Plausibilisierung; die Summe über alle Prozesse muss die
  Gesamtkapazität ergeben (eine **eingebaute Konsistenzprüfung**, die Option B fehlt).
- **Geopfert:** **Die Granularität unterhalb des Kernprozesses.** Eine Aussage je Teilprozess ist so
  nicht belastbar — und `v_prozessautomatisierung` liefert die Potenziale gerade **je Teilprozess**.
  Ebenso keine Aussage je einzelnem Durchlauf, also kein „spart X Minuten pro Vorgang".
- **[unsicher]** Ich habe nicht geprüft, ob das Unternehmensprofil eine belastbare Jahresarbeitszeit
  oder Kapazitätsverteilung enthält. Kapitel 9 („Wirtschaftlichkeit Geschäftsjahr 2026", 3.642
  Zeichen) und Kapitel 7 („Team, Rollen, Skill-Matrix", 13.052 Zeichen) wären dafür zu prüfen —
  **das ist der lohnendste nächste Messschritt**, falls diese Option verfolgt wird.

---

**Option E — Reihenfolge statt Betrag**
*BC2 liefert vorerst keine EUR-Aussage, sondern nur eine begründete Priorisierung.*

- **Machbar?** Ja, **vollständig aus vorhandenen Daten**: `v_prozessautomatisierung` (6 Dimensionen ×
  43 Teilprozesse), `items_unter_3`, Reifegrad, schwächster Teilprozess. Die in #158 bereits
  entschiedene **Nutzwertanalyse (Bitkom)** für Nicht-Monetäres ist genau dieses Instrument.
- **Kosten:** Am geringsten von allen — keine neue Datenerhebung, kein Frontend, keine Annahmen.
- **Geopfert:** **Der Business Case.** „Automatisierungskonzept **inkl. ROI**" steht im
  BC2-README als Produced-Message, und #158 nennt „Value belastbar bewerten" im Ziel. Option E
  liefert *welches zuerst*, nicht *was es bringt*.
- **Wert dennoch:** Sie ist die einzige Option, die **ohne jede erfundene Zahl** auskommt, und sie
  kann jede der Optionen A–D als **Zwischenstand** tragen, bis Zahlen vorliegen.

---

### 6e. Wäre BC2 ohne BC1 überhaupt lauffähig? — Belegte Antwort

**Teilweise. Die Trennlinie verläuft exakt zwischen Erkennen und Rechnen.**

| BC2-Schritt (nach #158) | Ohne BC1 lauffähig? | Beleg |
|---|---|---|
| Baseline aus Postgres lesen | **Ja** | Zugang steht, 26 Tabellen + 22 Views lesbar (#159, hier nachgemessen) |
| Automatisierungspotenziale **erkennen** | **Ja** | `v_prozessautomatisierung` 43 Zeilen mit 6 Dimensionen · `ref_teilprozesse.notation` 50/50 gefüllt · `items_unter_3` je KP |
| Potenziale **beschreiben** (To-Be-Vision) | **Ja** | LLM-Aufgabe auf vorhandenem Text; `notation` liefert die Aktivitätsfolgen |
| Value **monetär** bewerten | **Nein** | **Keine** der vier Pflichtgrößen liegt vor; `gate_pruefpunkt_werte` = 0 Zeilen; keine gefüllte numerische Aufwandsspalte in `public` |
| Value **qualitativ** bewerten (Nutzwertanalyse) | **Ja** | Reifegrad-, Automatisierungs- und Complianceachsen vorhanden |
| **Priorisieren** | **Ja, ordinal** — nein, monetär | s. o. |
| Konzept + Präsentation erzeugen | **Ja** | hängt an #167/#160, nicht an BC1 |
| Nach Schema `bc2` zurückschreiben | **Ja** | `has_schema_privilege('bc2','CREATE') = true` |

**Belegtes Fazit:** BC2 ist **ohne BC1 lauffähig für alles außer der monetären Wertaussage**. Die
Kostenachse steht (K1–K5, wenn auch `geschaetzt`); es fehlt ausschließlich die **Mengen- und
Zeitachse** — und die fehlt **vollständig**, nicht nur teilweise. Genau eine Zahl im ganzen
Datenbestand deutet in ihre Richtung: `"5x pro Monat"` als Freitext an einer Anfrage ohne
Prozessbezug.

Die Entscheidung zu Frage 6 ist damit **nicht** „ob BC2 ohne BC1 startet" — das kann es —, sondern:
**woher die Mengen- und Zeitachse kommt, und mit welcher Güte sie gekennzeichnet wird.**

---

## Widersprüche Dokument ↔ Datenbank

Der für BC2 wertvollste Teil. Bei jedem Widerspruch gilt: **die Messung sticht.**

| # | Dokument / Issue **[behauptet]** | Datenbank / Repo **[gemessen]** | Folge für BC2 |
|---|---|---|---|
| **W1** | BC1 liefert nach `contracts/bc1-to-bc2/` (README Z. 11, Design-Spec Z. 12) | **Das Verzeichnis existiert nicht.** `contracts/` enthält nur `README.md` und `bc3 - bc4/` | Der zugesagte Übergabeweg ist nie gebaut worden. BC2 darf ihn nicht als Schnittstelle einplanen. |
| **W2** | #163 Frage 5: „laut BC0 ist [`medienbrueche`] BC1s Aufgabe" | `ref_gate_pruefpunkte.quelle_bc` für `medienbrueche` = **`BC0`**, `guete_noetig = false`, „leer kann richtig sein" | Die Erwartung an BC1 ist gegenstandslos. BC2 sollte `medienbrueche` **nicht** von BC1 erwarten. |
| **W3** | BC0 „füllt `medienbrueche` nicht, BC1 soll es tun" | `bc1_role` hat **`INSERT = false`** auf `medienbrueche` — und auf allen 26 `public`-Tabellen | Selbst bei geändertem Willen kann BC1 nicht liefern, ohne dass **Rechte** geändert werden. Das ist eine Platform-Aufgabe, kein BC1-Versäumnis. |
| **W4** | Design-Spec: BC1 erzeugt ein „strukturiertes Prozessprofil" für BC2 | Der einzige BC1-Slot in der DB ist **`gate_ereignisse.bc1_profil_stand` (text)** — eine Freitextspalte, keine Struktur. Tabelle leer. | Es gibt **keine vereinbarte Struktur** für BC1s Output in der gemeinsamen DB. Der Vertrag ist ungeschrieben. |
| **W5** | Design-Spec B6: BC1 bleibt generisch, Felder kommen aus dem Use-Case-Paket | `ref_gate_pruefpunkte` **schreibt vier konkrete Pflichtfelder von BC1 fest** (`dauer`, `haeufigkeit`, `menge`, `rollen`) | Zwei unvereinbare Vertragsauffassungen. BC0 hält BC1 für gebunden; BC1s Design kennt keine Bindung. **Ungeklärt zwischen den Kontexten.** |
| **W6** | #163: „Die Design-Spec beschreibt ein Interview, das ein strukturiertes Prozessprofil erzeugt — steht dort Frequenz/Dauer/Menge drin?" | **Nein.** `haeufigkeit` nur in `TOY_PROZESS` (Spielzeug-Fixture, 13 Fundstellen, alle Test/Fixture); `dauer`, `menge`, `zeitanteil` **nirgends** | Die Erwartung an BC1 stützt sich auf ein Beispiel, nicht auf eine Zusage. |
| **W7** | #158: „Bandbreiten statt Punktwerten, **gestützt auf BC0s Güte-Flags**" | `gate_pruefpunkt_werte` = **0 Zeilen** bei 9 definierten Prüfpunkten | Die Stütze der bereits getroffenen Entscheidung existiert nicht. Bereits als #166 vermerkt — hier bestätigt. |
| **W8** | Implizit überall: BC1 fertigstellen ⇒ BC2 bekommt Daten | Der MVP-Plan schließt DB **ausdrücklich aus** („Keine … DB-Abhängigkeit im MVP", `InMemoryStateStore`); Persistenz ist „**Roadmap-Anker, NICHT Teil dieses Plans**" | **Der schwerwiegendste Punkt.** Selbst 100 % von #120–#126 liefert BC2 nichts. Zwischen „BC1 fertig" und „BC2 hat Daten" liegt ein **ungeticketetes** Vorhaben. |
| **W9** | `v_gate_prozessstand`: KP-01…04 haben je **5** Teilprozesse mit Medienbruch (auch in #159 so übernommen) | `v_system_abdeckung`: **0** Medienbrüche. Die erste View prüft nur, ob Freitext nicht leer ist — Inhalt: „**Wenige** Medienbrüche im Standard-Fall" | **Widerspruch innerhalb der Datenbank.** `tp_mit_medienbruch` ist für BC2 nicht verwendbar; es zählt Textvorhandensein, nicht Brüche. |
| **W10** | #159: „`ref_anfragen` trägt bereits Aufwandsgrößen" | **Eine** von vier Anfragen (A-2026-04) trägt **einen** Freitextwert `"5x pro Monat"` — und hat `process_id = NULL` | Richtig, aber deutlich schwächer als es klingt. Als Baustein für die Value-Rechnung **nicht tragfähig**. |
| **W11** | #159: KP-05/KP-06 sind „teilerhoben" | Erhebung `E-2026-08`: `methode = 'gesetzt'`, `status = 'offen'`, Hinweis „**Keine Erhebung im fachlichen Sinn. Die Stufen sind gesetzt**" | Die Reifegrade von KP-05/06 sind **gesetzt, nicht gemessen**. Wer darauf rechnet, muss es kennzeichnen. |

---

## Was offen blieb

1. **[unsicher] Kennt BC1 die Prüfpunkte?** `ref_gate_pruefpunkte` bindet BC1 an vier Pflichtgrößen,
   wird aber in keinem BC1-Dokument erwähnt. Die BC1-Dokumente stammen vom 23.06.2026, die
   Prüfpunkttabelle ist erkennbar jünger. **Ob BC1 diese Verpflichtung akzeptiert hat, ist eine
   Frage an BC1, nicht an die Datenbank.** (W5)
2. **Wer baut die Brücke vom BC1-Kern in die Datenbank?** Der Schritt ist in keinem Issue erfasst —
   weder bei BC1 (#120–#126 enden beim CLI) noch bei Platform. **[unsicher]** Ich habe die
   Platform-Issues nicht durchsucht.
3. **Enthält das Unternehmensprofil eine belastbare Kapazitätsverteilung?** Entscheidend für
   Option D. Kapitel 7 (13.052 Zeichen) und Kapitel 9 (3.642 Zeichen) sind ungeprüft. **Der
   lohnendste nächste Messschritt.**
4. **`bc2-strategic-advisor/CLAUDE.md` existiert nicht.** Der Auftrag nennt die Datei als Quelle der
   Invarianten; im Repo gibt es nur `bc1-context-discovery/CLAUDE.md` und die Repo-weite
   `CLAUDE.md` im Wurzelverzeichnis. Ich habe mich an letzterer und an #158 orientiert.
5. **Die Rechtefrage ist keine BC2-Entscheidung.** Ob `bc1_role` je Schreibrechte auf `public`
   bekommt, entscheidet Platform/BC0. Solange nicht, ist W3 unauflösbar.
6. **Frage 6 ist bewusst unbeantwortet.** Die Optionen A–E stehen mit Kosten und geopferter
   Aussagekraft nebeneinander; die Wahl trifft Sergio.

---

## Anhang — verwendete Abfragen

Alle Abfragen als `bc2_role`, ausschließlich lesend, Mandantenfilter wo inhaltlich relevant.
Zugangsdaten ausschließlich als Umgebungsvariable; nichts davon in diesem Dokument.

```sql
-- Schema bc1 vollständig leer (jede Objektart)
select c.relkind, c.relname from pg_class c
  join pg_namespace n on n.oid=c.relnamespace where n.nspname='bc1';

-- BC1 kann nirgends in public schreiben
select t.table_name,
       has_table_privilege('bc1_role','public.'||quote_ident(t.table_name),'INSERT') as ins
from information_schema.tables t
where t.table_schema='public' and t.table_type='BASE TABLE';

-- Der Vertrag: wer schuldet welche Größe
select pruefpunkt, bezeichnung, quelle_bc, guete_noetig, pflicht, aktiv
from ref_gate_pruefpunkte order by reihenfolge;

-- Die Wertetabelle dazu ist leer
select count(*) from gate_pruefpunkt_werte;   -- 0

-- Suche nach Aufwandsgrößen in ganz public
select table_name, column_name, data_type from information_schema.columns
where table_schema='public'
  and column_name ~* 'haeufig|frequenz|dauer|menge|volumen|zeitanteil|aufwand|umfang|fte|stunden|minuten';

-- Der Medienbruch-Widerspruch
select process_id, tp_mit_medienbruch from v_gate_prozessstand
 where company_id='7c2d5ee9-2a9a-5990-810f-502ea2b2012d';
select process_id, anz_medienbrueche, befund from v_system_abdeckung
 where company_id='7c2d5ee9-2a9a-5990-810f-502ea2b2012d';
select pg_get_viewdef('public.v_gate_prozessstand'::regclass, true);

-- Die einzige Häufigkeitsangabe im Bestand
select anfrage_id, eingang_weg, process_id, umfang_geschaetzt
from ref_anfragen where company_id='7c2d5ee9-2a9a-5990-810f-502ea2b2012d';

-- Die 30 Bitkom-Items messen keine Aufwandsgröße
select item_nr, dimension, kriterium, frage from ref_items order by item_nr;
```

Repo-seitig:

```bash
gh issue view 163 ; gh issue view 158 ; gh issue view 159 --comments ; gh issue view 95 --comments
gh issue list --label bc1 --state all
find contracts -type f          # kein bc1-to-bc2/
find bc1-context-discovery -type f   # 5 Dateien, alle .md
grep -n -i -E "haeufigkeit|dauer|menge|zeitanteil" bc1-context-discovery/design/Implementierungsplan-MVP-Kern.md
```
