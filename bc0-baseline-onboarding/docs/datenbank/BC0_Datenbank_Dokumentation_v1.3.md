# BC0 — Datenbankdokumentation

**Stand:** 12.08.2026 · Schemastand **v1.3** · Autor: Simeon Ehmer
**Gilt für:** die Produktivdatenbank des BC0-Onboarding-Werkzeugs
**Beschreibt ausschließlich PostgreSQL.** Der SQLite-Entwicklungsmodus der Anwendung kommt hier nicht vor; er ist ein Testhilfsmittel und kein Datenmodell.

---

## 0. Wozu dieses Dokument

Es beantwortet vier Fragen, und zwar in dieser Reihenfolge:

1. **Was liegt in der Datenbank?** — jede Tabelle, jede Spalte, jede Werteliste
2. **Wer darf was?** — Datenbankrollen und ihre Rechte
3. **Wie kommt man heran?** — die HTTP-Schnittstelle der Anwendung
4. **Was liegt *nicht* darin?** — damit niemand nach Feldern sucht, die es nicht gibt

**Es ersetzt** `06_Mockdata_BC1_to_BC2/DB_Schema.md` vom 01.06.2026. Jenes Dokument war ein *Entwurf* für die BC1→BC2-Schnittstelle und beschrieb Tabellen (`process_profiles`, `sub_process_roles`, `confidence_reports` …), die **nie angelegt wurden** — BC1 hat sein Datenmodell inzwischen selbst geschnitten (`bc1_prozessprofil`, siehe ADR-003). Wer das alte Dokument liest, sucht in dieser Datenbank vergeblich. Es gehört ins Archiv.

**Keine Zugangsdaten in diesem Dokument.** Abschnitt 8 nennt die Rollen und ihre Rechte, nicht ihre Passwörter. Passwörter werden direkt übergeben, nicht per Chat, Screenshot oder Mail, und stehen in keiner Datei, die in ein Repository gelangen kann.

---

## 1. Betriebsumgebung

| | |
|---|---|
| **Datenbank** | PostgreSQL **17.6**, verwaltet bei Supabase |
| **Projekt** | `CoE_factory_BC0` |
| **Region** | eu-west-1 (Irland) — EU-Datenhaltung |
| **Verbindung** | Session Pooler, Port 5432 |
| **Anwendung** | FastAPI unter Uvicorn, Docker Compose auf Hetzner Cloud CX23 |
| **Öffentlich erreichbar** | `https://bc0.perspektivwechsel.ai` — hinter Caddy mit automatischem TLS |
| **Zugangsschutz** | seit 11.08.2026: Anmeldepflicht für alle Endpunkte außer Anmeldung, Abmeldung und Status |
| **Sicherung** | nächtlich, Skript auf dem Server (nicht im öffentlichen Repository, weil es Hostnamen und Benutzernamen enthält) |

**Erweiterungen:** `pgcrypto` für `gen_random_uuid()`. Die im Juni-Entwurf vorgesehenen `pgvector` und `pg_trgm` sind **nicht** installiert — sie waren für eine Source-Attribution gedacht, die in BC1 stattfindet, nicht in BC0.

---

## 2. Grundregeln des Modells

**ADR-003 — Single Source of Truth.** BC0 hält die Baseline. BC1 bis BC4 lesen daraus und schreiben in ihre eigenen Schemata. Es gibt keinen Nachrichtenkanal zurück nach BC0; wer etwas mitteilen will, schreibt es in die Datenbank, und BC0 liest es dort.

**ADR-004 — Identität der Entitäten.** Sechs Regeln:

| | |
|---|---|
| **R1** | IDs sind fachlich und lesbar, wo ein Mensch sie zitiert (`KP-03`, `P-01`, `S-04`); technisch (`UUID`, `BIGSERIAL`) nur dort, wo sie nie ausgesprochen werden |
| **R2** | Der Server vergibt IDs fortlaufend, nicht die Oberfläche |
| **R3** | IDs werden **nie wiederverwendet** — der Zähler läuft über das Maximum, nicht über die Anzahl |
| **R4** | Es wird **gesperrt, nicht gelöscht** (`aktiv = false`) |
| **R5** | Klarnamen natürlicher Personen stehen an **genau einer Stelle**: `ref_personen.name` |
| **R6** | Ein Verweis ist ein Fremdschlüssel, keine Konvention |

