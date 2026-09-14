# BC2 Strategic Advisor — Trigger-Endpunkt
FROM python:3.12-slim

WORKDIR /app

# Abhaengigkeiten zuerst (besseres Layer-Caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# --proxy-headers: Hinter Caddy kaeme sonst bei jeder Anfrage nur Caddys IP an.
#
# --forwarded-allow-ips "*" heisst: jedem Absender wird sein X-Forwarded-For
# geglaubt. Vertretbar ist das hier aus genau einem Grund, der ausgesprochen
# gehoert: Port 8000 steht in docker-compose.yml unter `expose`, nicht unter
# `ports`. Er ist damit nur im Docker-Netz erreichbar, und dort spricht nur
# Caddy. **Wird der Port jemals nach aussen gelegt, ist diese Zeile eine
# Luecke** — dann gehoert hier die konkrete Adresse des Proxys hin.
# (Uebernommen aus BC0s Dockerfile, Befund A6.)
CMD ["python", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000", \
     "--proxy-headers", "--forwarded-allow-ips", "*"]
