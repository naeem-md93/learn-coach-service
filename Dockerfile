FROM python:3.13-slim

# Prevent .pyc files and enable unbuffered stdout/stderr (so logs show up
# immediately in Railway's log stream).
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install dependencies first so this layer is cached unless requirements.txt
# changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# NOTE: migrate/collectstatic must NOT run here (at build time) — Railway's
# private network (e.g. the Postgres host on *.railway.internal) is only
# reachable at container runtime, not during the image build. Both run from
# the start command below instead, every time the container boots.
#
# Gunicorn tuning (timeout/workers/threads/worker-class): defaults below
# mirror lc_service.settings.project.GunicornSettings exactly, and can be
# overridden per-environment via the same GUNICORN_* env vars without an
# image rebuild. --timeout=60 must stay above resources/services.py's
# EXTRACT_TITLE_TIMEOUT_SECONDS=45 (Resource upload synchronously calls
# FastAPI, which can take up to 45s downloading+processing a large PDF) —
# gunicorn's own default of 30s was killing the worker (SIGKILL, "WORKER
# TIMEOUT") before our own timeout/fallback logic ever got a chance to run.
# --worker-class=gthread + --threads lets one slow upload's I/O wait not
# block other users' requests within the same worker process.
CMD ["sh", "-c", "python manage.py migrate --noinput && python manage.py collectstatic --noinput && gunicorn lc_service.api.wsgi:application --bind 0.0.0.0:$PORT --workers ${GUNICORN_WORKERS:-3} --worker-class ${GUNICORN_WORKER_CLASS:-gthread} --threads ${GUNICORN_THREADS:-2} --timeout ${GUNICORN_TIMEOUT:-60}"]
