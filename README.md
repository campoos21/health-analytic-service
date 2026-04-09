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
| `GET`    | http://localhost:8000/api/v1/patients/                     | List patients (paginated, no PII)            |
| `GET`    | http://localhost:8000/api/v1/patients/{patient_id}         | Get a patient by `patient_id`                |
| `PUT`    | http://localhost:8000/api/v1/patients/{patient_id}         | Update a patient                             |
| `DELETE` | http://localhost:8000/api/v1/patients/{patient_id}         | Delete a patient                             |
| **Record Ingest** | | |
| `POST`   | http://localhost:8000/api/v1/records/                      | Upsert an ED visit record (idempotent)       |
| **Analytics** | | |
| `GET`    | http://localhost:8000/api/v1/analytics/visit-durations        | Completed visit durations (seconds)        |
| `GET`    | http://localhost:8000/api/v1/analytics/incomplete-visits      | Incomplete / in-progress visits            |

> All `/api/v1/` endpoints require an `X-API-Key` header. Create an API key via the Django admin panel.

### Patient List Privacy

The `GET /api/v1/patients/` endpoint returns **paginated summaries** without PII fields (`ssn_last4`, `contact_phone`, `date_of_birth`). Only the single-patient endpoint `GET /api/v1/patients/{patient_id}` returns the full record including sensitive fields.

| Query param | Type  | Default | Description |
|-------------|-------|---------|-------------|
| `offset`    | `int` | `0`     | Number of results to skip |
| `limit`     | `int` | `20`    | Max results per page (capped at 100) |

## Security & Architecture

### API Key Management

- API keys are **masked** in the Django admin list view (only the first 8 characters are shown).
- The full key is displayed **only once** — immediately after creation via a flash message.
- Keys are **read-only** after creation (cannot be edited in the admin).

### Authentication Caching

API key lookups are cached in-memory (`LocMemCache`) for **60 seconds** to avoid a database query on every request. The cache is automatically invalidated when keys are deactivated.

### Concurrency Safety

Visit assembly (`assign_record_to_visit`) runs inside `transaction.atomic()` with `select_for_update()` row-level locks to prevent duplicate visits when records for the same patient are ingested concurrently.

### Error Sanitisation

Database integrity errors (e.g. duplicate `patient_id`) return a **generic 409** message (`"A record with this identifier already exists."`) instead of leaking internal DB details.

### CORS

Cross-origin requests are handled by `django-cors-headers`. Allowed origins are configurable via the `CORS_ALLOWED_ORIGINS` environment variable (comma-separated).

### Structured Logging

The service uses Django's `LOGGING` framework with console output. Log levels are configurable via `DJANGO_LOG_LEVEL` (default: `INFO`). Key events logged:

- Visit creation and record attachment (`analytics` logger)
- Authentication failures (`health_analytic_service` logger)
- Integrity constraint violations (`health_analytic_service` logger)

### Connection Pooling

Database connections are kept alive for **600 seconds** (`CONN_MAX_AGE`) by default, avoiding the overhead of opening/closing a connection per request. Configurable via `DB_CONN_MAX_AGE`.

## Data Model

### Core Models (`health_analytic_service`)

| Model       | Description |
|-------------|-------------|
| **ApiKey**  | API key for authenticating external clients. |
| **Patient** | A patient that may appear across multiple ED visits. |
| **Record**  | A single ED visit event (e.g. REGISTRATION, TRIAGE, DEPARTURE). Linked to a Patient and a Visit. |

### Analytics Models (`analytics`)

| Model     | Description |
|-----------|-------------|
| **Visit** | Aggregates multiple Record events into a single ED visit for one patient. |

### Visit Assembly

When a `Record` is ingested via `POST /api/v1/records/`, the system automatically groups it into a **Visit**:

- **REGISTRATION** events always open a new visit.
- Subsequent events (TRIAGE, BED_ASSIGNMENT, TREATMENT, DISPOSITION, DEPARTURE) attach to the current open visit for that patient.
- A **DEPARTURE** event marks the visit as `COMPLETED`.
- If the time gap between events exceeds a configurable threshold (default **24 hours**), a new visit is created.

Each Visit stores **per-stage timestamps** directly:

| Field               | Set by event type |
|---------------------|-------------------|
| `registration_at`   | REGISTRATION      |
| `triage_at`         | TRIAGE            |
| `bed_assignment_at` | BED_ASSIGNMENT    |
| `treatment_at`      | TREATMENT         |
| `disposition_at`    | DISPOSITION       |
| `departure_at`      | DEPARTURE         |

#### Handling Missing Events

ED systems may have inconsistent data. The Visit model handles this gracefully:

| Scenario | Behaviour |
|----------|-----------|
| Missing REGISTRATION | Visit is created with `is_registration_missing = True`. Events still group by time proximity. |
| Missing DEPARTURE | Visit stays `IN_PROGRESS` with `is_departure_missing = True`. |
| Both present | Visit is `COMPLETED` with both flags `False`. |

#### Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `VISIT_GAP_THRESHOLD_HOURS` | `24` | Max gap (hours) between events in the same visit. Configurable via environment variable. |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:3000` | Comma-separated list of allowed origins for cross-origin requests. |
| `DJANGO_LOG_LEVEL` | `INFO` | Root logger level (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`). |
| `DB_CONN_MAX_AGE` | `600` | Persistent database connection lifetime in seconds (`0` = close after each request). |

### Analytical Endpoints

Both endpoints query the **Visit** model, support date-range filtering on `registration_at`, offset/limit pagination, API-key authentication, and rate limiting.

#### `GET /api/v1/analytics/visit-durations`

Returns the duration (in whole seconds) of every **completed** visit — i.e. visits that have both `registration_at` and `departure_at`.

| Query param | Type       | Default | Description |
|-------------|------------|---------|-------------|
| `date_from` | `datetime` | —       | Include visits registered **on or after** this timestamp |
| `date_to`   | `datetime` | —       | Include visits registered **on or before** this timestamp |
| `offset`    | `int`      | `0`     | Number of results to skip (pagination) |
| `limit`     | `int`      | `20`    | Max results per page (capped at 100) |

Example response:

```json
{
  "count": 42,
  "results": [
    {
      "id": 7,
      "patient_id": "PAT-001",
      "registration_at": "2026-04-01T08:00:00Z",
      "departure_at": "2026-04-01T10:30:00Z",
      "duration_seconds": 9000
    }
  ]
}
```

#### `GET /api/v1/analytics/incomplete-visits`

Returns visits that are **not** completed — status `IN_PROGRESS` or `INCOMPLETE` — along with their missing-boundary flags.

| Query param | Type       | Default | Description |
|-------------|------------|---------|-------------|
| `date_from` | `datetime` | —       | Include visits registered **on or after** this timestamp |
| `date_to`   | `datetime` | —       | Include visits registered **on or before** this timestamp |
| `offset`    | `int`      | `0`     | Number of results to skip (pagination) |
| `limit`     | `int`      | `20`    | Max results per page (capped at 100) |

Example response:

```json
{
  "count": 5,
  "results": [
    {
      "id": 12,
      "patient_id": "PAT-003",
      "status": "IN_PROGRESS",
      "is_registration_missing": false,
      "is_departure_missing": true,
      "registration_at": "2026-04-09T14:00:00Z"
    }
  ]
}
```

## Default Admin Credentials

Defined in `.env`:

| Variable                    | Default Value |
|-----------------------------|---------------|
| `DJANGO_SUPERUSER_USERNAME` | `admin`       |
| `DJANGO_SUPERUSER_PASSWORD` | `admin123`    |

> **⚠️ Change these credentials before deploying to production.**

## Development

The source code is bind-mounted into the container (`./:/app`), so local changes are reflected immediately without rebuilding.

The Docker image includes dev tools (mypy, flakeheaven) and test tools (pytest, factory-boy). After building, run them with:

### Running Tests

Run the full test suite (92 tests):

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

### Generating Migrations

When models are changed, generate and apply migrations inside the container:

```bash
docker compose run --rm --entrypoint "" backend python manage.py makemigrations
docker compose run --rm --entrypoint "" backend python manage.py migrate
```

### Test Structure

| File                                          | Type        | Tests | Description                                      |
|-----------------------------------------------|-------------|-------|--------------------------------------------------|
| `health_analytic_service/tests/test_models.py`      | Unit        | 13    | Model creation, nullable fields, unique constraints, FK behaviour |
| `health_analytic_service/tests/test_schemas.py`     | Unit        | 7     | Pydantic schema validation, required/optional fields |
| `health_analytic_service/tests/test_patient_api.py` | Integration | 11    | Patient CRUD, pagination, PII exclusion, 409 on duplicate |
| `health_analytic_service/tests/test_record_api.py`  | Integration | 7     | Record upsert, partial payloads, patient get-or-create |
| `health_analytic_service/tests/test_auth.py`        | Integration | 6     | API key auth: missing, invalid, inactive → 401   |
| `health_analytic_service/tests/test_throttling.py`  | Integration | 1     | Rate limiting returns 429 after threshold        |
| `analytics/tests/test_analytics_api.py`             | Integration | 15    | Visit durations & incomplete visits: filtering, pagination, auth |
| `analytics/tests/test_visit_model.py`               | Unit        | 10    | Visit model creation, properties, cascade delete, ordering |
| `analytics/tests/test_visit_assembly.py`            | Unit + Int  | 22    | Visit assembly: full lifecycle, missing events, time-gap splitting, idempotency, API integration |

### Linting & Type Checking

Run the type checker:

```bash
docker compose exec backend mypy analytics/ health_analytic_service/ --ignore-missing-imports
```

Run the linter:

```bash
docker compose exec backend flakeheaven lint analytics/ health_analytic_service/ --exclude="*/migrations/*"
```

## Stopping the Services

```bash
docker compose down
```

To also remove the database volume:

```bash
docker compose down -v
```
