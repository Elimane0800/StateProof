# StateProof backend image.
#
# Built from the REPO ROOT (not ./backend) so the ARIA agent pipeline
# (agents/), the checkpoint config (config/), and the demo ground-truth
# (demo/) all land in the image. The live /inspection/return path imports the
# `agents` package, which PYTHONPATH=/app makes resolvable.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

WORKDIR /app

# Install Python deps first for layer caching (backend + agents deps merged).
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# Application code + everything the live pipeline reads at runtime.
COPY backend/ ./backend/
COPY agents/ ./agents/
COPY config/ ./config/
COPY demo/ ./demo/
COPY packages/ ./packages/

EXPOSE 8080

# --app-dir puts backend/ on sys.path so `app.main` resolves, while
# PYTHONPATH=/app keeps the repo-root `agents` package importable.
CMD ["uvicorn", "app.main:app", "--app-dir", "backend", "--host", "0.0.0.0", "--port", "8080"]
