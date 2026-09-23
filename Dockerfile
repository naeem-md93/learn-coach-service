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
CMD ["sh", "-c", "python manage.py migrate --noinput && python manage.py collectstatic --noinput && gunicorn lc_service.api.wsgi:application --bind 0.0.0.0:$PORT"]
