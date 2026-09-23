web: python manage.py migrate --noinput && python manage.py collectstatic --noinput && gunicorn lc_service.api.wsgi:application --bind 0.0.0.0:$PORT
