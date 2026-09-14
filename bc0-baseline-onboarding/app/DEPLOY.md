# BC0 Onboarding-Tool — Deployment (EU-VM, Docker)

**Ziel:** App läuft zentral unter einer URL. Nutzer brauchen nur einen Browser — **keine Installation**. Zentrale DB bleibt erhalten.

*Ersteller: Simeon Ehmer | Version v1.0 | Stand 22.06.2026*

> **Status:** vorbereitet. Ausführen, sobald der Team-Beschluss zum Hosting steht.

---

## Was im Paket liegt (Ordner `BC0_App/`)

| Datei | Zweck |
|---|---|
| `Dockerfile` | Container-Bauanleitung für die FastAPI-App |
| `docker-compose.yml` | App + Caddy (Reverse-Proxy/HTTPS) + persistente Volumes |
| `Caddyfile` | Reverse-Proxy, automatisches HTTPS bei eigener Domain |
| `.env.example` | Konfiguration (Domain) — nach `.env` kopieren |
| `.dockerignore` | hält DB/Cache aus dem Image |

Die SQLite-DB liegt auf einem **Docker-Volume** (`bc0_data`) → bleibt bei Updates erhalten.

---

## Schritt für Schritt (Hetzner-VM, Ubuntu)

**1. VM anlegen.** Hetzner Cloud, z. B. **CX33** (Falkenstein/Nürnberg), Ubuntu 22.04/24.04. Firewall: nur **22 (SSH), 80, 443** offen.

**2. Docker installieren.**
```bash
curl -fsSL https://get.docker.com | sh
```

**3. App auf die VM bringen** (eine Variante wählen):
```bash
# per Git (wenn das Repo erreichbar ist):
git clone <REPO_URL> && cd coe-factory/BC0_App
# ODER per scp vom eigenen Rechner:
#   scp -r "BC0_App" root@<VM-IP>:/opt/bc0 && cd /opt/bc0
```

**4. Konfiguration setzen.**
```bash
cp .env.example .env
# Ohne Domain (Test):   DOMAIN=:80   (Aufruf per http://<VM-IP>/)
# Mit Domain (HTTPS):   DOMAIN=bc0.eure-domain.de   (DNS-A-Record vorher auf VM-IP setzen)
nano .env
```

**5. Starten.**
```bash
docker compose up -d --build
```
Aufruf: `http://<VM-IP>/` bzw. `https://bc0.eure-domain.de` — **fertig, ohne Installation für Nutzer.**

**6. (Optional) NoroAI-Demodaten einspielen.**
```bash
docker compose exec app python seed_noroai.py
```

---

## Betrieb

- **Logs:** `docker compose logs -f`
- **Update (neuer Code):** `git pull` (bzw. neu kopieren) → `docker compose up -d --build` (DB bleibt im Volume).
- **Backup der DB:**
  ```bash
  docker run --rm -v bc0_app_bc0_data:/data -v $PWD:/backup alpine \
    cp /data/bc0.db /backup/bc0_backup_$(date +%F).db
  ```
  (Volume-Name ggf. mit `docker volume ls` prüfen.)
- **Stoppen:** `docker compose down` (Daten bleiben; `-v` würde sie löschen — **nicht** im Normalbetrieb).

---

## Hinweise

- **HTTPS** kommt automatisch, sobald in `.env` eine echte Domain steht (Let's Encrypt via Caddy). Ohne Domain läuft die App über HTTP — für Tests/intern ok.
- **PWA-„Installieren"** im Browser bietet sich erst mit HTTPS sauber an. Wer das will: dieselben Deploy-Dateien in den Ordner `BC0_App_PWA/` kopieren und von dort bauen.
- **DSGVO:** EU/DE-Region, **AVV** mit dem Anbieter abschließen, einmal mit der/dem Datenschutzbeauftragten gegenchecken (fremde KMU-Daten).
- **DB-Engine:** vorerst SQLite (reicht, läuft im Container). Spätere Migration auf PostgreSQL ändert nur den Hintergrund — der Schnittstellen-Vertrag (Snapshot/API) bleibt gleich.
