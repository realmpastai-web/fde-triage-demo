FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 TRIAGE_DATA_DIR=/app/var
WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .

COPY data ./data
COPY evals ./evals

RUN useradd --create-home --uid 10001 app && mkdir -p /app/var /app/reports && chown -R app /app/var /app/reports
USER app

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz')"
# Triage the client export on boot, then serve. Data dir is a volume so the audit log survives restarts.
CMD ["sh", "-c", "python -m triage eval --out /app/reports >/dev/null && python -m triage run && python -m triage serve --host 0.0.0.0 --port 8000"]
