# Health Analytic Service

A Django-based health analytics backend served with Gunicorn and backed by PostgreSQL, fully containerised with Docker.

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) (≥ 20.10)
- [Docker Compose](https://docs.docker.com/compose/install/) (v2+)

## Quick Start

```bash
# 1. Copy the example env file and edit secrets as needed
cp .env.example .env

# 2. Build and start all services
docker compose up --build
```

The first run will automatically:
- Apply all Django database migrations
- Collect static files
- Create a Django superuser from the `DJANGO_SUPERUSER_*` variables in `.env`

## Endpoints

| URL                                      | Description              |
|------------------------------------------|--------------------------|
| http://localhost:8000/healthcheck/        | Health-check (`{"status": "ok"}`) |
| http://localhost:8000/admin/              | Django admin panel       |

## Default Admin Credentials

Defined in `.env`:

| Variable                    | Default Value |
|-----------------------------|---------------|
| `DJANGO_SUPERUSER_USERNAME` | `admin`       |
| `DJANGO_SUPERUSER_PASSWORD` | `admin123`    |

> **⚠️ Change these credentials before deploying to production.**

## Development

The Docker image includes dev tools (mypy, flakeheaven). After building, run them with:

Run the type checker:

```bash
docker compose exec backend mypy .
```

Run the linter:

```bash
docker compose exec backend flakeheaven lint .
```

## Stopping the Services

```bash
docker compose down
```

To also remove the database volume:

```bash
docker compose down -v
```
