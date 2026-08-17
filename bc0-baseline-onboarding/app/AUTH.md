# Anmeldung und Benutzerverwaltung

*Etappe 4a · eingerichtet 10.08.2026 · BC0 · Simeon Ehmer*

> **Was sich geändert hat.** Bis zum 10.08.2026 war die BC0-App unter
> `bc0.perspektivwechsel.ai` ohne Anmeldung erreichbar — und schreibbar. Jeder,
> der die Adresse kannte, konnte Mandanten anlegen, Bewertungen ändern und
> Belege löschen. Seit dieser Etappe verlangt jeder Pfad unter `/api/` eine
> gültige Sitzung.

---

## 1. Ersteinrichtung

Es gibt **kein Standardkonto**. Solange kein Benutzer angelegt ist, kommt
niemand hinein — auch nicht versehentlich. Der erste Zugang entsteht auf dem
Server:

```bash
ssh root@<server>
cd /opt/bc0
docker compose exec app python benutzer_verwalten.py anlegen \
  --email <adresse> --name "<Vorname Name>" --rolle admin
```

Das Passwort wird **verdeckt abgefragt**, nicht als Argument übergeben.
Argumente stehen in der Shell-History und in der Prozessliste — für ein Passwort
der falsche Ort.

Danach zeigt die Anmeldemaske unter der Live-URL. Alles Weitere läuft über die
Oberfläche; das Skript bleibt der Rettungsweg, falls kein Admin mehr
anmeldefähig ist.

**Prüfen, ob es geklappt hat:**

```bash
docker compose exec app python benutzer_verwalten.py liste
```

---

## 2. Die beiden Rollen

| | Benutzer | Admin |
|---|---|---|
| Mandanten sichtbar | nur die zugeordneten | **alle** |
| anlegen, ändern, speichern | ja, im eigenen Mandanten | ja, überall |
| **löschen** | nein | **ja** |
| **freigeben** (an BC2) | nein | **ja** |
| Benutzer verwalten | nein | ja |