**Mandantentrennung.** Jede fachliche Tabelle trägt `company_id` als erste Spalte des Primärschlüssels. Ein Löschen des Mandanten räumt alles Zugehörige mit (`ON DELETE CASCADE`).

**ID-Muster im Überblick:**

| Ebene | Muster | Beispiel |
|---|---|---|
| Mandant | UUID | `a3f1c2e8-…` |
| Kernprozess | `KP-XX` | `KP-02` |
| Teilprozess | `KP-XX.TP-Y` | `KP-02.TP-3` |
| Einzelbewertung | `KP-XX.TP-Y.I-NN` | `KP-02.TP-3.I-07` |
| Person | `P-NN` | `P-01` |
| System beim Mandanten | `S-NN` | `S-04` |
| System im Katalog | `SYS-<Kat>-<Kurz>` | `SYS-CRM-ESPO` |
| Rolle | `R-NN` | `R-02` |
| Kostenklasse | `K1`–`K5` | `K3` |
| Medienbruch | `MB-NNN` | `MB-001` |

---

## 3. Aufzählungstypen (ENUM)

Drei echte PostgreSQL-ENUMs. Alle übrigen Wertelisten sind `CHECK`-Bedingungen auf `TEXT` — bewusst, weil sich eine `CHECK`-Liste ohne Sperre der Tabelle erweitern lässt, ein ENUM in älteren Versionen nicht.

```sql
process_category  = 'Steuerungsprozess' | 'Kerngeschäftsprozess' | 'Unterstützungsprozess'
onboarding_status = (Status des Mandanten, Vorbelegung 'neu')
beleg_source      = Herkunft einer Bewertung, Vorbelegung 'manuell'
doc_status        = 'hochgeladen' | 'ocr_fertig' | 'vorgeschlagen' | 'bestaetigt' | 'verworfen'
```

---

## 4. Mandant und Profil

### `companies` — der Mandant

| Spalte | Typ | | Bedeutung |
|---|---|---|---|
| `company_id` | `uuid` | **PK**, Vorbelegung `gen_random_uuid()` | |
| `name` | `text` | NOT NULL | |
| `branche`, `rechtsform`, `region` | `text` | | |
| `mitarbeitende` | `integer` | `>= 0` | |
| `status` | `onboarding_status` | NOT NULL, `'neu'` | |
| `created_at`, `updated_at` | `timestamptz` | NOT NULL, `now()` | |

### `company_profile` — Langprofil, 1:1 zum Mandanten

`company_id` ist zugleich Primär- und Fremdschlüssel. Enthält `geschaeftsmodell`, `tech_stack`, `vision` als Text, `finanzen` und `profile_json` als `jsonb`. **`profile_json` ist die RAG-Quelle für BC1** — frei strukturiert, absichtlich nicht normalisiert.

### `profile_documents` — hochgeladene Profildokumente

`doc_id` (UUID, PK), `company_id`, `filename`, `minio_key`, `mime_type`, `uploaded_at`.

---

## 5. Prozessstruktur

### `ref_prozesse` — Kernprozesse

| Spalte | Typ | | Bedeutung |
|---|---|---|---|
| `company_id` + `process_id` | `uuid` + `varchar(8)` | **PK** | `process_id` muss `^KP-[0-9]{2}$` erfüllen |
| `process_name` | `text` | NOT NULL | |
| `kategorie` | `process_category` | NOT NULL | Steuerung / Kerngeschäft / Unterstützung |
| `beschreibung` | `text` | | ein bis zwei Sätze, **Erklärgrundlage für den BC1-Interview-Bot** |
| `trigger_text` | `text` | | Prozessauslöser |
| `input_text`, `output_text` | `text` | | **derzeit bei allen zehn Prozessen leer** — siehe Abschnitt 11 |
| `owner_name`, `owner_role` | `text` | | **veraltet.** Abgelöst durch `ref_personen` und `prozess_personen`. Wird nach Prüfung der Migration entfernt |
| `created_at` | `timestamptz` | NOT NULL | |

