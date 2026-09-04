# BC0 Onboarding-Tool – Container
FROM python:3.12-slim

WORKDIR /app

# poppler-utils liefert `pdftotext` — den verlustfreien Weg aus Stufe 2
# (Beleg-Ingestion, Konzept vom 18.08.2026, Abschnitt 3). Rund 15 MB.
#
# WARUM DAS HIER STEHT UND NICHT IM OCR-CONTAINER: Es ist KEINE
# Zeichenerkennung. `pdftotext` liest eine vorhandene Textebene aus, Buchstabe
# fuer Buchstabe, in Millisekunden und hundertprozentig genau. Die eigentliche
# Erkennung (PaddleOCR) bekommt nach der Entscheidung vom 18.08. einen eigenen
# Container mit Speicherlimit und Warteschlange — die gehoert nicht hierher.
#
# Fehlt das Paket, laeuft die Anwendung weiter: `_pdftotext` faengt den
# OSError und der Beleg wartet auf den Worker. Genau dieser Zustand herrscht
# auf jedem Entwicklungsrechner.
RUN apt-get update \
 && apt-get install -y --no-install-recommends poppler-utils \
 && rm -rf /var/lib/apt/lists/*

# Abhängigkeiten zuerst (besseres Layer-Caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App-Code
COPY . .

# DB liegt auf dem persistenten Volume (siehe docker-compose.yml)
ENV BC0_DB=/data/bc0.db
EXPOSE 8000

# --proxy-headers (Punkt 47, Befund A6): Hinter dem Reverse Proxy kaeme sonst
# bei jeder Anfrage nur Caddys IP an. Jede Begrenzung je IP waere damit
# wirkungslos — sie zaehlte alle Nutzer als einen.
#
# --forwarded-allow-ips "*" heisst: JEDEM Absender wird sein X-Forwarded-For
# geglaubt. Das ist hier vertretbar, aber nur aus einem Grund, der ausgesprochen
# gehoert: Port 8000 steht in docker-compose.yml unter `expose`, nicht unter
# `ports`. Er ist damit ausschliesslich im Docker-Netz erreichbar, und dort
# spricht nur Caddy. **Wird der Port jemals nach aussen gelegt, ist diese Zeile
# eine Luecke** — dann gehoert hier die konkrete Adresse des Proxys hin.
CMD ["python", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000", \
     "--proxy-headers", "--forwarded-allow-ips", "*"]
