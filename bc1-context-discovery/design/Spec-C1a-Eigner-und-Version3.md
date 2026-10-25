# Spec C1a — Eigner-Rolle, D4 als Anzahl, E2 „je Schrittlauf", Testprofile Version 3

> Stand 24.10.2026, Entwurf 3, an den Bau angeglichen 24.10.2026. Alle Entscheidungen aus Abschnitt 9 sind getroffen (BC1-Projektleitung, 24.10.).
> - **Änderung 25.10. (Abschnitt 3, entschieden von der BC1-Projektleitung, Abschlussplan „Neu 24.10. — aus C1a" (4b)):** `ANZAHL` nimmt „ca" auch ohne Punkt und am Ende genau ein „." oder „!" an. Plan: `design/Plan-ANZAHL-ca-und-Satzzeichen.md`.
> - **Angleich an den Bau (24.10.):** Zwei Abweichungen des Plans sind von der BC1-Projektleitung bestätigt und hier eingearbeitet: der Writer liest den BC0-Eigner beim Schreiben (Abschnitte 1 und 4), und `ANZAHL` akzeptiert ein vorangestelltes Näherungswort (Abschnitt 3).
> - **Entscheidung der BC1-Projektleitung (24.10.):** Die Eigner-Spalte kommt in C1a. BC2 ist vorher um die Korrektur des README-Satzes gebeten worden (#286, Kommentar vom 24.10.).
> - **Nachtrag 24.10. abends (ändert 9.1 und 9.5):** BC2 hat in #286 nicht geantwortet, BC0 hat die Lesart aus 9.1 nicht bestätigt. Die BC1-Projektleitung hat entschieden, von Zustimmung auszugehen: Der Vertrag ist als Fassung 1.4 mitgeändert, gemergt wird ohne Warten. Widerspricht BC2 oder BC0, zieht BC1 nach. Beide sind informiert (#286, #206).
> - **Geprüft:** Builder-Check (24.10.) und Zweitmeinung Codex (24.10.). Beide Befundlisten sind eingearbeitet.
> - **Quellen:**
>   - Abschlussplan C1/C1a
>   - BC0-Brief vom 23.09. (Owner-Frage R-01)
>   - Vertrag BC1→BC2 Fassung 1.3 (README I1, I2, I8, Absatz D4, offener Punkt 1; Schema-Beschreibungen)
>   - Zusage „Version 3" in #195
> - **Nächster Schritt nach Abnahme:** Implementierungsplan.

## Big Picture

**Ziel.** C1a bedient zwei Abnehmer:

- **BC2** bekommt saubere Rechengrößen. Die Fallzahl je Durchlauf (D4) wird nicht mehr hochgerechnet. Die Schrittdauer (E2) hat eine klare Bezugsgröße, die zu BC2s Rechnung passt.
- **BC0** bekommt die Rolle des Prozess-Eigners in `process_owner_rolle_id`. BC0 hat darum gebeten (10.09.) und den Weg am 23.09. bestätigt.

Danach schreibt BC1 die drei Testprofile neu (Datenstand „Version 3", in #195 zugesagt), mit den neuen Regeln und mit `anfrage_id`.

**Was sich ändert (Klartext).**

1. **Eigner (Frage B3).** Bisher fragt das Interview den Eigner als Freitext, und die Spalte bleibt leer.
   - Neu nennt das Interview die aktiven Rollen des Mandanten (`mandant_rollen`). Hat die Anfrage genau einen Kernprozess und führt BC0 für ihn eine aktive Eigner-Rolle (`v_prozesse_lesen.owner_rolle_id`), schlägt das Interview sie vor.
   - Die befragte Person **nennt** die Rolle. Ein bloßes „Ja" reicht nicht, denn der Extraktor sieht die zuletzt gestellte Frage nicht. Der Fragetext bittet deshalb ausdrücklich darum, die Rolle zu nennen.
   - In der Spalte steht die **im Interview gewählte** Rolle (9.1).
   - Weicht sie von BC0s Eintrag ab, hält das Profil einen **Befund** fest, und der Dienst schreibt eine Warnzeile. Laut BC0 ist das der Normalfall, kein Fehler. BC1 ändert bei BC0 nichts.
2. **Fallzahl je Durchlauf (D4).** Die Antwort ist eine reine Anzahl. „3 Fälle" ergibt 3. „5 pro Woche" ist ungültig, und das Interview fragt nach. Bisher wurde daraus 260.
3. **Schrittdauer (E2).** Die Frage nennt ausdrücklich die Dauer **eines Laufs dieses Schritts** (9.2). Bisher nannte sie keine Bezugsgröße. Ohne D3 läuft der Schritt einmal je Prozessdurchlauf, beide Formeln des Vertrags (I1, I8) stimmen dann.
4. **Testprofile Version 3.** Die drei Fälle werden mit neuen Sitzungsnummern neu geschrieben, denn `fertig` ist endgültig. Sie tragen:
   - `executions_per_run` = 1
   - eine Eigner-Rolle
   - eine `anfrage_id`

   Das Werkzeug prüft vor dem ersten Schreiben **alle** Anfragen. So entsteht kein Mischbestand aus alten und neuen Fassungen. Es meldet BC0 wie der Dienst „im Interview" und zieht danach das Gate nach (9.3).
5. **Vertragstext (gemeinsam mit BC2).** C1a macht in `contracts/bc1-to-bc2/` mehrere Stellen falsch. Die vollständige Liste steht in Abschnitt 8. Wir ändern sie im C1a-PR mit (Fassung 1.4). Die vollständige Liste ging als zweiter Kommentar an BC2 (#286); BC2 hat nicht geantwortet, BC1 geht von Zustimmung aus (Nachtrag im Kopf, 9.5).

**Wer etwas davon merkt.**
- **BC2:** Für BC2 kommen neue Profilfassungen, eine gefüllte Eigner-Spalte (BC2 nutzt sie nicht) und `executions_per_run` = 1. Die Formeln bleiben gleich. Ergebnisse ändern sich nur, soweit sich Eingangswerte ändern: D4 geht nicht in die Jahresminuten ein (I2), und D1/E1 der Testprofile bleiben, wie sie sind.
- **BC0:** BC0 bekommt die Spalte und den Befund im Profil-JSON. Ob BC0 den Befund anzeigt, entscheidet BC0. Ein Lesezugriff auf `befunde` oder die Spalte findet sich in BC0s Code auf `main` nicht (Suche am 24.10.).

**Voraussetzung für den Live-Lauf von Version 3, nicht für den Bau.** Die Startprüfung aus B5 lässt nur Anfragen mit dem Status `zugeordnet` oder `im_interview` zu. Live gemessen am 24.10.:

| Anfrage | Status | Bedeutung |
|---|---|---|
| A-2026-01 | `eingegangen` | noch nicht interviewbar |
| A-2026-02 | `uebergeben` | **endgültig**, BC0 kennt keinen Rücksprung (`app.py`, Statuskette; `schema_v2.7.1`) |
| A-2026-03 | `eingegangen` | noch nicht interviewbar |

Für KP-05.TP-1 braucht es also eine **neue** Anfrage. Die Anfragen stellt BC0 bereit. Die BC1-Projektleitung klärt das nach dem Bau mit BC0 (9.3).

**Bewusst nicht in C1a (mit Ziel im Abschlussplan):**
- **Rollen am Fokus-Schritt** (F1) bleiben Freitext, und `bc1.profil_rollen` bleibt leer. BC2 hat die Rollenachse am 20.09. abgewählt (#172), das ist ein Dauerzustand.
- **D1/E1 je Kernprozess einheitlich** entfällt. Vertrag I1 sagt ausdrücklich, dass D1/E1 den Prozess so beschreiben, wie die befragte Person ihn gerahmt hat. Zwei Profile desselben Kernprozesses dürfen sich widersprechen, und BC2 rechnet je Profilzeile. Der Abschlussplan-Punkt stammt aus der Vertragsprüfung vom 10.09.; erledigt hat ihn I1 („Vertrag ehrlich machen"). *(Zur Bestätigung: 9.4)*
- **Weitere Rollen einer Person** (`person_rollen`, BC0 v3.9): `bc1_role` hat darauf kein Recht.
- **Löschkaskade über `person_rollen` (BC0, unabhängig von C1a):** Eine Beobachtung zu BC0s eigener Tabelle ist BC0 direkt mitgeteilt (9.6); was daraus folgt, entscheidet BC0. BC1s Eigner-FK ist mit gefüllter Spalte getestet (`test_ddl_trigger.py:358`).
- **Extraktor kennt die zuletzt gestellte Frage nicht.** Das gilt für alle Felder und ist vorbestehend. C1a baut die LLM-Schnittstelle nicht um, sondern formuliert B3 so, dass die Antwort die Rolle nennt.
- **D3 aktiv nachfragen:** Kleinpunkt „Neu 23.10." (1). **Fragesteller vorbelegen:** B5-Rückstellung (4).

## Technischer Teil

### 1. BC0-Lesepfad (`bc0_lesepfade.py`, `start.py`)

- `rollen(conn, company_id) -> list[tuple[str, str]]`:
  - `(rolle_id, bezeichnung)` aus `mandant_rollen`, gefiltert auf `company_id` und `aktiv`, sortiert nach `rolle_id`
  - Leserecht über `bc_leser`, gemessen am 12.09. und am 24.10.
- `eigner_rollen(conn, company_id, process_ids) -> dict[str, str | None]`:
  - `owner_rolle_id` je Kernprozess aus `v_prozesse_lesen`, gefiltert auf `company_id` und die angefragten Prozess-IDs
  - `None` heißt: **keine ableitbare Eigner-Hauptrolle**. Entweder hat der Prozess keine Eigner-Person, oder die Person hat keine Rolle. Die Sicht unterscheidet das nicht.
- `lade_kontext` lädt beides. Die Kernprozesse sind die Präfixe der Teilprozess-IDs der Anfrage.
- **Startabbruch** mit klarer Meldung, wenn der Mandant keine aktive Rolle hat. *(Entscheidung des Verfassers.)* Begründung: Ohne Optionen ist B3 im Interview nicht beantwortbar, und das soll man beim Start erfahren, nicht nach zwei vergeblichen Nachfragen. Das folgt dem Muster der übrigen Startprüfungen; zwingend ist es nicht.
- `Bc0Kontext` bekommt zwei neue Felder mit leerem Default, sodass kontextfreie Tests unverändert bleiben:
  - `rollen: tuple[tuple[str, str], ...]`
  - `eigner: tuple[tuple[str, str | None], ...]`
- **Fingerabdruck** (`_ctx_fingerprint`): Die Rollen-IDs kommen hinein, weil sie die Gültigkeit bestimmen (wie die Systeme). Die Eigner kommen nicht hinein, weil sie nur Vorschlag und Befund ändern. *(Entscheidung des Verfassers.)*
- **Bezugsbasis für den Befund** ist der BC0-Stand **beim Schreiben**: Der Writer liest die Eigner-Rolle des Kernprozesses dann aus der DB, wie er es bei `kp_existiert` und `system_ids` schon tut. Der Startkontext liefert nur den **Vorschlag** im Fragetext. `SessionState` bekommt keinen Eigner-Schnappschuss (YAGNI), der Writer keinen neuen Konstruktorparameter. Ändert BC0 den Eigner während eines Interviews, vergleicht der Befund mit dem neuen Stand; wer den alten Vorschlag bestätigt hat, bekommt dann einen Befund. Das wird hingenommen und ist getestet.
- `prozessprofil.sql` Abschnitt 0: `mandant_rollen` kommt in die SELECT-Vorprüfung („was der Dienst tatsächlich liest"). Das ist keine Signaturänderung.

### 2. Paket (`discovery_paket.py`)

- `SCHEMA_VERSION_CTX` geht von `"1.1"` auf `"1.2"`, weil sich die Bedeutung von B3, D4 und E2 ändert. Der kontextfreie Zweig bleibt bei 1.0 und unverändert, wie beim Präzedenzfall E4.
- **B3** `process_owner_role`, im Kontext-Zweig:
  - Typ `AUSWAHL(*rolle_ids)` der aktiven Rollen
  - Fragetext: Rollen als `ID = Bezeichnung`, wie bei E5, mit der Bitte, die Rolle zu nennen
  - **Vorschlag** nur, wenn die Anfrage **genau einen** Kernprozess hat und dessen BC0-Eigner-Rolle **aktiv** ist, z. B. „Laut BC0 ist das Logistik (R-05)." Ist sie stillgelegt oder fehlt sie, gibt es keinen Vorschlag.
  - Bei mehreren Kernprozessen in der Anfrage gibt es ebenfalls keinen Vorschlag. Die Rolle gilt für den Prozess, den die Person beschreibt; der Befund vergleicht beim Schreiben mit dem Eigner des aus E5 abgeleiteten Kernprozesses. Live hat heute jede Anfrage genau einen Kernprozess.
  - Den Wortlaut legt der Bauende fest. Das Feld bleibt Pflicht. Der JSON-Feldname bleibt `process_owner_role`, der Wert ist eine `rolle_id`.
- **D4** `executions_per_run`, im Kontext-Zweig: Feldtyp `ANZAHL` (siehe 3).
- **E2** `focus_step_duration_minutes`, im Kontext-Zweig: Der Fragetext fragt nach der Dauer **eines Laufs dieses Schritts** (9.2), den Wortlaut legt der Bauende fest. Typ `MINUTEN` bleibt.

### 3. Feldtyp `ANZAHL` (`bc1_core/feldtypen.py`)

Allgemein, deshalb im Kern. Er nutzt den vorhandenen Token-Parser und die Formatierung (`_zahl_aus_token`, `_formatiere`, Endlichkeit wie `_ist_nichtnegative_zahl`), keinen zweiten Parser.

**Grammatik.** Gültig sind nur zwei Formen:
- eine Zahl allein
- eine Zahl, gefolgt von höchstens **einem Zählwort** aus einer festen Liste (Fall, Fälle, Vorgang, Vorgänge, Stück), optional ergänzt um „je Durchlauf" oder „pro Durchlauf"

Beiden Formen darf ein **Näherungswort** vorangehen: `etwa`, `ca.` (seit 25.10. auch `ca` ohne Punkt), `circa`, `ungefähr` (auch `ungefaehr`), `rund`, `im Schnitt`, `durchschnittlich`. Sonst wäre die häufige Antwort „etwa 3" ungültig und das Interview müsste nachfragen. (Der vorhandene Zahlparser nimmt solche Wörter nur zusammen mit einer Periode an, nicht allein; die Erweiterung ist neu.)

Seit 25.10. darf beiden Formen am Ende **genau ein** Satzzeichen `.` oder `!` folgen, direkt am letzten Wort oder an der Zahl („3 Fälle."). Ein `?` drückt Zweifel aus und bleibt ungültig, damit das Interview nachfragt. Ebenfalls ungültig bleiben: mehrere Zeichen, ein Komma und ein Leerzeichen vor dem Satzzeichen („3 ."). Die Paketfassung bleibt 1.2, denn jede bisher gültige Antwort ergibt denselben Wert; nur Antworten, die bisher eine Nachfrage auslösten, werden gültig.

Alles andere bleibt unverändert und ist damit ungültig.

| Antwort | Ergebnis |
|---|---|
| `0`, `1`, `3`, `2,5`, `1.000` | gültig: `0`, `1`, `3`, `2.5`, `1000`. Durchschnitt erlaubt, der Vertrag nennt `number ≥ 0`. *(Entscheidung des Verfassers)* |
| `3 Fälle`, `3 Vorgänge pro Durchlauf`, `etwa 3`, `ca. 3 Fälle`, `im Schnitt 2,5` | gültig, `3` bzw. `2.5` |
| seit 25.10.: `ca 3`, `ca 3 Fälle`, `3 Fälle.`, `3.`, `etwa 3.`, `3 Fälle!`, `2,5.` | gültig, `3` bzw. `2.5` |
| seit 25.10. ausdrücklich: `3?`, `3..`, `3,`, `3 Fälle.!`, `ca3`, `3 .`, `ca.. 3` | ungültig, Nachfrage |
| `5 pro Woche`, `15 im Monat`, `5/Monat`, `5 täglich`, `3 %`, `3 Stunden` | ungültig, Nachfrage |
| `-1`, leer, zwei Zahlen, Überlauf (nicht endlich) | ungültig |

### 4. Writer (`profil_writer.py`)

Reihenfolge wie bisher, als gemeinsames Abnahmekriterium: **Payload → Sweep → Ableitung von Spalten und Befunden.**

- `process_owner_rolle_id` ist der Wert von `process_owner_role` mit Status `gueltig` im gesweepten Payload, sonst `NULL` (auch bei `ungeloest`).
  - **Keine** zweite Prüfung gegen den aktuellen Kontext: Die Gültigkeit hat `AUSWAHL` beim Erfassen geprüft, den Bestand prüft der FK.
  - Spalte und JSON-Status können so nicht auseinanderlaufen, auch nicht im Recovery-Replay nach einem Neustart.
  - Die Konstante „Etappe 1" (`{"process_owner_rolle_id": None}`) entfällt.
- **Befund** `profil["befunde"]["eigner_rolle_abweichung"] = {"process_id", "interview_rolle", "bc0_rolle"}`:
  - Er entsteht, wenn BC0 beim Schreiben für den aus E5 abgeleiteten Kernprozess eine Eigner-Rolle führt und diese von der gültigen Wahl abweicht.
  - Dazu `log.warning("eigner_rolle_abweichung session=%s kp=%s interview=%s bc0=%s", …)` mit IDs, wie bei `kp_tp_diskrepanz`.
  - Ohne BC0-Rolle oder ohne gültige Wahl gibt es keinen Befund.
- Der Writer liest die Eigner-Rolle beim Schreiben aus `v_prozesse_lesen` (mit `company_id`-Filter), nicht aus dem Startkontext (siehe Abschnitt 1, Bezugsbasis).
- **FK `prozessprofil_owner_rolle_fk`** (seit Etappe 1; NO ACTION, nicht deferrable, anders als `profil_rollen_rolle_fk`):
  - Er greift schon beim **Draft**. Löscht BC0 die gewählte Rolle, bevor die Zeile geschrieben ist, gilt das bestehende Fehlerverhalten:
    - ein nichtterminaler Turn protokolliert und läuft weiter (`profil_writer.py`, `reconcile`)
    - erst der Abschluss endet mit 503 `profil_write_fehlgeschlagen`

    Das wird getestet, nicht abgefangen.
  - Er verhindert danach nur **Löschen oder Ändern des Schlüssels** (`company_id`, `rolle_id`). `bezeichnung`, `klasse` und `aktiv` bleiben bei BC0 änderbar, eine Zeile kann also später dieselbe ID unter anderer Bezeichnung zeigen.
  - Bekannt und angenommen: BC0-Befund vom 14.09. zu FKs ohne `ON DELETE`, BC0 legt still statt zu löschen (#218).

### 5. Datenbank und Auslieferung

- Keine DDL-Änderung. Spalte und FK bestehen, die Sollsignatur bleibt gleich. Die geänderte SELECT-Vorprüfung berührt die Signatur nicht. Ob der nächste Lauf Fall 2 meldet, zeigt der Lauf selbst, wie immer.
- **Versionswechsel 1.1 → 1.2.** Der Paket-Guard lehnt Turns alter Sitzungen ab (`core.py`), und je Teilprozess ist nur ein Draft erlaubt. **Vorbedingung der Auslieferung:** keine offene Sitzung, kein Draft, kein ausstehender Abschluss. Gemessen am 24.10.: `bc1.sessions` 0 Zeilen, `in_erhebung` 0. Vor dem Deployment wird erneut gemessen. Gibt es dann Offenes, wird es unter 1.1 abgeschlossen oder nach K5 verworfen, erst danach wird umgestellt. Keine automatische Migration und kein gelockerter Guard: Freitext-B3 und hochgerechnetes D4 lassen sich nicht übersetzen.

### 6. Gerüst und Testdaten (`tests/db/bc0_geruest.sql`, `tests/db_fixture.py`)

Die Personentabellen und die Eigner-Sicht gibt es im Gerüst schon, es fehlen die Daten. Neu kommen mandantenspezifisch hinzu:
- mehrere Rollen, darunter eine inaktive
- dieselbe Rollen-ID bei beiden Mandanten mit anderer Bezeichnung, außerdem eine Rolle, die es nur bei einem Mandanten gibt
- ein Eigner mit aktiver Rolle, einer mit inaktiver Rolle und ein Kernprozess ohne Eigner

### 7. Testprofile Version 3 (`use_case_testprofile.py`)

- **Neue Sitzungsnummern** `…-testdaten-v3`. „Version 3" bezeichnet den **Datenstand**. Die DB vergibt `profil_version` selbst (`max+1`). Abgenommen wird über neue Bindung, erwartete Inhalte und „jüngste fertige Fassung".
- `executions_per_run` = `1` in allen drei Fällen. D1/E1 bleiben, wie die Projektgruppe sie gesetzt hat.
- **Eigner-Antworten:** Alle drei Fälle nennen die von BC0 vorgeschlagene Rolle, live `R-05` (9.4). In Version 3 entsteht deshalb kein Befund. Den Befund-Weg decken die Container-Tests ab.
- **Anfragen** werden je Fall beim Aufruf übergeben (z. B. `--anfrage KP-05.TP-1=A-2026-NN`) und nicht mehr fest im Code geführt. BC0 vergibt die neue ID erst später.
- **Erst alle Anfragen prüfen, dann schreiben.** Das ist der vorgezogene Kleinpunkt „Neu 06.10." (10). Ist eine nicht interviewbar, bricht das Werkzeug ohne Schreiben ab, mit sauberer Meldung statt Traceback.
- **Meldungen an BC0** (9.3): Das Werkzeug nutzt den vorhandenen B4-Melder (`bc0_meldungen.py`) mit demselben Zugang wie der Dienst.
  - vor dem Interview je Anfrage `im_interview`, aus `zugeordnet`
  - nach dem Freeze Gate nachziehen

  Ohne `--echt` bleibt es ein Trockenlauf ohne Meldung. Ein Fehler beim Melden bricht vor dem Schreiben ab. Wie mit einem Fehler nach dem Freeze umgegangen wird, entscheidet der Plan; Vorbild ist das Verhalten des Dienstes aus B4.
- **Kennzeichnung** (`open_remarks`): bleibt und nennt zusätzlich „Version 3".
- Die Tests in `test_use_case_testprofile.py` pinnen die neuen Werte.

### 8. Vertrag (`contracts/bc1-to-bc2/`, nur mit BC2s Zustimmung in #286)

Mit C1a werden folgende Stellen falsch oder überholt:

**README:**
- „`process_owner_rolle_id` ist immer `NULL` — und das bleibt so"
- I1: der E2-Wortlaut, „E2 nennt im Fragetext gar keine Bezugsgröße … schärft E2 mit der nächsten Paket-Revision" und die Bezugsgröße von `focus_step_duration_minutes`; neu gilt „je Lauf des Fokus-Schritts" (9.2)
- der Absatz „D4 nutzt heute denselben Normalisierer"
- offener Punkt 1 („Version 3 folgt")

**`prozessprofil.schema.json`, Beschreibungen von:**
- `process_owner_rolle_id`
- `executions_per_run`
- `focus_step_duration_minutes`
- `process_id`: „… profil.befunde ist {}" stimmt mit dem neuen Befund nicht mehr
- `rollen`: „Eingang für die Kapazitätsachse" ist seit #172 überholt

### 9. Entscheidungen der BC1-Projektleitung (24.10.)

Alle sechs folgen der Empfehlung aus Entwurf 2.

1. **Eigner-Spalte = die im Interview gewählte Rolle**, BC0s Rolle steht im Befund. Diese Lesart folgt dem Brief vom 23.09. Der Kopfkommentar von BC0 v3.9 ließe auch eine Kopie von BC0s Rolle zu. Wir bitten BC0 um eine kurze Bestätigung (Meldung aus 9.6). Fiele sie anders aus, ändert sich im Code eine Stelle.
2. **E2 = Dauer eines Laufs des Fokus-Schritts.** Damit stimmen I1 (ohne D3) und I8 (mit D3) überein. Die Änderung an I1 braucht BC2s Zustimmung (#286).
3. **Das Werkzeug meldet BC0 wie der Dienst:** `im_interview`, danach Gate nachziehen, über den vorhandenen B4-Melder. Die Anfragen stellt BC0 bereit; für KP-05.TP-1 braucht es eine neue.
4. **Testdaten:** D1/E1 bleiben, wie die Projektgruppe sie gesetzt hat. Alle drei Eigner-Antworten bestätigen BC0s Vorschlag (`R-05`).
5. **#286 wird erweitert:** die vollständige Liste aus Abschnitt 8 und E2 (9.2). Antwortet BC2 nicht rechtzeitig, wird mit dem Merge gewartet. *(Geändert am 24.10. abends: von Zustimmung ausgehen, siehe Nachtrag im Kopf.)*
6. **Der `person_rollen`-Befund wird an BC0 gemeldet**, zusammen mit der Bitte um Bestätigung aus 9.1. Den Kanal wählt die BC1-Projektleitung.
