# BC2 Trigger-Endpunkt — Inbetriebnahme

Ziel: `https://bc2.02da.de/api/bc0/uebergabe` ist erreichbar und BC0 hat einen
Schlüssel. Entschieden in [#190](https://github.com/pg-coe-kmu/coe-factory/issues/190),
Betriebsmuster von BC0 übernommen ([#136](https://github.com/pg-coe-kmu/coe-factory/issues/136)).

**Stand 10.09.2026:** Schritte 1 und 2 stehen aus — der netcup-Server ist in
manueller Bestellprüfung, der A-Record ist noch nicht gesetzt. Alles ab
Schritt 3 ist gebaut und getestet.

**Nachgezogen an BC0s gebauten Ruf** (Commit `9ddda89`): BC0 weist sich mit
einer HMAC-Signatur aus, nicht mit `Authorization: Bearer`, und schickt nur die
Kennungen. BC2 nimmt jetzt beides an — siehe Schritt 8 und 9.

---

## Was hier liegt

| Datei | Zweck |
|---|---|
| `app.py` | Der Endpunkt. Nimmt an, quittiert mit `202`, rechnet nichts. |
| `eingang.py` | Ablage. Postgres im Betrieb, Arbeitsspeicher in den Tests. |
| `migration_bc2.1_eingang.sql` | Legt `bc2.eingang` an. Wiederholbar. |
| `Dockerfile`, `docker-compose.yml`, `Caddyfile` | Container, Reverse-Proxy, HTTPS |
| `.env.example` | Vorlage. Die echte `.env` liegt **nur** auf dem Server. |
| `tests/` | 28 Tests ohne Datenbank, dazu ein Vertragstest gegen die echte. |

---

## 1. Server (manuell)

**netcup VPS nano G11s**, Standort Nürnberg, Ubuntu 24.04 — bestellt am
10.09.2026, 3,08 €/Monat brutto, **IPv4 ausdrücklich mitbestellt** (ohne sie
kein A-Record und kein Weg für BC0s Aufruf).

Sobald der Server bereitsteht:

```bash
ssh root@<IP>
curl -fsSL https://get.docker.com | sh
```

Firewall: nur **22, 80, 443** offen.

## 2. DNS (manuell)

Bei **Linevast** einen A-Record setzen:

```
bc2.02da.de.   A   <IP des netcup-Servers>
```

Erst danach kann Caddy ein Let's-Encrypt-Zertifikat ziehen. Vorher steht in der
`.env` `DOMAIN=:80` und es läuft nur HTTP — zum Testen in Ordnung, für die
Übergabe an BC0 nicht.

Propagierung prüfen:

```bash
dig +short bc2.02da.de
```

## 3. Code auf den Server

```bash
git clone https://github.com/pg-coe-kmu/coe-factory.git /opt/bc2
cd /opt/bc2/bc2-strategic-advisor/app
```

## 4. Schlüssel erzeugen

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

**BC2 stellt aus, nicht BC0** — der Betreiber des Endpunkts vergibt den
Schlüssel an den Aufrufer. Damit kann BC2 ihn rotieren und einzeln zurückziehen.

Der Wert gehört **ausschließlich** in die `.env` auf dem Server. Nicht ins Repo,
nicht in ein Issue, nicht in den Gruppenchat (ADR-003). **Übergabe an Simeon per
SMS** — derselbe Kanal, über den die Datenbank-Zugangsdaten kamen.

## 5. Konfiguration

```bash
cp .env.example .env
nano .env
```

Drei Werte:

```
DATABASE_URL=postgresql://bc2_role.<KENNUNG>:<PASSWORT>@aws-0-eu-west-1.pooler.supabase.com:5432/postgres?sslmode=require
BC2_TRIGGER_TOKEN=<der Wert aus Schritt 4>
DOMAIN=bc2.02da.de
```

⚠️ **Port 5432, nicht 6543.** Der Transaction-Pooler hält keine Sitzung über die
einzelne Anweisung hinaus.

```bash
chmod 600 .env
```

## 6. Migration einspielen

```bash
psql "$DATABASE_URL" -f migration_bc2.1_eingang.sql
```

Legt `bc2.eingang` an. Die BC2-Rolle hat CREATE ausschließlich auf `bc2`
(ADR-003) — schlägt der Aufruf mit `permission denied` fehl, stimmt die
Rollenzuordnung nicht, und **dann erst melden, dann weiterarbeiten**.

## 7. Starten

```bash
docker compose up -d --build
docker compose logs -f app
```

Der Dienst **startet nicht ohne `BC2_TRIGGER_TOKEN`**. Das ist Absicht: ein
Endpunkt, der Pakete von jedem annimmt, ist schlimmer als keiner.

## 8. Gegenproben

```bash
# Lebenszeichen, ohne Schluessel
curl -i https://bc2.02da.de/health
# -> 200 {"status":"ok"}

# Bereitschaft samt Datenbank, mit Schluessel
curl -i -H "Authorization: Bearer $BC2_TRIGGER_TOKEN" \
     https://bc2.02da.de/api/intern/bereit
# -> 200 {"status":"bereit","datenbank":true}

# Ohne Schluessel muss der Endpunkt schweigen
curl -i -X POST https://bc2.02da.de/api/bc0/uebergabe -d '{}'
# -> 401

# Ein Paket annehmen
curl -i -X POST https://bc2.02da.de/api/bc0/uebergabe \
     -H "Authorization: Bearer $BC2_TRIGGER_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"paket_id":"PROBE-1","company_id":"NOROAI",
          "uebergeben_am":"2026-09-10T14:32:11+02:00",
          "teilprozesse":["KP-02.TP-1"]}'
# -> 202 {"paket_id":"PROBE-1","status":"angenommen"}

# Derselbe Aufruf noch einmal — Doppelanstoss ist harmlos
# -> 202 {"paket_id":"PROBE-1","status":"bereits_angenommen"}
```

**Die wichtigste Gegenprobe: BC0s echter Ruf.** So ruft BC0 wirklich — mit
Signatur statt Bearer und nur den Kennungen. Wenn diese Probe durchgeht, geht
Simeons Aufruf durch:

```bash
python3 - <<'EOF'
import hashlib, hmac, json, os, time, urllib.request
geheim = os.environ["BC2_TRIGGER_TOKEN"]
rumpf = json.dumps({"ereignis": "paket_uebergeben",
                    "company_id": "7c2d5ee9-2a9a-5990-810f-502ea2b2012d",
                    "paket_id": "PROBE-2",
                    "uebergeben_am": "2026-09-10 14:32:11.123456+02"},
                   separators=(",", ":"), sort_keys=True).encode()
stempel = str(int(time.time()))
sig = hmac.new(geheim.encode(), stempel.encode() + b"." + rumpf, hashlib.sha256).hexdigest()
r = urllib.request.Request("https://bc2.02da.de/api/bc0/uebergabe", data=rumpf,
                           headers={"Content-Type": "application/json",
                                    "X-BC0-Timestamp": stempel,
                                    "X-BC0-Signature": "sha256=" + sig}, method="POST")
with urllib.request.urlopen(r) as a:
    print(a.getcode(), a.read().decode())
EOF
# -> 202 {"paket_id": "PROBE-2", "status": "angenommen"}
```

Proben hinterher entfernen: `PROBE-1` **und** `PROBE-2`.

Probe hinterher wieder entfernen:

```sql
DELETE FROM bc2.eingang WHERE paket_id = 'PROBE-1';
```

Der Vertragstest gegen die echte Datenbank macht dasselbe automatisiert:

```bash
BC2_ECHTE_DB=1 python -m pytest tests/test_vertrag_postgres.py -v
```

## 9. An BC0 übergeben

BC0s Code liest zwei Umgebungsvariablen (`bc0-baseline-onboarding/app/app.py:4325`).
Genau die beiden Werte braucht Simeon — **`BC2_HOOK_SECRET` per SMS**, der Rest
darf offen stehen:

```
BC2_HOOK_URL=https://bc2.02da.de/api/bc0/uebergabe
BC2_HOOK_SECRET=<derselbe Wert wie BC2_TRIGGER_TOKEN>
```

**Ein Geheimnis, eine SMS.** BC0 signiert damit, BC2 prüft damit; derselbe Wert
wird zusätzlich als `Authorization: Bearer` akzeptiert.

Danach ist Simeons Gegenprobe ein Klick auf **Übergabe** in BC0 — die Antwort
trägt `zustellung.ergebnis` und den HTTP-Code, und in `bc_zustellungen` steht
der Versuch.

---

## Nachhol-Abgleich

Kein Paket geht verloren, auf drei Wegen: der Ruf, BC0s
`POST …/uebergabe/nachliefern`, und BC2s Abgleich gegen
`public.v_uebergabe_offen` beim Start. Fällt BC2 aus, während BC0 überträgt,
holt BC2 das Paket beim nächsten Start selbst — dafür muss auf BC0s Seite
niemand etwas anstoßen. Von Hand anstoßen:

```bash
curl -X POST -H "Authorization: Bearer $BC2_TRIGGER_TOKEN" \
     https://bc2.02da.de/api/intern/abgleich
# -> {"nachgeholt": 2, "paket_ids": ["PKT-…","PKT-…"]}
```

**Kein Dauer-Polling** — die Festlegung aus
[#165](https://github.com/pg-coe-kmu/coe-factory/issues/165) bleibt.

## Aktualisieren

```bash
cd /opt/bc2 && git pull
cd bc2-strategic-advisor/app && docker compose up -d --build
```

Die `.env` bleibt dabei unberührt; sie ist nicht im Repo.
