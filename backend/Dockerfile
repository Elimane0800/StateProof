# Application Collection registry base (when pulling from dp.apps.rancher.io):
#   FROM dp.apps.rancher.io/library/python:3.12-slim
# Local hackathon builds use the public image; the application-collection pull
# secret still applies when deploying charts from the registry.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
