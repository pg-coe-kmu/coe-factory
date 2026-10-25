# BC0 — Datenbankdokumentation · Nachtrag v3.0 bis v3.4

**Stand:** 21.09.2026 · alle Stände eingespielt und an der Produktion gegengeprüft · Autor: Simeon Ehmer
**Schließt an** `BC0_Datenbank_Dokumentation_Nachtrag_v2.1-v2.9.md` (Stand 04.09.2026) an, der
seinerseits `BC0_Datenbank_Dokumentation_v1.3.md` fortschreibt. **Geprüft an den Skripten im Klon**
und an `git log`, nicht am Gedächtnis. Maßgeblich bleibt das Skript; hier steht die Erklärung.

---

## 1. Die Stände im Überblick

| Stand | Datum | Commit | Inhalt | Schema? |
|:------|:-----|:-------|:------------------------------------|:-----|
| **v3.0** | 07.–10.09.2026 | `9ddda89` | **Wer hat die Anfrage gestellt, und wann geht sie ans Gate** — Abschnitt 2 | ja |
| **v3.1** | 08.–10.09.2026 | `9ddda89` | **Zustellung an BC2: Protokoll und Wiederholung** — Abschnitt 3 | ja |
| **v3.2** | 14.09.2026 | `b0786ce` | **Der Ruf an BC2 härtet ab** — RFC-3339-Zeitstempel, kein `None` im Rumpf | nein, nur Anwendung |
| **v3.3** | 18.09.2026 | `3661405` | **Das Gate liest die BC1-Anreicherung** (#P4) — Abschnitt 4 | nein, nur Anwendung |
| **v3.4** | 18.09.2026 | `744003d` | **Der `aktiv`-Filter und der eindeutige Eigner** — Abschnitt 5 | ja |

Alle drei Schemastände sind **rein additiv**: keine Spalte entfällt, keine Regel wird gelockert,
keine Zeile geändert.

---

## 2. v3.0 — Wer hat die Anfrage gestellt, und wann geht sie ans Gate

Zwei Befunde aus Richards Brief vom 03.09.2026, beide am 07.09. am Quelltext nachgeprüft.

### 2.1 Der Steller: die Anmeldung wurde geprüft und dann vergessen

Die Anfragemaske verlangt eine Anmeldung, aber `ref_anfragen` speicherte den Benutzer nicht. Wer
eine Anfrage gestellt hatte, war hinterher nur bekannt, wenn jemand die optionale `steller_id` von
Hand ausgefüllt hatte.

| Objekt | Bedeutung |
|:----------------------------|:-------------------------------------------------|
| `ref_anfragen.angelegt_von` | Konto, das die Anfrage abgeschickt hat (FK `app_benutzer`, `ON DELETE SET NULL`). NULL bei Anfragen vor v3.0 |
| `app_benutzer_mandanten.person_id` | **Konto ↔ Person, je Mandant** — der lange offene Punkt 64. FK auf `ref_personen`, `MATCH SIMPLE`: ist die Spalte NULL, greift der Fremdschlüssel nicht. Die Zuordnung wird nachgetragen, nicht erzwungen |

**Warum die Zuordnung an `app_benutzer_mandanten` hängt und nicht an `app_benutzer`:** Ein Konto
kann mehreren Mandanten zugeordnet sein, `ref_personen` ist je Mandant. **Dieselbe Person hat bei
zwei Mandanten zwei P-IDs.**

**Warum zwei Spalten für dasselbe:** `steller_id` sagt, **wer gemeint ist** — auch wenn ein Dritter
die Maske bedient hat. `angelegt_von` sagt, **wer abgeschickt hat**. Beides kann auseinanderfallen.

### 2.2 Sicht `v_anfrage_steller`

Löst den Steller in der Reihenfolge Formular → Konto auf und weist die Herkunft aus:

| Spalte | Inhalt |
|:------------------|:---------------------------------------------|
| `steller_formular` | `ref_anfragen.steller_id`, also von Hand eingetragen |
| `konto_id` | `angelegt_von` |
| `steller_konto` | die P-ID hinter diesem Konto |
| `person_id` | **das Ergebnis** — Formular hat Vorrang vor Konto |
| `herkunft` | `formular` · `konto` · `unbekannt` |
| `person_name`, `person_funktion` | aus `ref_personen` |

> **Das Leserecht auf diese Sicht fehlte bis zum 18.09.** `schema_v3.0` enthält kein einziges
> `GRANT`. Richard wäre beim ersten Zugriff in einen Rechtefehler gelaufen. Nachgezogen von Hand am
> 18.09. und dauerhaft in v3.4 verankert.

### 2.3 `anfrage_am_gate_nachziehen(company_id, anfrage_id)`

Richards Frage lautete: *„Darf BC1 nach Abschluss des Profils `am_gate` setzen?"* Der Befund war
unerwartet: **`am_gate` stand seit v2.2 in der Wertemenge, und keine Zeile Code setzte ihn.**

Simeons Festlegung vom 07.09.: *„Wenn er abgeschlossen hat, sollte es automatisch ins Gate 0 zur
Freigabe HitL gehen."* Damit erledigt sich die Frage — **BC1 muss es nicht dürfen, weil BC0 es
selbst nachzieht.**

Die Funktion zieht Anfragen im Status `zugeordnet` oder `im_interview` auf `am_gate`, sobald BC1
geliefert hat. Gibt es `bc1.prozessprofil` nicht, meldet sie das und ändert nichts.

---

## 3. v3.1 — Zustellung an BC2

Beschluss Projektmeeting 07.09.2026: **REST-API für die BC2-Aktivierung, JSON-IDs statt
Datei-Check.** Beim Schnüren ruft BC0 den BC2-Dienst und übergibt **nur** `company_id`, `paket_id`
und `uebergeben_am`. Die Daten holt BC2 mit der `paket_id` selbst.

> Eine Nachricht ist nicht wiederholbar lesbar, ein Zustand schon. **Die Nachricht ist der Zettel
> mit der Nummer, nicht der Inhalt** — die Datenbank bleibt alleinige Quelle (ADR-003 Regel 4).

### 3.1 `bc_zustellungen` — append-only

| Spalte | Bedeutung |
|:--------------|:----------------------------------------------------|
| `zustellung_id` | bigserial, PK |
| `company_id` | FK `companies`, CASCADE |
| `paket_id` | das gerufene Paket |
| `ziel_bc` | `bc2` · `bc3` · `bc4` |
| `ziel_url` | **der Ort ohne das Geheimnis** |
| `versuch` | laufende Nummer, > 0 |
| `ergebnis` | `zugestellt` · `fehler` · **`kein_ziel`** |
| `http_code`, `meldung` | Antwortcode, gekürzter Fehlertext |
| `gesendet_am` | Zeitstempel |

**Jeder Versuch steht drin, auch der gescheiterte.** Ohne das wäre „wir haben gerufen" eine
Behauptung. Kein UPDATE, kein DELETE — dieselbe Regel wie am Gate.

`kein_ziel` ist bewusst kein Fehler: Es ist keine Adresse hinterlegt, also wurde nicht gerufen. Ein
Zustand, und er soll sichtbar sein.

> **Zieladresse und Geheimnis stehen nicht in der Datenbank**, sondern in der `.env` des Servers
> (`BC2_HOOK_URL`, `BC2_HOOK_SECRET`). Ein Geheimnis gehört nicht in eine Tabelle, die vier
> Kontexte lesen dürfen.

### 3.2 Sicht `v_zustellung_offen`

Ein Paket gilt als zugestellt, sobald **ein** Versuch `zugestellt` war. Alles andere steht hier, mit
Anzahl der Versuche und letztem Ergebnis — damit erkennbar ist, ob es klemmt oder nur wartet.
`v_uebergabe_offen` bleibt die Rückfallebene: **ein verpasster Ruf ist kein verlorenes Paket.**

> **Eine Feinheit aus Probe 3 vom 08.09.:** Sortiert wird nach Zeitstempel **und** laufender Nummer.
> `now()` ist der Beginn der Transaktion — zwei Versuche im selben Vorgang tragen denselben Wert,
> und dann entschied der Zufall, welcher als „letzter" galt.

### 3.3 v3.2 — die Abhärtung vom 14.09.

Kein Schema, nur der Ruf: **RFC-3339-Zeitstempel** und kein `None` mehr im Rumpf. Signiert wird
HMAC-SHA256 über `"<timestamp>.<rumpf>"` auf den **rohen Bytes**, Header `X-BC0-Signature` und
`X-BC0-Timestamp`, Fenster 300 Sekunden.

**Am 20.09.2026 erstmals belegt zugestellt** — beide offenen Pakete mit **HTTP 202**,
`v_zustellung_offen` zum ersten Mal leer. Die vorherige `Unauthorized`-Antwort lag allein am
fehlenden Schlüssel; die Signatur war von Anfang an richtig.

---

## 4. v3.3 — Das Gate liest die BC1-Anreicherung

Kein Schema, ein Befund: **`_bc1_angaben()` gab fest `None` zurück** — mit der Begründung, die
Feldnamen seien nicht benannt. Sie standen seit dem 08.09. in `bc1.prozessprofil`. Das Gate zeigte
seither *„wartet auf BC1"*, obwohl BC1 geliefert hatte.

Seit dem 18.09. liest `_bc1_anreicherung()` die Quelle:

| Regel | |
|:--------------------------|:-----------------------------------------|
| **Gelesen wird die jüngste fertige Fassung** je Teilprozess | Ein Entwurf (`status = 'in_erhebung'`) zählt nicht — woran BC1 noch arbeitet, ist keine Grundlage für eine Freigabe |
| **Eine Zeile heißt nicht, dass alles dasteht** | `fehlend` nennt die leeren Angaben aus `GATE_BC1_FELDER`, damit die Begründung sagen kann, *was* fehlt |
| **Fällt der Zugriff aus, kommt ein leeres Verzeichnis** | SQLite, fehlendes Schema, fehlendes Leserecht → derselbe Zustand wie vorher (`wartet_bc1`), **niemals eine falsche Zuversicht** |

Gegenprobe `pruefung_v33_bc1_anreicherung.sql`, Erwartungswerte **vor** dem Lauf festgelegt: drei
Zeilen für NoroAI, alle `profil_version = 2`, `erhebung_id = E-2026-08`, `rollen_anzahl = 0` —
`bc1.profil_rollen` ist leer.

---

## 5. v3.4 — Der `aktiv`-Filter und der eindeutige Eigner

Zwei Befunde aus Richards Brief vom 15.09., am 18.09. an der Produktion nachgemessen.

### 5.1 Die Trennlinie, die dieser Stand zieht

> **„Woran arbeiten wir JETZT?"** → gefiltert auf `aktiv = true`
> **„Wie war es DAMALS?"** → ungefiltert; `stand_zum()` und `bewertung_aktuell_zum()` bleiben
> unberührt.

Würde der historische Weg mitfiltern, verschwänden Prozesse **rückwirkend** aus Berichten, die es
damals anders gab. Das wäre das Gegenteil von R9.

### 5.2 Was gefiltert wird

| Objekt | Änderung |
|:-----------------------|:------------------------------------------|
| `v_prozesse_lesen` | filtert `aktiv`; zusätzlich `owner_rolle_id` |
| `v_bewertung_aktuell` | **stillgelegte Teilprozesse zählen nicht mehr in den Reifegrad-Mittelwert.** Spalten unverändert, damit `v_reifegrad_*` nicht bricht — nur der Join kommt dazu |
| `v_teilprozesse_lesen` | **neu** — aktive Teilprozesse, ersetzt den direkten Zugriff auf `ref_teilprozesse` |
| `v_systeme_lesen` | **neu** — aktive Systeme, ersetzt den direkten Zugriff auf `mandant_systeme` |

Simeons Entscheidung vom 18.09.: Ein stillgelegter Teilprozess geht **nicht** in den Reifegrad eines
aktuellen Berichts ein. Sonst zieht ein Prozess, den es nicht mehr gibt, den Schnitt des
Unternehmens.

> **Achtung, Doppelführung:** Dieselbe Regel steht ein zweites Mal in `app.py` als `_bew_aktuell()`,
> weil der SQLite-Entwicklungsmodus keine Sichten hat. Beide Stellen sind mit v3.4 geändert.

### 5.3 Genau ein Eigner je Prozess

`ux_prozess_eigner_eindeutig` — Teilindex auf `prozess_personen (company_id, process_id)`
`WHERE funktion = 'eigner'`. Andere Beteiligungsarten bleiben mehrfach möglich. KP-05 trug drei
Eigner, KP-04 einen ohne Rolle; die Daten wurden am 18.09. über die Oberfläche bereinigt, danach die
Regel erzwungen.

### 5.4 Rechte

`GRANT SELECT` an `bc_leser` auf `v_teilprozesse_lesen`, `v_systeme_lesen` — und auf
**`v_anfrage_steller`**, das Recht, das v3.0 vergessen hatte.

---

## 6. Was BC1 bis BC4 seit v3.0 zusätzlich lesen

| Objekt | seit | wofür |
|:----------------------|:-----|:-----------------------------------|
| `v_anfrage_steller` | v3.0, Recht ab v3.4 | Wer die Anfrage gestellt hat, mit P-ID und Herkunft — **BC1s Interviewpartner** |
| `v_teilprozesse_lesen` | v3.4 | aktive Teilprozesse statt `ref_teilprozesse` |
| `v_systeme_lesen` | v3.4 | aktive Systeme statt `mandant_systeme` |
| `v_prozesse_lesen` | v3.4 erweitert | jetzt gefiltert, mit `owner_rolle_id` |

`bc_zustellungen` und `v_zustellung_offen` sind **Betriebstabellen von BC0** und stehen
nachgelagerten Kontexten nicht zur Verfügung — siehe die offene Entscheidung
[#214](https://github.com/pg-coe-kmu/coe-factory/issues/214) zu den Standard-Leserechten in
`public`.

---

## 7. Was sich an Aussagen früherer Fassungen ändert

| frühere Aussage | gilt seit |
|:-------------------------------------|:------------------------|
| `ref_anfragen`: der Steller ist optional und von Hand zu pflegen | `angelegt_von` wird automatisch gesetzt, `v_anfrage_steller` löst auf (v3.0) |
| Status `am_gate` steht in der Wertemenge | wird seit v3.0 auch **gesetzt** — durch `anfrage_am_gate_nachziehen()` |
| Der Anstoß an BC2 ist ein Dateiabgleich | **REST-Ruf mit HMAC-Signatur**, protokolliert in `bc_zustellungen` (v3.1/v3.2) |
| Das Gate meldet „wartet auf BC1" | liest seit v3.3 tatsächlich, was BC1 geliefert hat |
| `v_prozesse_lesen`, `v_bewertung_aktuell` zeigen alles | filtern seit v3.4 auf `aktiv`; die historischen Wege **nicht** |
| Ein Prozess kann mehrere Eigner haben | **genau einer** seit v3.4 |
| BC1 liest `ref_teilprozesse` und `mandant_systeme` direkt | über `v_teilprozesse_lesen` und `v_systeme_lesen` (v3.4) |

---

## 8. Was offen bleibt

| Punkt | Vorgang |
|:--------------------------------------------|:-------------|
| BC1 unterrichten, dass der `aktiv`-Filter live ist — er wartet darauf für Paket C2 | [#228](https://github.com/pg-coe-kmu/coe-factory/issues/228) |
| Direkte Leserechte von `bc1_role` auf `prozess_personen` und `ref_personen` entziehen | [#216](https://github.com/pg-coe-kmu/coe-factory/issues/216) |
| Standard-Leserechte in `public`: automatisch oder je Tabelle freigeben | [#214](https://github.com/pg-coe-kmu/coe-factory/issues/214) |
| `GRANT REFERENCES` an `bc2_role` bis `bc4_role` — v2.4 gab es nur `bc1_role` | ToDo 121 |
| Rückweg am Gate: eine Zurückweisung wird als `entschieden` geparkt, ohne Weg zurück | [#234](https://github.com/pg-coe-kmu/coe-factory/issues/234) |
| Einzelne Zustellung nachliefern und eine Zustellung widerrufen — beides gibt es nicht | [#239](https://github.com/pg-coe-kmu/coe-factory/issues/239) |

---

*Grundlage: `schema_v3.0_steller_und_am_gate.sql`, `schema_v3.1_zustellung.sql`,
`schema_v3.4_aktiv_und_owner.sql`, `pruefung_v3.0_…`, `pruefung_v3.1_…`,
`pruefung_v33_bc1_anreicherung.sql`, `app.py` (`_bc1_anreicherung`, `_bew_aktuell`) sowie
`git log` auf `origin/main` — Stand `744003d` vom 18.09.2026.*
