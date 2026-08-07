# BC0 Onboarding-Tool – Container
FROM python:3.12-slim

WORKDIR /app

# Abhängigkeiten zuerst (besseres Layer-Caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App-Code
COPY . .

# DB liegt auf dem persistenten Volume (siehe docker-compose.yml)
ENV BC0_DB=/data/bc0.db
EXPOSE 8000

CMD ["python", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
