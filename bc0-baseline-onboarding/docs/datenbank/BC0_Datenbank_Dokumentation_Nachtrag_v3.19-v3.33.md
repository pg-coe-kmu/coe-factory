# BC0 — Datenbankdokumentation · Nachtrag v3.19 bis v3.33

**Stand:** 04.11.2026 · Autor: BC0
**Schließt an** `BC0_Datenbank_Dokumentation_Nachtrag_v3.16-v3.18.md` (Stand 25.10.2026) an.
**Grundlage:** Skripte in `10_DB_Dokumentation/v3.19_Kaskade_und_Anfragebindung/`, `14_App_V2/v3.21_…` bis `v3.32_…` und `10_DB_Dokumentation/v3.31_Bereinigung_UC1_NoroAI/`; Drehbuch S-175 bis S-238; Bestandsaufnahmen 4–7 gegen die Produktion (01.–03.11.2026).
**Repo:** `origin/main` steht auf v3.20.2 (PR #354, 26.10.). **v3.21 bis v3.33 sind eingespielt, aber noch nicht im Repo** (Governance-Handbuch V1.2, E11).

> **Maßgeblich ist das Skript, nicht dieses Dokument.** Die md5-Summen nennen die eingespielte Fassung.

---

## 1. Die Stände im Überblick

| Stand | Datei (md5) | Art | Inhalt | eingespielt |
|:--|:--|:--|:--|:--|
| **v3.19a** | `schema_v3.19a_person_rollen_kaskade.sql` (4bd0ed6b…) | Schema | FK `person_rollen → mandant_rollen` DEFERRABLE INITIALLY DEFERRED — Mandantenlöschung läuft wieder | 25.10. |
| **v3.19b** | `schema_v3.19b_anfragebindung_erhebung.sql` (266be49b…) | Schema | Trigger `anfrage_prozesse_benannt`; `v_anfrage_teilprozesse` ohne unbenannte TPs; verworfene Erhebung macht Freigaben veraltet | 25.10. |
| **v3.19c** | `schema_v3.19c_pruefpunkt_rollen_aus.sql` (1ab8309d…) | Daten | Prüfpunkt `rollen` (Rollen mit Zeitanteil) `aktiv = false` | 25.10. |
| v3.20–v3.20.2 | — | nur Anwendung | Gate liest das BC1-Profil der gewählten Anfrage; CodeQL-Fund behoben | 25./26.10. |
| **v3.21** | `schema_v3.21_bc1_gespraeche.sql` (708efa0b…) | Schema | Tabelle `bc1_gespraeche` (Anfrage ↔ BC1-Session) | 29.10. |
| v3.22 | `neuaufbau_uc1_uc2_v3.22.sql` (e2ecfcac…) | Daten | Neuaufbau UC1/UC2 bei NoroAI (Anfragen abgelehnt, TPs benannt, 150 Bitkom-Werte in E-2026-10) | 29.10. |
| v3.23 | `loeschen_anfragen_rueckschreibungen_v3.23.sql` (07498fa2…) | Daten | Bereinigung: Anfragen und Rückschreibungen BC1–BC3 bei NoroAI | 31.10. |
| **v3.24** | `schema_v3.24_sammelpaket.sql` (16f2b614…) | Schema | Funktion `gate_paket_buendeln()` (Sammelpaket) | 31.10. |
| **v3.25** | `schema_v3.25_abschluss_abloesung.sql` (809a385c…) | Schema | `anfrage_abloesung`, `teilprozess_abgeloest`, Trigger `teilprozess_eingefroren`, Funktion `anfrage_alt_entscheiden()` | 31.10. |
| v3.26 | — | Anwendung + Dienst | PaddleOCR; nutzt die vorhandenen Spalten `erkannt_durch`, `ocr_confidence`, `status` | 31.10. |
| v3.27–v3.31 | — | nur Anwendung | Vorschläge aus Unterlagen (setzt `beleg_dokumente.extrakt`, `extrakt_durch`, `extrakt_am`), Oberfläche | 31.10.–01.11. |
| v3.31b | `loeschen_gate_bc2_bc3_v3.31b.sql` (4e313afb…) | Daten | UC1: Gate, Pakete, BC2, BC3 gelöscht; Anfragen → `am_gate` | 01.11. |
| **v3.32** | `schema_v3.32_prozessdokumentation.sql` (7044b5a2…) | Schema | Agentenblatt (Schema v2.0 nachgeholt) + Rechte `bc4_role` | 03.11. |
| v3.33 | `loeschen_uc1_bc2_bc4_und_tp5_v3.33.sql` (ec755a2e…) | Daten | UC1: BC2–BC4, Gate und A-2026-04 mit BC1-Profil gelöscht | 03.11. |

---

## 2. v3.19 — Kaskade, Anfragebindung, Prüfpunkt

**v3.19a.** `person_rollen → mandant_rollen` hatte keine Löschregel; `DELETE FROM companies` brach mit „still referenced from table person_rollen“ ab. Befund von BC1. Der Fremdschlüssel ist jetzt `DEFERRABLE INITIALLY DEFERRED` (wie `profil_rollen_rolle_fk` bei BC1) — die Prüfung läuft am Ende der Transaktion, wenn die Kaskade durch ist. Prüfung: `person_rollen_rolle_fk | t | t`.

**v3.19b.**
- Trigger `anfrage_prozesse_benannt` (BEFORE INSERT/UPDATE auf `anfrage_prozesse`): ein **direkter** Bezug auf einen unbenannten Teilprozess („Teilprozess N“) wird abgewiesen. Ältere Zuordnungen und spätere Umbenennungen prüft er nicht (Restlücke, BC1-Hinweis S-181; Kandidat v3.19d).
- `v_anfrage_teilprozesse`: Bezieht sich eine Anfrage auf einen ganzen Kernprozess, zählen unbenannte Teilprozesse nicht zur SOLL-Liste.
- `v_freigabe_datenstand`: Eine Freigabe ist veraltet, wenn ihre Erhebung (`bc0_stand`) verworfen ist; neue Spalte `erhebung_verworfen`, Grund „Erhebung E-… verworfen“ in `geaenderte_tabellen`.

**v3.19c.** `ref_gate_pruefpunkte.rollen` → `aktiv = false` (wie `zulaessigkeit`). BC1 liefert keine Rollen mit Zeitanteil (#233, Weg a).

---

## 3. v3.21 — `bc1_gespraeche`

| Spalte | Typ | Regel |
|:--|:--|:--|
| `company_id`, `anfrage_id` | UUID, TEXT | PK; FK auf `ref_anfragen` **ON DELETE CASCADE** |
| `session_id` | TEXT | eindeutig, Muster `^[A-Za-z0-9_-]{1,64}$` |
| `angelegt_am` | TIMESTAMPTZ | Vorgabe `now()` |

Setzt nur das BC0-Backend beim ersten Gesprächsschritt (`POST …/anfragen/{id}/gespraech`). Keine Nachrichtentexte. Rechte nur für den Eigentümer (REVOKE von PUBLIC und den BC-Rollen).

> **Befund 04.11. (eigener Fehler, v3.33):** Über `bc1_gespraeche.session_id` lässt sich die BC1-Session einer Anfrage eindeutig bestimmen. v3.33 hat die Session zu A-2026-04 nur über Spalten in `bc1.sessions` gesucht (keine gefunden) und `bc1_gespraeche` per Kaskade gelöscht. **Die BC1-Session zu A-2026-04 ist deshalb in `bc1.sessions` stehen geblieben.** Die Kennung steht in der Sicherung `sicherung_vor_v3.33_2026-11-03.sql`. Künftige Bereinigungen lesen die `session_id` **vor** dem Löschen aus `bc1_gespraeche`.

---

## 4. v3.24 — Sammelpaket

`gate_paket_buendeln(p_company uuid, p_benutzer text, p_hinweis text, p_anfragen text[])` → `paket_id`.

| Prüfung (sonst Abbruch, `check_violation`) | |
|:--|:--|
| Jede Anfrage existiert und ist nicht `abgelehnt` | |
| Jede Anfrage ist **vollständig** freigegeben (alle Teilprozesse aus `v_anfrage_teilprozesse`) | Weg-1-Regel |
| Ein Teilprozess gehört nicht zu zwei ausgewählten Anfragen | „getrennt übergeben“ |
| Genau diese Freigaben sind nicht schon als Paket übergeben | kein identisches zweites Paket |

Schreibt ein Ereignis `uebergeben` für das Unternehmen, `gate_pakete`, `gate_paket_inhalt` (je Teilprozess mit `anfrage_id`, `bc1_profil_stand`, `hinweis_an_bc2`) und je Anfrage ein Ereignis `uebergeben`; setzt die Anfragen auf `uebergeben`. `gate_paket_schnueren()` (Einzel- und Portfolio-Weg) bleibt unverändert. Rechte: REVOKE von PUBLIC, `anon`, `authenticated`.

**Erster Lauf:** 02.11.2026, Paket `63d585ee…` mit KP-06.TP-2 bis TP-5 (A-2026-01 bis -04), Zustellung an BC2 HTTP 202.

---

## 5. v3.25 — Abschluss und Ablösung

| Objekt | Zweck |
|:--|:--|
| `anfrage_abloesung` (PK `company_id, anfrage_id`) | die Entscheidung „alte Prozesse sperren — Ja/Nein“ mit Pflichtbegründung, `teilprozesse[]`, `entschieden_von`, `entschieden_am`; **genau eine je Anfrage** |
| `teilprozess_abgeloest` (PK `company_id, sub_process_id`) | welcher Teilprozess durch welche Anfrage abgelöst ist |
| Trigger `nur_anhaengen` auf beiden | append-only |
| Trigger `historie` auf beiden | wie alle Fachtabellen (v2.6) |
| Trigger `teilprozess_eingefroren` auf `ref_teilprozesse` (UPDATE) und `bitkom_bewertungen` (INSERT/UPDATE) | abgelöste Teilprozesse sind eingefroren |
| Funktion `anfrage_alt_entscheiden(company, anfrage, benutzer, sperren, begruendung)` | nur bei Status `erledigt`; „Ja“ = stilllegen (`aktiv = false`), dann einfrieren |

Der Abschluss selbst ist der vorhandene Status `erledigt` (seit v2.2) und sperrt nichts. Beide Tabellen am 03.11. bei NoroAI leer.

---

## 6. v3.32 — Agentenblatt (Schema v2.0 nachgeholt)

Schema v2.0 vom 19.08.2026 war nie eingespielt; der Reiter „Prozessdokumentation“ meldete 501, und BC4 konnte kein Agentenblatt schreiben (Bestandsaufnahme 7, 03.11.).

| Objekt | Schlüssel | Pflichtfelder (Auszug) |
|:--|:--|:--|
| `prozess_dokumentation` | `company_id, sub_process_id` | `bezeichnung`, `zweck`, `ersteller`, `version`, `ablauf`, `grenzen`; dazu `einsatzumgebung`, `metriken`, `ueberwachung`, `bei_stoerung`, `betriebsmodell` (selbst_gehostet · saas · hybrid · on_premise), `geprueft_am`, `aenderbar_durch` (Personen-IDs) |
| `prozess_dok_agenten` | + `agent_id` (A01 …) | `bezeichnung`, `aufgabe`, `eskalation`; dazu `modell`, `modell_version`, `prompt_fassung`, `deterministisch` |
| `prozess_dok_werkzeuge` | + `lfd` | `bezeichnung`, `version`, `art` (laufzeit · bibliothek · dienst · modell · entwicklung · orchestrierung) |
| `prozess_dok_tests` | + `lfd` | `am`, `verfahren`, `ergebnis` |
| Sicht `v_prozess_dokumentation_stand` | | Stand je Blatt, Zahl der Agenten, fällige Prüfung |

**Rechte (neu gegenüber v2.0):** `bc4_role` SELECT, INSERT, UPDATE — **kein DELETE**; `bc_leser`, `bc2_role`, `bc3_role` nur SELECT; `anon`, `authenticated` nichts. **Kein `historie`-Trigger** — er schreibt mit den Rechten des Aufrufers in `audit_log`, das darf `bc4_role` nicht (wie bei `ki_laufdaten`); Änderungen zeigen `geaendert_am`/`geprueft_am`. Gegenprobe 03.11.: 5 Objekte da; `bc4_role` t/t/t/f; `anon`/`authenticated` f/f.

**Freigabe an BC4:** 04.11.2026 (WhatsApp BC0). Abweichungen der Durchläufe (Mehdi, Zaka) gehen vorerst in `prozess_dok_tests`, eine Zeile je Durchlauf mit Paket-ID im Feld `verfahren`.

---

## 7. Bereinigungen von Testläufen (v3.22, v3.23, v3.31b, v3.33)

Alle nach demselben Ablauf (Governance-Handbuch V1.2, W9): lesende Bestandsaufnahme → Skript am PostgreSQL-Testgerüst → Vollsicherung (`pg_dump --data-only -n public -n bc1 … -n bc4`) → Einspielen in **einer** Transaktion mit Vorher/Nachher-Zählung → Abbruch mit Rollback, wenn etwas übrig bleibt oder sich Stammdaten und andere Mandanten ändern → Probe im Browser.

- Schutz-Trigger `nur_anhaengen` und BC1-Freeze (`tr_freeze_profil`, `tr_freeze_rollen`) werden **nur innerhalb der Transaktion** abgeschaltet; die Ausgabe zeigt danach alle auf `O`.
- BC2-Trigger `…_fest` greifen nur bei UPDATE/INSERT; Löschen von `bc2.lauf` kaskadiert auf Konzept, Potenzial, Gate 1.
- Rückspielen einer Sicherung nur mit `--disable-triggers` (`bc2.konzept` verweist auf sich selbst).
- **Anfragenummern:** Nach dem Löschen einer Anfrage vergibt die Anwendung ihre Nummer neu (höchste + 1). Widerspricht ADR-004 R3 (Handbuch E19).

**Stand NoroAI nach v3.33 (03.11.):** A-2026-01 bis -03 `am_gate` mit BC1-Profil Fassung 1; Gate, Pakete, BC2, BC3, `ki_laufdaten` leer; KP-06.TP-5 wartet auf BC1.

---

## 8. Rückschreiben der Contexts — gemessener Stand (Bestandsaufnahme 7, 03.11.)

| Context | schreibt in | UC1-Lauf 02.11. | Lücke |
|:--|:--|:--|:--|
| BC1 | `bc1.prozessprofil`, `bc1.sessions`; Status über die BC0-Schnittstelle | 4 Profile, je Fassung 1 mit `anfrage_id` | `bc1.sessions` ohne Anfrage-Bezug (Zuordnung nur über `bc1_gespraeche`) |
| BC2 | `bc2.eingang`, `lauf`, `konzept`, `potenzial`, `gate1`, `gate1_potenzial`, `gate1_prozess` | 1 Lauf, 1 Konzept, 4 Potenziale, Gate 1 `approved` | Gate 1 ohne `entscheider` und Kommentar |
| BC3 | `bc3.lieferungen` | 1 Lieferung (KP-06.TP-2), Gate 2 `approved` | `anfrage_id` leer (Zuordnung über `paket_id` eindeutig) |
| BC4 | `public.ki_laufdaten`, ab v3.32 Agentenblatt | 7 Generator-Läufe mit `paket_id` | `kosten_eur` leer; Schema `bc4` ohne Tabellen |

---

## 9. Überholte Aussagen

| Dokument | Aussage | richtig |
|:--|:--|:--|
| Nachtrag v3.16–v3.18, Abschn. „Offen“ | BC3/BC4 schreiben `paket_id` noch nicht | seit 25.10. (BC3, #347) bzw. 02.11. (BC4) belegt |
| Governance-Handbuch V1.1 | OCR „Konzept“; v2.0 nicht gemessen | OCR produktiv seit v3.26; v2.0 als v3.32 eingespielt |
| Datenbankdokumentation v1.3 | `audit_log` leer | gefüllt seit v2.6 (04.09.) |

---

*Nachtrag v3.19–v3.33 · 04.11.2026 · BC0 · Drehbuch S-239*