### `ref_teilprozesse` — Teilprozesse, genau fünf je Kernprozess

| Spalte | Typ | | |
|---|---|---|---|
| `company_id` + `sub_process_id` | `uuid` + `varchar(16)` | **PK** | Muster `^KP-[0-9]{2}\.TP-[0-9]+$` |
| `process_id` | `varchar(8)` | FK → `ref_prozesse` | |
| `step_no` | `integer` | `BETWEEN 1 AND 5`, eindeutig je Prozess | |
| `sub_process_name` | `text` | NOT NULL | |
| `notation` | `text` | | Ablauf als `A → B → C` |
| `tools` | `text` | | **veraltet.** Abgelöst durch `teilprozess_systeme` |
| `medienbrueche` | `text` | | teilweise abgelöst durch `medienbrueche` |
| `schnittstellen`, `api` | `text` | | noch Freitext, kein Register (siehe Abschnitt 11) |

### `prozess_schnittstellen` — Verflechtung zwischen Kernprozessen

Primärschlüssel `(company_id, von_process_id, nach_process_id, art)`. Beide Prozess-IDs sind Fremdschlüssel auf `ref_prozesse`; `von` und `nach` dürfen nicht gleich sein.

`art` ∈ `daten` · `freigabe` · `material` · `information`

---

## 6. Bitkom-Bewertung

### `ref_items` — der Fragenkatalog, global

30 Zeilen, `item_nr` von 1 bis 30 als Primärschlüssel. Aufbau des Modells **Digitale Prozesse 3.0**: 5 Dimensionen × 3 Kriterien × 2 Fragen. Spalten `dimension`, `kriterium`, `frage`.

Die fünf Dimensionen: Technologie · Prozessdaten · Prozessqualität · Kundinnen und Kunden · Skills und Kultur.

### `bitkom_bewertungen` — die Einzelbewertungen

| Spalte | Typ | | |
|---|---|---|---|
| `company_id` + `id` | `uuid` + `varchar(28)` | **PK** | `id` muss `^KP-[0-9]{2}\.TP-[0-9]+\.I-[0-9]{2}$` erfüllen |
| `sub_process_id` | `varchar(16)` | FK → `ref_teilprozesse` | |
| `item_nr` | `integer` | FK → `ref_items` | eindeutig je Teilprozess |
| `stufe` | `integer` | `BETWEEN 1 AND 5` | |
| `beleg` | `text` | NOT NULL, **nicht leer** | Belegpflicht: keine Bewertung ohne Begründung |
| `quelle` | `beleg_source` | NOT NULL, `'manuell'` | |
| `bewerter` | `text` | | Freitext, **kein Verweis auf `ref_personen`** |
| `bewertet_am` | `timestamptz` | NOT NULL | |

**Skalenbedeutung nach Bitkom** — die Abstände sind ungleich, das ist im Modell so vorgesehen:

| Stufe | Erfüllungsgrad |
|---|---|
| 1 | 0 % |
| 2 | über 0 bis 40 % |
| 3 | über 40 bis 50 % |
| 4 | über 50 bis 95 % |
| 5 | über 95 % |

Bitkom aggregiert ausdrücklich **über Mittelwerte** (zwei Fragen → Kriterium, drei Kriterien → Dimension, fünf Dimensionen → Digitalisierungsgrad). Nachkommastellen sind modellkonform.

### `beleg_dokumente` und `bewertung_belege`

`beleg_dokumente` hält hochgeladene Nachweise: `doc_id` (UUID, PK), `ref_id` als Text (`KP-XX` oder `KP-XX.TP-Y`, **polymorph, deshalb ohne Fremdschlüssel**), `storage_key`, `ocr_text`, `ocr_confidence`, `extrakt` als `jsonb`, `status`.

`bewertung_belege` verknüpft Bewertung und Dokument (n:m) mit optionalem `zitat` und `seite`. **Derzeit leer.**

---

## 7. Entitäten-Register (neu seit 12.08.2026)