Beschlossen im Meeting vom 10.08.2026. Eine dritte Stufe („nur lesen") ist
bewusst nicht vorgesehen — sie hätte ohne konkreten Bedarf nur die
Rechteprüfung verkompliziert.

**Ein Benutzer ohne Mandantenzuordnung sieht nichts.** Das ist kein Fehler,
sondern die sichere Vorbelegung. Zuordnen:

```bash
docker compose exec app python benutzer_verwalten.py mandanten \
  --email <adresse> --mandant <company_id>
```

Die `company_id` steht in der Übersicht der Anwendung oder in der Datenbank
(`SELECT company_id, name FROM companies;`).

---

## 3. Wo geprüft wird — drei Ebenen

Die Trennung ist Absicht. Jede Ebene fängt etwas anderes ab.

**Ebene 1 — Die Datenbank.** Eigene Rolle und eigenes Schema je Bounded Context,
kein Schreibrecht auf `public` außer für BC0. Beschrieben in `ROLLEN.md`. Diese
Ebene wirkt auch dann, wenn die Anwendung einen Fehler hat.

**Ebene 2 — Die Anwendung.** `AnmeldepflichtMiddleware` weist jede Anfrage unter
`/api/` ohne gültige Sitzung mit `401` ab. Ausgenommen sind nur drei Pfade
(`/api/auth/login`, `/logout`, `/status`) — jeder davon ist in
`bc0_auth/middleware.py` einzeln begründet.

> **Warum eine Middleware und nicht `Depends` an jedem Endpunkt?**
> Weil ein neu hinzugefügter Endpunkt sonst so lange offen wäre, bis jemand
> daran denkt. Die Middleware dreht die Vorgabe um: geschützt, sofern nicht
> ausdrücklich freigegeben. Ein vergessener Schutz führt dann zu `401` statt zu
> einem offenen Endpunkt — ein Fehler, der auffällt.

**Ebene 3 — Die Oberfläche.** Sie blendet aus, was der Angemeldete nicht darf.
Das ist **Bequemlichkeit, keine Sicherheit.** Wer die Oberfläche umgeht und
direkt gegen die API spricht, wird von Ebene 2 abgewiesen.

---

## 4. Aufbau des Pakets `bc0_auth`

```
bc0_auth/
├── modelle.py          Rolle, Benutzer, Sitzung — fachliche Typen, keine Technik
├── passwoerter.py      Hash-Verfahren, Sitzungsschlüssel
├── repository.py       Persistenz — der einzige Ort mit SQL für Benutzer/Sitzungen
├── dienst.py           Anwendungsfälle: anmelden, abmelden, Sitzung auflösen
├── middleware.py       Anmeldepflicht als Netz unter der API
├── abhaengigkeiten.py  Depends-Funktionen für FastAPI
└── routen.py           HTTP-Schnittstelle unter /api/auth
```

Die Abhängigkeiten zeigen **ausschließlich nach innen**: `routen` kennt `dienst`,
`dienst` kennt `repository` und `passwoerter`, alle kennen `modelle`, und
`modelle` kennt niemanden. Deshalb lassen sich die inneren Schichten ohne
Webserver und ohne Datenbank testen.

`bc0_auth` öffnet **keine eigene Datenbankverbindung**, sondern bekommt die
Verbindungsfabrik der Anwendung im Konstruktor übergeben. Das vermeidet einen
Import-Zyklus mit `app.py` und macht die Tests möglich.

**Eingriff in `app.py`:** sechs Zeilen nach `init_db()`. Kein bestehender
Endpunkt wurde umgeschrieben.

---

## 5. Die getroffenen Entscheidungen und ihre Begründung

**Passwörter: PBKDF2-HMAC-SHA256, 600.000 Durchläufe, 16 Byte Salz je Passwort.**
Argon2 oder bcrypt wären fachlich vorzuziehen, brauchen aber eine zusätzliche
Abhängigkeit und bei bcrypt eine kompilierte Erweiterung im Container. PBKDF2
liegt in der Standardbibliothek und ist nach BSI TR-02102-1 und NIST SP 800-132
zulässig. 600.000 Durchläufe entsprechen der OWASP-Empfehlung. Der
Kostenparameter steht **im Hash selbst** — wird er später erhöht, bleiben alte
Hashes gültig und werden bei der nächsten erfolgreichen Anmeldung still
nachgezogen. Kein Zwangs-Passwortwechsel, keine Migration.

**Mindestlänge 12 Zeichen, keine Zeichenklassen-Pflicht.** Erzwungene
Sonderzeichen führen erfahrungsgemäß zu kürzeren, schlechter merkbaren
Passwörtern. Die Länge ist der wirksamere Hebel (NIST SP 800-63B).

**Sitzungen serverseitig, nicht als JWT.** Ein JWT bleibt bis zum Ablauf gültig,
auch wenn das Konto inzwischen gesperrt wurde. Eine Zeile in `app_sitzungen`
lässt sich löschen — die Sitzung ist sofort beendet. Die zusätzliche Abfrage je
Anfrage ist bei dieser Zugriffszahl ohne Belang.

**In der Datenbank steht nur der SHA-256-Abdruck des Sitzungsschlüssels.** Wer
die Tabelle lesen kann — etwa über ein Backup auf dem Webhosting —, kann damit
keine fremde Sitzung übernehmen. Ein eigener Test prüft genau das.

**Cookie statt Bearer-Token.** `HttpOnly` macht das Cookie für JavaScript
unlesbar; ein eingeschleustes Skript kann es nicht abgreifen. Ein im
`localStorage` abgelegtes Token wäre genau das. Gegen websiteübergreifende
Anfragen steht `SameSite=Lax`. Das Cookie wird nur über HTTPS gesendet;
`BC0_COOKIE_UNSICHER=1` schaltet das für die lokale Entwicklung ab — **im
Betrieb niemals setzen.**

**Die Fehlermeldung bei fehlgeschlagener Anmeldung ist immer dieselbe.**
Unbekannte Adresse, falsches Passwort und gesperrtes Konto sind von außen nicht
zu unterscheiden. Sonst ließe sich durch Ausprobieren feststellen, welche
Adressen existieren. Auch der Rechenaufwand ist gleich: Bei unbekannter Adresse
wird ein Blind-Hash geprüft, damit die Antwortdauer nichts verrät. Die
tatsächliche Ursache steht ausschließlich im Serverprotokoll.

**Der Zugriff auf einen fremden Mandanten antwortet mit `404`, nicht `403`.**
Ein Benutzer soll nicht erfahren, dass ein Mandant existiert, den er nicht sehen
darf.

**Der Benutzer wird bei jeder Anfrage frisch geladen.** Das kostet eine kleine
Abfrage, bewirkt aber, dass eine Sperre, ein Rollenwechsel oder eine geänderte
Mandantenzuordnung **sofort** wirken — nicht erst nach der nächsten Anmeldung.

**Ein Passwortwechsel beendet alle offenen Sitzungen.** Ein Wechsel geschieht
meist, weil ein Verdacht besteht. Bliebe eine alte Sitzung gültig, ginge der
Zweck verloren.

**Ein Admin kann sich nicht selbst herabstufen oder sperren.** Sonst entstünde
der Zustand, in dem kein Admin mehr existiert und die Anwendung nur noch über
die Kommandozeile zu retten wäre.

**Benutzer werden gesperrt, nicht gelöscht.** `freigegeben_durch` (Etappe 4d)
verweist auf die `benutzer_id`. Ein Nachweis, dessen Urheber verschwunden ist,
ist kein Nachweis.

---

## 6. Tests

```bash
cd BC0_App_PWA
pip install -r requirements-dev.txt
python -m pytest tests/ -v
```

**43 Tests, Stand 10.08.2026.** Zwei Dateien mit unterschiedlichem Zuschnitt:

- `tests/test_auth.py` — die Bausteine einzeln, ohne Webserver und ohne
  Datenbankverbindung nach außen.
- `tests/test_app_zugriff.py` — die vollständige Anwendung über den
  FastAPI-Testclient, mit Middleware, Router und Cookie-Behandlung.

Der größere Teil prüft die Fälle, die **scheitern müssen**: falsches Passwort,
gesperrtes Konto, abgelaufene Sitzung, fremder Mandant, unbekannter API-Pfad,
Selbst-Herabstufung. Ein Rechtemodell, das nur im Gutfall geprüft wurde, ist
eine Vermutung.

> **Die Tests laufen niemals gegen die Produktivdatenbank.** `tests/conftest.py`
> setzt `DATABASE_URL` auf leer, bevor `app.py` importiert werden kann. Da
> `app.py` seine `.env` mit `os.environ.setdefault` einliest, wird der bereits
> gesetzte Wert nicht überschrieben — die Anwendung sieht „kein PostgreSQL" und
> arbeitet auf einer temporären SQLite-Datei. Ohne diesen Griff liefe ein Test
> auf dem Server gegen Supabase.

---

## 7. Betrieb

**Wer hat Zugang?**

```sql
SELECT email, rolle, aktiv, letzte_anmeldung FROM app_benutzer ORDER BY email;
```

**Offene Sitzungen** (der Schlüssel steht nirgends im Klartext):

```sql
SELECT b.email, s.angelegt_am, s.laeuft_ab
  FROM app_sitzungen s JOIN app_benutzer b USING (benutzer_id)
 ORDER BY s.angelegt_am DESC;
```

**Alle Sitzungen sofort beenden** (Notfall — jeder muss sich neu anmelden):

```sql
DELETE FROM app_sitzungen;
```

**Passwort zurücksetzen**, wenn jemand ausgesperrt ist:

```bash
docker compose exec app python benutzer_verwalten.py passwort --email <adresse>
```

Sitzungsdauer: **8 Stunden** — ein Arbeitstag. Lang genug, um nicht zu stören,
kurz genug, dass ein vergessener Rechner am Folgetag nicht mehr angemeldet ist.
Abgelaufene Sitzungen werden bei jeder Anmeldung mit abgeräumt; ein eigener
Hintergrundlauf ist nicht nötig.

**Passwörter werden direkt übergeben** — nicht per Chat, Screenshot oder Mail.
Dieselbe Regel gilt bereits für die Datenbankrollen (`ROLLEN.md`).

---

## 8. Was diese Etappe noch nicht leistet

| offen | kommt mit |
|---|---|
| ~~Mandantenfilter in den Fachendpunkten~~ | ✅ **erledigt 11.08.2026, Etappe 4b** |
| Löschen ist noch nicht auf Admins beschränkt | **Etappe 4c** |
| `audit_log` wird weiterhin nicht befüllt (R9) | **Etappe 4c** |
| Freigabeverwaltung: Status, freigegeben am, freigegeben durch | **Etappe 4d** |
| Row-Level-Security in der Datenbank als zusätzliche Ebene | nach #148 |

### Stand nach Etappe 4b

Die Anwendung ist geschlossen **und** innerhalb getrennt. Jeder Endpunkt mit
einer `company_id` prüft die Zugehörigkeit; die Mandantenliste ist gefiltert;
neue Mandanten anlegen dürfen nur Admins — sonst könnte sich ein Benutzer selbst
welche schaffen und die Trennung umgehen.

**13 zusätzliche Tests** in `tests/test_mandantenfilter.py`, darunter der Nachweis,
dass ein Entzug der Zuordnung **ohne Neuanmeldung** wirkt.

Was noch fehlt, ist das Löschrecht (4c) und die Row-Level-Security in der
Datenbank. Letztere wäre die vierte Ebene: Selbst ein Fehler in der Anwendung
könnte dann keine fremden Mandantendaten liefern. Vor realen Mandantendaten
(#144) sollte sie stehen.

---

*Zugehörige Dokumente: `ROLLEN.md` (Datenbankrollen der Bounded Contexts),
`schema_v1.2_benutzerverwaltung.sql` (Tabellen), `BACKUP.md` (Sicherung),
ADR-003 (Schreibmodell, angenommen 10.08.2026).*
