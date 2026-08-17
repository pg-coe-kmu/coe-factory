# ADR-004 — Identität der Entitäten in BC0

**Status:** Entwurf · 12.08.2026
**Bezug:** [#149](https://github.com/pg-coe-kmu/coe-factory/issues/149) Entitäten-Register · blockiert M2 (Zugangsübergabe an BC1–BC4)
**Ersetzt nicht, sondern ergänzt:** ADR-003 (Schreibmodell / Single Source of Truth)

---

## 1. Kontext

BC0 ist nach ADR-003 die Single Source of Truth für die Baseline. BC1 bis BC4
lesen aus diesem Schema und schreiben in ihre eigenen. Ein Verweis von BC1 auf
ein Objekt in BC0 funktioniert nur, wenn dieses Objekt eine ID hat, die

* **stabil** ist — sie ändert sich nicht, wenn sich die Benennung ändert,
* **eindeutig** ist — kein zweites Objekt trägt sie,
* **auflösbar** ist — der Empfänger kann sie ohne Rückfrage in BC0 nachschlagen.

Eine Bestandsaufnahme am 12.08.2026 über alle 17 Tabellen des Produktivschemas
ergab: Jede Tabelle besitzt einen Primärschlüssel. Es fehlt keine ID an einer
vorhandenen Tabelle. Es fehlen **drei Entitätstypen vollständig**. Sie sind
erhoben worden, aber als Freitext in Spalten fremder Tabellen abgelegt:

| Entitätstyp | Ablage heute | Befund aus dem Produktivbestand |
|---|---|---|
| **Person** | `ref_prozesse.owner_name` (TEXT) | 9 verschiedene Werte, darin sieben reale Personen, zwei unbenannte Externe und eine rotierende Funktion — verbunden mit „/", „+" und „·" |
| **System / Werkzeug** | `ref_teilprozesse.tools` (TEXT) | 20 Zeilen, vier verschiedene Werte, je Kernprozess über alle fünf Teilprozesse identisch kopiert; enthält neben Produktnamen auch Bewertungsaussagen („vollständig digital") |
| **Erhebung** | gar nicht; nur `bitkom_bewertungen.bewertet_am` | Eine Nacherhebung ([#143](https://github.com/pg-coe-kmu/coe-factory/issues/143)) würde den Mai-Stand spurlos überschreiben |

Alle drei Freitextfelder leiden am selben Konstruktionsfehler wie zuvor die
Rollen (S-070, 11.08.): Eine **n:m-Beziehung wurde in ein einzelnes Textfeld
gepresst**. Ein Prozess hat mehrere Verantwortliche; ein Teilprozess nutzt
mehrere Systeme. Weil die Spalte nur einen Wert aufnimmt, hat die Erhebung mit
Trennzeichen improvisiert. Das Ergebnis ist maschinell nicht auflösbar.

Hinzu kommt ein zweiter, davon unabhängiger Grund. `owner_name` enthält
**Klarnamen natürlicher Personen**. Diese Spalte steht heute in `ref_prozesse`,
und `ref_prozesse` ist genau die Tabelle, auf die BC1–BC4 Leserechte bekommen
sollen. Solange die Klarnamen dort stehen, ist die Zugangsübergabe (M2) nicht
vertretbar — nicht wegen fehlender IDs, sondern wegen der Datenminimierung.

---

## 2. Entscheidung

### 2.1 Regelwerk

**R1 — IDs sind fachlich, nicht technisch.**
Wo ein Mensch die ID lesen muss, ist sie sprechend und aus dem Fach abgeleitet
(`KP-03`, `KP-03.TP-2`, `P-01`, `S-04`, `E-2026-05`). Wo sie nur eine Zeile
identifiziert und nie zitiert wird, genügt eine technische ID (`BIGSERIAL`,
`UUID`). Beide Formen existieren nebeneinander; die Wahl richtet sich danach,
ob die ID je in einem Gespräch, einem Ticket oder einer Schnittstelle auftaucht.

**R2 — IDs werden vergeben, nicht eingegeben.**
Die Vergabe erfolgt serverseitig, fortlaufend, je Mandant (`max + 1`). Die
Oberfläche schickt bei neuen Objekten **keine** ID mit. Damit kann kein
Bedienfehler zwei Objekte auf dieselbe ID setzen.

**R3 — IDs werden nie wiederverwendet.**
Wird `P-03` gesperrt, bleibt `P-03` für immer belegt. Die nächste Person
bekommt `P-08`, auch wenn `P-03` frei aussieht. Andernfalls zeigte ein alter
Verweis aus BC1 auf eine andere Person als bei seiner Entstehung.

**R4 — Es wird gesperrt, nicht gelöscht.**
Jede Entitätstabelle hat `aktiv BOOLEAN NOT NULL DEFAULT TRUE`. Löschen gibt es
nur beim Löschen des ganzen Mandanten (`ON DELETE CASCADE`). Diese Regel galt
seit dem 11.08. für Rollen und wird hiermit auf alle Entitäten ausgedehnt.

**R5 — Klarnamen stehen an genau einer Stelle.**
Der Name einer natürlichen Person steht ausschließlich in `ref_personen.name`.
Jede andere Tabelle verweist über `person_id`. Damit ist die Auskunft nach
Art. 15 DSGVO eine Abfrage, die Löschung nach Art. 17 ein `UPDATE` auf eine
Zeile — und die Leserechte für BC1–BC4 lassen sich erteilen, ohne den Namen
mitzugeben (Abschnitt 2.5).

**R6 — Ein Verweis ist ein Fremdschlüssel.**
Wo eine ID auf ein Objekt in BC0 zeigt, wird das als `FOREIGN KEY` erzwungen,
nicht als Konvention dokumentiert. Ausgenommen sind bewusst polymorphe Felder
(`audit_log.entity_id`, `beleg_dokumente.ref_id`); diese tragen stattdessen
einen Format-CHECK.

### 2.2 Vollständige Übersicht

| Entität | ID-Format | Gültig in | Tabelle | Stand |
|---|---|---|---|---|
| Unternehmen / Mandant | UUID | global | `companies` | vorhanden |
| Kernprozess | `KP-01` … `KP-10` | je Mandant | `ref_prozesse` | vorhanden |
| Teilprozess | `KP-01.TP-1` | je Mandant | `ref_teilprozesse` | vorhanden |
| Bewertungsitem (Bitkom-Katalog) | `1` … `30` | global, fest | `ref_items` | vorhanden |
| Einzelbewertung | `KP-01.TP-1.I-07` | je Mandant | `bitkom_bewertungen` | vorhanden |
| Rolle | `R-01` | je Mandant | `mandant_rollen` | seit 11.08. |
| Kostenklasse | `K1` … `K5` | global, fest | CHECK-Werteliste | seit 11.08. |
| Prozess-Schnittstelle | zusammengesetzt | je Mandant | `prozess_schnittstellen` | seit 11.08. |
| Gate-Ereignis | `BIGSERIAL` | global | `gate_ereignisse` | seit 11.08. |
| Anwendungsbenutzer | `benutzer_id` | global | `app_benutzer` | seit 10.08. |
| Sitzung | `sitzung_id` | global | `app_sitzungen` | seit 10.08. |
| Belegdokument | UUID | global | `beleg_dokumente` | vorhanden |
| Profildokument | UUID | global | `profile_documents` | vorhanden |
| Audit-Eintrag | `BIGSERIAL` | global | `audit_log` | vorhanden |
| **Person** | **`P-01`** | **je Mandant** | **`ref_personen`** | **neu, Teil A** |
| **System im Katalog** | **`SYS-CRM-ESPO`** | **global** | **`ref_systeme_katalog`** | **neu, Teil B** |
| **System beim Mandanten** | **`S-01`** | **je Mandant** | **`mandant_systeme`** | **neu, Teil B** |
| **Erhebung** | **`E-2026-05`** | **je Mandant** | **`ref_erhebungen`** | **neu, Teil C** |

### 2.3 Person (`P-01`)

Personen sind **mandantenbezogen**, nicht global. Dieselbe natürliche Person
bei zwei Mandanten bekommt zwei IDs. Das ist gewollt: Eine mandantenübergreifende
Personenidentität wäre eine Zusammenführung personenbezogener Daten über
Auftraggeber hinweg, für die es keine Rechtsgrundlage gibt.

Der Name ist **nullable**. „externer Steuerberater" und „externer DSB" sind
reale Beteiligte ohne erhobenen Namen; sie bekommen trotzdem eine ID, sonst
ginge der Verweis verloren. Gefüllt sein muss mindestens eines von `name` oder
`funktion`.

Die Zuordnung zum Prozess ist eine eigene Tabelle mit einer **Funktion**
(`eigner`, `sponsor`, `mitwirkend`, `vertretung`). Erst damit lässt sich
„Engagement Manager (rotierend) · Sponsor: Sergio Morazán Irias" korrekt
abbilden: eine Person als Sponsor, eine Funktion als Eigner.

### 2.4 System (zweistufig)

Ein **globaler Katalog** (`ref_systeme_katalog`) führt das Produkt — EspoCRM ist
bei jedem Mandanten dasselbe EspoCRM. Eine **mandantenbezogene Tabelle**
(`mandant_systeme`) führt die Instanz mit der Bezeichnung, die der Mandant
verwendet, und verweist auf den Katalog.

Der Mehraufwand ist eine Tabelle. Der Gegenwert: BC2 kann später über Mandanten
hinweg auswerten — „wie viele der erfassten KMU führen ein CRM?" — ohne dass
„EspoCRM", „Espo CRM" und „Espo" nachträglich zusammengeführt werden müssen.
Der Katalogverweis ist **optional**; ein Eigenbau ohne Produktentsprechung
bleibt katalogfrei.

**Bewertungsaussagen gehören nicht ins Systemfeld.** Der heutige Wert
„GitLab + EspoCRM + n8n vollständig digital · Repo-Setup teilautomatisch via n8n"
vermischt drei Systeme mit zwei Reifegradaussagen. Die Systeme wandern ins
Register, die Aussagen sind bereits über `bitkom_bewertungen` erfasst und
werden bei der Migration verworfen, nicht kopiert.

### 2.5 Erhebung (`E-2026-05`)

Eine Erhebung ist ein Messzeitpunkt mit Methode und Stand. Jede Einzelbewertung
gehört zu genau einer. `erhebung_id` tritt in den Primärschlüssel von
`bitkom_bewertungen` ein.

Das ist der Eingriff mit dem größten Risiko, weil er 600 produktive Zeilen und
einen Fremdschlüssel aus `bewertung_belege` berührt. Er ist trotzdem nötig:
Ohne ihn ist eine Gate-Freigabe nicht reproduzierbar. Die Freigabe muss belegen
können, auf welchem Datenstand sie beruhte — und wenn die Nacherhebung von
KP-05 bis KP-10 die Mai-Werte von KP-01 bis KP-04 mit überschreibt, ist der
Bezugspunkt weg.

### 2.6 Pseudonymisierte Leseansicht

Für BC1–BC4 wird das Leserecht **von den Tabellen auf Views verlagert**, soweit
personenbezogene Daten betroffen sind:

* `v_prozesse_lesen` — `ref_prozesse` ohne `owner_name`, dafür mit den
  `person_id`-Verweisen
* `v_prozess_personen_lesen` — Zuordnung mit `person_id`, `funktion`,
  `rolle_id`, ohne Namen

`GRANT SELECT` auf diese Views, `REVOKE` auf `ref_personen` und `ref_prozesse`.
Wer den Namen zu einer `person_id` braucht, fragt in BC0 nach — und dieser
Vorgang ist dann eine dokumentierte Weitergabe, keine stille Mitlieferung.

---

## 3. Verworfene Alternativen

**UUIDs für alles.** Technisch sauber, in der Anwendung unbrauchbar. Niemand
sagt im Interview „für Prozess `a3f1c2e8-…`". Die sprechenden IDs sind der
Grund, warum die Abstimmung mit BC1 bisher ohne Missverständnisse lief.

**Personen global über Mandanten hinweg.** Verlockend, weil Berater in mehreren
Projekten auftauchen. Verworfen aus Datenschutzgründen (2.3).

**Nur mandantenlokale Systeme ohne Katalog.** Eine halbe Stunde schneller
gebaut, dafür ein Zusammenführungsproblem, sobald der zweite Mandant erfasst
wird. Verworfen.

**Klarnamen in `ref_prozesse` belassen und nur die Rechte einschränken.** Hätte
die Doppelpflege zementiert: Der Name stünde weiter in der Prozesstabelle *und*
im Register, und beide würden auseinanderlaufen.

**Erhebung erst später einführen.** Verworfen, weil die Nacherhebung (#143)
bereits geplant ist. Nachträglich wäre der Mai-Stand nicht mehr rekonstruierbar.

---

## 4. Konsequenzen

**Positiv**

* M2 (Zugangsübergabe an BC1–BC4) wird entsperrt, sobald Teil A steht.
* BC1 kann Personen und Systeme per ID referenzieren statt per Namensabgleich.
* Auskunft und Löschung nach DSGVO sind Einzeloperationen auf einer Tabelle.
* Der Vorher-Nachher-Vergleich über Erhebungen wird möglich — Voraussetzung für
  jede Wirkungsmessung nach einer Automatisierung.

**Negativ und in Kauf genommen**

* Die Migration der Freitexte ist **Handarbeit**. Sieben Personen und acht
  Systeme lassen sich nicht zuverlässig automatisch trennen, weil die
  Trennzeichen uneinheitlich sind („/", „+", „·") und Personen mit Funktionen
  gemischt wurden.
* `ref_prozesse.owner_name` und `ref_teilprozesse.tools` bleiben zunächst als
  Spalten bestehen und werden erst nach erfolgreicher Migration entfernt. In
  der Zwischenzeit besteht die Gefahr der Doppelpflege; die Oberfläche stellt
  sie deshalb ab dem Umbau **schreibgeschützt** dar.
* Der Umbau von `bitkom_bewertungen` (Teil C) erfordert ein Backup vor der
  Ausführung und ist nicht ohne Weiteres rückabwickelbar.

---

## 5. Umsetzung in drei Teilen

| Teil | Inhalt | Risiko | Entsperrt |
|---|---|---|---|
| **A** | `ref_personen`, `prozess_personen`, Pseudonym-Views, Rechteumstellung | gering — nur neue Objekte | **M2** |
| **B** | `ref_systeme_katalog`, `mandant_systeme`, `teilprozess_systeme` | gering — nur neue Objekte | Medienbruch-Analyse |
| **C** | `ref_erhebungen`, Umbau `bitkom_bewertungen` und `bewertung_belege` | **hoch** — Primärschlüsseländerung auf 600 produktiven Zeilen | [#143](https://github.com/pg-coe-kmu/coe-factory/issues/143) |

Teil C wird erst ausgeführt, nachdem A und B produktiv laufen und ein Backup
des Tages vorliegt.