### `ref_personen` — Personen je Mandant

| Spalte | Typ | | |
|---|---|---|---|
| `company_id` + `person_id` | `uuid` + `text` | **PK** | Muster `^P-[0-9]{2}$` |
| `name` | `text` | **nullable** | **das einzige personenbezogene Feld im ganzen Schema** |
| `funktion` | `text` | | `MD`, `Lead DevOps`, `externer Steuerberater` |
| `rolle_id` | `text` | FK → `mandant_rollen` | optional; ohne Rolle keine Kostenklasse |
| `extern` | `boolean` | NOT NULL, `false` | |
| `organisation` | `text` | | bei Externen |
| `aktiv` | `boolean` | NOT NULL, `true` | |
| `angelegt_am` | `timestamptz` | NOT NULL | |

**Bedingung:** mindestens eines von `name` oder `funktion` muss gefüllt sein. Unbenannte Externe bekommen eine ID über die Funktion — sonst ginge ihr Verweis aus dem Prozess verloren.

**Personen sind mandantenbezogen, nicht global.** Dieselbe natürliche Person bei zwei Auftraggebern bekommt zwei IDs. Eine übergreifende Personenidentität wäre eine Zusammenführung personenbezogener Daten über Auftraggeber hinweg.

### `prozess_personen` — wer verantwortet welchen Prozess (n:m)

Primärschlüssel `(company_id, process_id, person_id, funktion)`. Die Funktion steht im Schlüssel: dieselbe Person darf in einem Prozess zugleich Eigner und Sponsor sein.

`funktion` ∈ `eigner` · `sponsor` · `mitwirkend` · `vertretung`

### `ref_systeme_katalog` — Produktkatalog, global

`katalog_id` (PK, Muster `^SYS-[A-Z0-9]{2,4}-[A-Z0-9]{2,10}$`), `bezeichnung`, `kategorie`, `hersteller`, `quelloffen`, `aktiv`.

`kategorie` ∈ `crm` · `erp` · `dms` · `pm` · `bi` · `automatisierung` · `kommunikation` · `entwicklung` · `buchhaltung` · `hr` · `fachanwendung` · `office` · `sonstiges`

### `mandant_systeme` — Systeme beim Mandanten

`(company_id, system_id)` als PK, Muster `^S-[0-9]{2}$`. `katalog_id` ist ein **optionaler** Verweis: „Strategie-Cockpit" benennt eine Gattung, kein Produkt, und bleibt katalogfrei.

### `teilprozess_systeme` — welches System in welchem Teilprozess (n:m)

`nutzung` ∈ `fuehrend` · `genutzt` · `abgeloest` · `geplant`
`genauigkeit` ∈ `teilprozess` · `kernprozess_pauschal`

**Zu `genauigkeit`:** Die Erhebung 2026-05 hat Systeme auf Kernprozessebene erfasst und den Text über alle fünf Teilprozesse kopiert. Alle daraus migrierten Zeilen tragen `kernprozess_pauschal`. Wer sie liest, soll wissen, dass sie **nicht** teilprozessgenau ist.

### `medienbrueche` — Übergänge ohne durchgehende Datenverbindung

