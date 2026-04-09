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

| Method   | URL                                                        | Description                                  |
|----------|------------------------------------------------------------|----------------------------------------------|
| `GET`    | http://localhost:8000/healthcheck/                         | Health-check (`{"status": "ok"}`)            |
|          | http://localhost:8000/admin/                               | Django admin panel                           |
|          | http://localhost:8000/api/v1/docs                          | Interactive Swagger UI (OpenAPI docs)        |
| **Patients CRUD** | | |
| `POST`   | http://localhost:8000/api/v1/patients/                     | Create a patient                             |
| `GET`    | http://localhost:8000/api/v1/patients/                     | List all patients                            |
| `GET`    | http://localhost:8000/api/v1/patients/{patient_id}         | Get a patient by `patient_id`                |
| `PUT`    | http://localhost:8000/api/v1/patients/{patient_id}         | Update a patient                             |
| `DELETE` | http://localhost:8000/api/v1/patients/{patient_id}         | Delete a patient                             |
| **Record Ingest** | | |
| `POST`   | http://localhost:8000/api/v1/records/                      | Upsert an ED visit record (idempotent)       |
| **Analytics (stubs)** | | |
| `GET`    | http://localhost:8000/api/v1/analytics/analytical_endpoint_1 | Analytics stub (returns `{}`)              |
| `GET`    | http://localhost:8000/api/v1/analytics/analytical_endpoint_2 | Analytics stub (returns `{}`)              |

> All `/api/v1/` endpoints require an `X-API-Key` header. Create an API key via the Django admin panel.

## Default Admin Credentials

Defined in `.env`:

| Variable                    | Default Value |
|-----------------------------|---------------|
| `DJANGO_SUPERUSER_USERNAME` | `admin`       |
| `DJANGO_SUPERUSER_PASSWORD` | `admin123`    |

> **⚠️ Change these credentials before deploying to production.**

## Development

The Docker image includes dev tools (mypy, flakeheaven) and test tools (pytest, factory-boy). After building, run them with:

### Running Tests

Run the full test suite (48 tests):

```bash
docker compose exec backend python -m pytest -v
```

Run tests with short tracebacks on failure:

```bash
docker compose exec backend python -m pytest -v --tb=short
```

Run a specific test file:

```bash
docker compose exec backend python -m pytest health_analytic_service/tests/test_models.py -v
```

Run a specific test class or test:

```bash
docker compose exec backend python -m pytest health_analytic_service/tests/test_record_api.py::TestRecordIngest::test_upsert_same_record_id -v
```

Run all tests:

```bash
docker compose exec backend python -m pytest -v
```

### Test Structure

| File                                          | Type        | Tests | Description                                      |
|-----------------------------------------------|-------------|-------|--------------------------------------------------|
| `health_analytic_service/tests/test_models.py`      | Unit        | 13    | Model creation, nullable fields, unique constraints, FK behaviour |
| `health_analytic_service/tests/test_schemas.py`     | Unit        | 7     | Pydantic schema validation, required/optional fields |
| `health_analytic_service/tests/test_patient_api.py` | Integration | 10    | Patient CRUD endpoints, 409 on duplicate         |
| `health_analytic_service/tests/test_record_api.py`  | Integration | 7     | Record upsert, partial payloads, patient get-or-create |
| `health_analytic_service/tests/test_auth.py`        | Integration | 6     | API key auth: missing, invalid, inactive → 401   |
| `health_analytic_service/tests/test_throttling.py`  | Integration | 1     | Rate limiting returns 429 after threshold        |
| `analytics/tests/test_analytics_api.py`             | Integration | 4     | Analytics stubs return 200, require auth         |

### Linting & Type Checking

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
