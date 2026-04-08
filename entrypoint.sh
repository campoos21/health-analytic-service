#!/bin/bash
set -e

echo "Applying database migrations..."
python manage.py migrate --noinput

echo "Collecting static files..."
python manage.py collectstatic --noinput

echo "Creating superuser (if it does not already exist)..."
python manage.py createsuperuser --noinput 2>/dev/null || true

echo "Starting Gunicorn..."
exec gunicorn health_analytic_service.wsgi:application -c gunicorn.conf.py