`(company_id, bruch_id)` als PK, Muster `^MB-[0-9]{3}$`. `von_system_id` und `nach_system_id` sind beide nullable — oft ist nur eine Seite bekannt („wird ausgedruckt und abgeheftet").

`art` ∈ `manuelle_uebertragung` · `druck_scan` · `mail_anhang` · `doppelerfassung` · `telefon_zuruf` · `sonstiges`

`aufwand_min` trägt den Zeitverlust je Durchlauf. **BC0 füllt das nicht** — die Zeitwerte entstehen im BC1-Interview.

---

## 8. Rollen, Kostenklassen und das Gate

### `mandant_rollen`

`(company_id, rolle_id)` als PK. `klasse` ∈ `K1`–`K5`, `aktiv` als Sperrmerkmal.

| Klasse | Bedeutung |
|---|---|
| **K1** | gewerblich / Assistenz |
| **K2** | Sachbearbeitung |
| **K3** | Fachkraft / Spezialist |
| **K4** | Führung / Teamleitung |
| **K5** | Geschäftsführung |

### `rollen_kostensaetze`

`(company_id, klasse, gueltig_ab)` als PK. `satz_eur_h` muss größer als null sein.

`quelle` ∈ `erhoben` · `branchenreferenz` · `geschaetzt`

**Eine Änderung erzeugt eine neue Zeile mit `gueltig_ab = heute`**, statt die alte zu überschreiben. Nur so bleibt nachvollziehbar, mit welchem Satz eine frühere Freigabe gerechnet hat. Die aktuell gültigen Sätze liefert `v_rollen_kostensaetze_aktuell`.

Erwartet wird der **Vollkostensatz**, nicht der Bruttolohn: einschließlich Arbeitgeberanteil, Ausfallzeiten (1.500 bis 1.600 produktive Stunden statt 2.080) und Arbeitsplatzkosten — typischerweise das 1,7- bis 2,2-fache des Bruttostundenlohns. Der angesetzte Faktor gehört in `bemerkung`, sonst ist der ROI nicht reproduzierbar.

### `gate_ereignisse` — Freigabeprotokoll, append-only

| Spalte | | |
|---|---|---|
| `ereignis_id` | `bigserial` | **PK** |
| `gate` | `text` | generisch, damit spätere Gates dieselbe Tabelle nutzen |
| `objekt_typ`, `objekt_id` | `text` | worauf sich die Entscheidung bezieht |
| `ereignis` | `text` | `freigegeben` · `widerrufen` · `zurueckgewiesen` · `uebergeben` |
| `benutzer_id` | `text` | FK → `app_benutzer` |
| `grundlage` | `jsonb` | **der Datenstand, auf den sich die Freigabe bezieht** |
| `grund` | `text` | Pflicht bei `zurueckgewiesen` |
| `paket_id` | `uuid` | Pflicht bei `uebergeben` |

Die beiden Pflichtbedingungen sind als `CHECK` erzwungen, nicht als Konvention.

---

## 9. Benutzerverwaltung und Protokoll

### `app_benutzer`

`benutzer_id` (PK), `email` (eindeutig), `name`, `passwort_hash`, `rolle` ∈ `benutzer` · `admin`, `aktiv`, `angelegt_am`, `letzte_anmeldung`.

**Passwörter** werden mit PBKDF2-HMAC-SHA256 abgelegt, 600.000 Durchläufe, 16 Byte Salz, Format `pbkdf2_sha256$<durchlaeufe>$<salz>$<abdruck>`. Kein Endpunkt gibt einen Hash heraus.

### `app_benutzer_mandanten`

n:m zwischen Benutzer und Mandant. Ein Benutzer ohne Eintrag sieht **keinen** Mandanten.

### `app_sitzungen`

`sitzung_id` (PK), `benutzer_id`, `schluessel_abdruck`, `angelegt_am`, `laeuft_ab`. In der Tabelle steht **nur der SHA-256-Abdruck** des Sitzungsschlüssels, nie der Schlüssel selbst — wer die Datenbank liest, kann sich damit nicht anmelden.

### `audit_log`

`audit_id` (bigserial), `company_id`, `entity`, `entity_id`, `action`, `actor`, `payload` (jsonb), `at`. Append-only. **Derzeit leer** — die Anwendung schreibt noch nicht hinein; das ist Etappe 4c.

---

## 10. Views

| View | Was sie liefert |
|---|---|
| `v_reifegrad_tp` | Ø-Stufe je Teilprozess |
| `v_reifegrad_kp` | Ø-Stufe je Kernprozess |
| `v_reifegrad_kp_dim` | Ø-Stufe je Kernprozess und Dimension — Grundlage des Spinnennetzes |
| `v_reifegrad_company` | Ø-Stufe je Mandant |
| `v_crossfunktional` | Verflechtung der Prozesse |
| `v_prozessautomatisierung` | Automatisierungssicht |
| `v_rollen_kostensaetze_aktuell` | je Klasse der jüngste gültige Satz |
| `v_gate_prozessstand` | je Kernprozess die vier Sperren des Gates |
| `v_gate_freigabestand` | letzter Freigabestand je Objekt |
| **`v_prozesse_lesen`** | `ref_prozesse` **ohne Klarnamen**, dafür `eigner_ids` und `sponsor_ids` als Array |
| **`v_prozess_personen_lesen`** | Beteiligung mit Kostenklasse, ohne Namen |
| `v_personen_abdeckung` | je Prozess: ist ein Eigner benannt? |
| `v_systemlandschaft` | je System: Kategorie, Hersteller, Verbreitung |
| `v_system_abdeckung` | je Prozess: Systeme und Medienbrüche |

Die drei fett gesetzten sind die **Lesequellen für BC1 bis BC4**.

---

## 11. Zugänge und Rechte

**Dieses Dokument enthält keine Passwörter.** Es nennt Rollen und Rechte. Passwörter werden direkt übergeben — nicht per Chat, Screenshot oder Mail — und stehen in keiner Datei, die in ein Repository gelangen kann. Die `.env` auf dem Server ist von der Übertragung ausgenommen.

### Datenbankrollen

| Rolle | Wer | Rechte |
|---|---|---|
| **Eigentümer** (`postgres`) | die BC0-Anwendung | vollständig auf alle Objekte. Nur die Anwendung verbindet sich damit; die Zugangsdaten liegen ausschließlich in der `.env` auf dem Server |
| **`bc_leser`** | BC1, BC2, BC3, BC4 | `SELECT` auf die Baseline und auf die pseudonymisierten Sichten — siehe unten |

### Was `bc_leser` lesen darf

Stammdaten und Bewertungen: `ref_items`, `ref_teilprozesse`, `bitkom_bewertungen`, `companies`, `company_profile` sowie alle Reifegrad- und Gate-Views.

Register und Kosten: `mandant_rollen`, `rollen_kostensaetze`, `v_rollen_kostensaetze_aktuell`, `prozess_schnittstellen`, `gate_ereignisse`, `ref_systeme_katalog`, `mandant_systeme`, `teilprozess_systeme`, `medienbrueche`, `v_systemlandschaft`, `v_system_abdeckung`.

Personenbezug **nur über Sichten**: `v_prozesse_lesen`, `v_prozess_personen_lesen`, `v_personen_abdeckung`.

### Was `bc_leser` ausdrücklich nicht lesen darf

| Objekt | Grund |
|---|---|
| `ref_personen` | trägt die Klarnamen (ADR-004 R5) |
| `prozess_personen` | ohne Namen zwar harmlos, aber es soll genau **einen** Lesepfad geben |
| `ref_prozesse` | trägt `owner_name` im Klartext. **Der Entzug steht noch aus** — `schema_v1.3_teil_a2_rechte_umstellung.sql`, einzuspielen erst nach Absprache mit BC1, weil BC1 danach auf `v_prozesse_lesen` wechseln muss |
| `app_benutzer`, `app_benutzer_mandanten`, `app_sitzungen` | wer die Baseline liest, muss nicht wissen, welche Menschen sie erfasst haben |

### Anwendungszugänge

Getrennt von den Datenbankrollen und ausdrücklich **nicht dieselben Passwörter**:

| Ebene | Bedeutung |
|---|---|
| **SSH zum Server** | Betrieb und Ausrollen. Nur Simeon |
| **Anwendungskonto `admin`** | Mandanten anlegen, YAML importieren, Benutzer verwalten, alle Mandanten sehen |
| **Anwendungskonto `benutzer`** | nur die zugewiesenen Mandanten; ein Konto ohne Zuweisung sieht eine leere Liste |

Ein Zugriff auf einen fremden Mandanten wird mit **404 beantwortet, nicht mit 403** — damit sich die Existenz eines Mandanten nicht durch Ausprobieren feststellen lässt.

---

## 12. HTTP-Schnittstelle (FastAPI)

Alle Endpunkte antworten JSON. **Alle außer den drei offenen erfordern eine gültige Sitzung**; ohne sie kommt `401`. Die Sitzung liegt in einem `HttpOnly`-Cookie namens `bc0_sitzung`, `SameSite=Lax`, nur über HTTPS.

### Anmeldung — `/api/auth`

| Methode | Pfad | Recht | Zweck |
|---|---|---|---|
| `GET` | `/api/auth/status` | **offen** | läuft eine Sitzung? |
| `POST` | `/api/auth/login` | **offen** | anmelden, setzt das Cookie |
| `POST` | `/api/auth/logout` | **offen** | abmelden |
| `GET` | `/api/auth/me` | angemeldet | eigenes Konto |
| `POST` | `/api/auth/me/passwort` | angemeldet | eigenes Passwort ändern |
| `GET` | `/api/auth/benutzer` | **Admin** | Benutzer auflisten |
| `POST` | `/api/auth/benutzer` | **Admin** | Benutzer anlegen |
| `PUT` | `/api/auth/benutzer/{benutzer_id}` | **Admin** | Name, Rolle, Mandanten, Sperre |
| `POST` | `/api/auth/benutzer/{benutzer_id}/passwort` | **Admin** | fremdes Passwort zurücksetzen |

Kein Endpunkt gibt je einen Passwort-Hash heraus, und keiner nimmt vom Aufrufer eine Rollenangabe für sich selbst entgegen — andernfalls könnte sich jeder Benutzer selbst zum Admin machen.

### Mandanten und Prozesse

| Methode | Pfad | Recht | Zweck |
|---|---|---|---|
| `GET` | `/api/meta` | angemeldet | Wertelisten: 30 Items, Kostenklassen, Quellen |
| `GET` | `/api/companies` | angemeldet | Mandantenliste, **auf die zugewiesenen gefiltert** |
| `POST` | `/api/companies` | **Admin** | Mandant anlegen |
| `GET` | `/api/companies/{cid}` | Mandant | Mandant mit Prozessen und Teilprozessen |
| `PUT` | `/api/companies/{cid}/profile` | Mandant | Unternehmensprofil |
| `PUT` | `/api/companies/{cid}/process` | Mandant | Kernprozess mit Teilprozessen |
| `POST` | `/api/companies/{cid}/process/add` | Mandant | Kernprozess ergänzen |
| `POST` | `/api/companies/{cid}/rating` | Mandant | Bewertungen speichern |
| `GET` | `/api/companies/{cid}/report` | Mandant | Reifegradbericht |
| `POST` | `/api/import_yaml` | **Admin** | Mandant aus YAML importieren |

### Belege

| Methode | Pfad | Recht |
|---|---|---|
| `POST` | `/api/companies/{cid}/documents` | Mandant |
| `GET` | `/api/companies/{cid}/documents` | Mandant |
| `GET` | `/api/companies/{cid}/documents/{doc_id}/file` | Mandant |
| `DELETE` | `/api/companies/{cid}/documents/{doc_id}` | Mandant |

### Stammdaten

| Methode | Pfad | Recht | Zweck |
|---|---|---|---|
| `GET` | `/api/companies/{cid}/rollen_kosten` | Mandant | Rollen und aktuelle Kostensätze |
| `PUT` | `/api/companies/{cid}/rollen_kosten` | Mandant | speichern; Rollen werden gesperrt, nicht gelöscht |
| `GET` | `/api/companies/{cid}/entitaeten` | Mandant | Personen, Systeme, Zuordnungen, Auswahllisten |
| `PUT` | `/api/companies/{cid}/entitaeten` | Mandant | speichern; **jeder Block einzeln optional** |

„Mandant" als Recht heißt: angemeldet **und** dem Mandanten zugewiesen, sonst `404`.

Zum letzten Eintrag: Fehlt im Rumpf der Schlüssel `personen`, `systeme` oder `zuordnungen`, wird der jeweilige Block nicht angefasst. Sonst könnte ein Teilformular stillschweigend löschen, was es gar nicht anzeigt.

### Oberfläche

`GET /` liefert die Anwendung, `GET /sw.js` den Service Worker, `GET /manifest.json` das PWA-Manifest, `/static/*` die übrigen Dateien.

---

## 13. Was diese Datenbank nicht enthält

Damit niemand danach sucht:

**Keine Zeiten, Mengen oder Häufigkeiten.** BC0 erhebt den Reifegrad, nicht den Aufwand. Wie oft ein Prozess läuft, wie lange ein Schritt dauert, wie viele Vorgänge im Jahr anfallen — all das entsteht im BC1-Interview. Ohne diese Werte ist **keine ROI-Rechnung möglich**; BC0 liefert die Kostenachse (welche Rolle, welche Klasse, welcher Satz), nicht die Mengenachse.

**Keine BC1-Profiltabellen.** `process_profiles`, `sub_process_roles`, `sub_process_systems`, `source_refs`, `confidence_reports` aus dem Entwurf vom 01.06.2026 existieren nicht. BC1 hält sein Modell in eigenen Tabellen (`bc1_prozessprofil`), BC0 liest es dort.

**Keine Embeddings, keine Vektorsuche.** `pgvector` ist nicht installiert. Source-Attribution findet in BC1 statt.

**Kein Register für `ref_teilprozesse.schnittstellen` und `.api`.** Beide sind noch Freitext. Sie bekommen erst dann ein Register, wenn sie tatsächlich gepflegt werden.

**Kein Erhebungsbezug.** Eine Bewertung weiß nur, *wann* sie entstand (`bewertet_am`), nicht *zu welcher Erhebung* sie gehört. Eine Nacherhebung würde den bisherigen Stand überschreiben. Das behebt Schema v1.3 **Teil C** (`ref_erhebungen`, `erhebung_id` im Primärschlüssel von `bitkom_bewertungen`) — beschlossen, noch nicht gebaut.

---

## 14. Bekannte Lücken im Datenbestand

Stand 12.08.2026, Mandant NoroAI Consulting GmbH:

| Lücke | Umfang | Folge |
|---|---|---|
| `input_text` / `output_text` | **0 von 10** Prozessen gefüllt | die cross-funktionale Matrix zeigt durchgehend `? → ?` |
| Bewertungen KP-05 bis KP-10 | **nicht erhoben** | sechs Prozesse sind nicht freigabefähig |
| Kostensätze K1–K5 | leer | keine ROI-Rechnung möglich |
| Rollen des Mandanten | leer | **keine der zehn Personen hat eine Kostenklasse** |
| `audit_log` | leer | keine Änderungshistorie (Etappe 4c) |
| `bewertung_belege` | leer | Bewertungen haben Freitextbelege, aber keine Dokumentbezüge |
| `medienbrueche` | leer | Zähler im Gate stammt noch aus dem Freitextfeld |

---

## 15. Schemastände

| Stand | Datum | Inhalt |
|---|---|---|
| v1.0 | 08.06.2026 | Grundmodell |
| v1.1 | 27.06.2026 | Belegpflicht, Views |
| v1.1.1 | 07.08.2026 | Nachtrag der aus der Anwendung heraus angelegten Tabellen |
| v1.2 Teil 1 | 10.08.2026 | Benutzerverwaltung: `app_benutzer`, `app_benutzer_mandanten`, `app_sitzungen` |
| v1.2 Teil 2 | 11.08.2026 | `beschreibung`, `mandant_rollen`, `rollen_kostensaetze`, `prozess_schnittstellen`, `gate_ereignisse` und drei Views |
| **v1.3 Teil A** | **12.08.2026** | `ref_personen`, `prozess_personen`, drei pseudonymisierte Sichten |
| **v1.3 Teil B** | **12.08.2026** | `ref_systeme_katalog`, `mandant_systeme`, `teilprozess_systeme`, `medienbrueche`, zwei Sichten |
| v1.3 Teil A2 | offen | Entzug des Leserechts auf `ref_prozesse` — nach Absprache mit BC1 |
| v1.3 Teil C | offen | `ref_erhebungen`, Umbau von `bitkom_bewertungen` |
| v1.3 Teil D | offen | Entfernen von `owner_name`, `owner_role`, `tools` |

Die ausführbaren Skripte liegen in `BC0_App_PWA/`. Maßgeblich ist immer das Skript, nicht dieses Dokument — hier steht die Erklärung, dort die Wahrheit.
