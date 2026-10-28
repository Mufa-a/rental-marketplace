# Production image for the Django API. Build: docker build -t nyumbani-backend backend/
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DJANGO_SETTINGS_MODULE=config.settings.prod

WORKDIR /app
RUN useradd --create-home --uid 10001 app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Collect Django admin static files at build time. The values below exist only for this
# command (production settings refuse to start without them); real ones come from the environment.
RUN DJANGO_SECRET_KEY=collectstatic-only ALLOWED_HOSTS=build.invalid AFRICASTALKING_USERNAME=x AFRICASTALKING_API_KEY=x \
    R2_PRIVATE_BUCKET_NAME=x python manage.py collectstatic --noinput \
    && mkdir -p /app/private_media && chown -R app:app /app/private_media

USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz/', timeout=4).status == 200 else 1)"

# Migrations are run as a separate, explicit release step (see docs/DEPLOYMENT.md), never on boot.
CMD ["sh", "-c", "exec gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers ${WEB_CONCURRENCY:-3} --timeout 30 --access-logfile - --forwarded-allow-ips='*'"]
