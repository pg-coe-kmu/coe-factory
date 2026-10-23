# BC1 Interactive Context Discovery — Dienst (FastAPI)
FROM python:3.12-slim

# uv aus dem offiziellen Image, feste Version (nicht latest) — gleiche Abhaengigkeiten
# auf jedem Rechner.
COPY --from=ghcr.io/astral-sh/uv:0.11.32 /uv /usr/local/bin/uv

WORKDIR /app

# Abhaengigkeiten zuerst (besseres Layer-Caching). uv.lock ist die Wahrheit fuer die
# Versionen: --frozen loest nichts nach, nur die Gruppe service, keine Dev-Pakete.
# UV_PYTHON_DOWNLOADS=never: das Python des Basis-Images nehmen, keines nachladen.
ENV UV_PYTHON_DOWNLOADS=never \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --group service --no-install-project

# Code — Tests, Doku, Snapshots und .env bleiben draussen (.dockerignore).
COPY bc1_core/ bc1_core/
COPY bc1_service/ bc1_service/

# Kein root-Betrieb (BC0-Lehre #210): eigener Benutzer ohne Login-Shell.
RUN useradd --system --no-create-home --shell /usr/sbin/nologin bc1
USER bc1

EXPOSE 8000

# Datenbank, LLM-Key und BC0-Zugang kommen zur Laufzeit aus der Umgebung (-e),
# ein Snapshot (BC1_SNAPSHOT_PFAD) wird gemountet, nie ins Image kopiert.
#
# Bewusst OHNE --proxy-headers --forwarded-allow-ips "*" (anders als BC0/BC2): das
# ist nur vertretbar, wenn der Port ausschliesslich hinter einem Reverse Proxy im
# Docker-Netz liegt. Das BC1-Hosting ist noch nicht entschieden — beim Betrieb
# hinter einem Reverse Proxy die Flags nachziehen, mit der konkreten Proxy-Adresse.
CMD ["/app/.venv/bin/python", "-m", "uvicorn", "bc1_service.main:app", "--host", "0.0.0.0", "--port", "8000"]
