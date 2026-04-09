# Integration Guide — Health Analytic Service

> Written for Lakeview Health Network's engineering team.

This document explains how to set up, run, and integrate with the Health Analytic Service — an ED (Emergency Department) visit analytics backend that ingests event records, assembles them into visits, and exposes analytical endpoints.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Setup & First Run](#setup--first-run)
3. [Creating API Keys](#creating-api-keys)
4. [Ingesting Records](#ingesting-records)
5. [Querying Analytical Endpoints](#querying-analytical-endpoints)
6. [Patient Management](#patient-management)
7. [How Visit Assembly Works](#how-visit-assembly-works)
8. [Environment Variables Reference](#environment-variables-reference)
9. [Running Tests](#running-tests)
10. [Monitoring & Logging](#monitoring--logging)
11. [Stopping & Resetting](#stopping--resetting)
12. [Troubleshooting](#troubleshooting)

---

## Prerequisites

| Requirement | Minimum version |
|---|---|
| [Docker](https://docs.docker.com/get-docker/) | 20.10+ |
| [Docker Compose](https://docs.docker.com/compose/install/) | v2+ |

No local Python, PostgreSQL, or other dependencies are required — everything runs inside Docker containers.

---

## Setup & First Run

### 1. Clone the repository

```bash
git clone <repository-url>
cd health-analytic-service
```

### 2. Create your environment file

```bash
cp .env.example .env
```

Open `.env` and update:
- `DJANGO_SECRET_KEY` — set to a long random string (use `python -c "import secrets; print(secrets.token_urlsafe(50))"`)
- `POSTGRES_PASSWORD` — set to a strong database password
- `DJANGO_SUPERUSER_PASSWORD` — set to a strong admin password
- `CORS_ALLOWED_ORIGINS` — set to the URLs of any frontends that will call the API

### 3. Build and start

```bash
docker compose up --build
```

On first start, the entrypoint script automatically:
1. Applies all database migrations
2. Collects static files
3. Creates a Django superuser (from `DJANGO_SUPERUSER_*` env vars)
4. Starts Gunicorn on port **8000**

### 4. Verify the service is running

```bash
curl http://localhost:8000/healthcheck/
# → {"status": "ok"}
```

---

## Creating API Keys

All API endpoints require authentication via an `X-API-Key` header.

### Via the Django Admin

1. Open http://localhost:8000/admin/
2. Log in with your superuser credentials (from the `.env` file)
3. Go to **API Keys → Add API Key**
4. Enter a descriptive name (e.g. `ehr-integration-prod`)
5. Click **Save**
6. **Copy the full key from the green banner immediately** — it will not be shown again

The key will appear masked (`abcdef12***`) in subsequent views.

### Using the key

Include it in every API request:

```bash
curl -H "X-API-Key: <your-key>" http://localhost:8000/api/v1/patients/
```

---

## Ingesting Records

The primary integration point is `POST /api/v1/records/` — your EHR system sends ED event records here.

### Endpoint

```
POST /api/v1/records/
Content-Type: application/json
X-API-Key: <your-key>
```

### Payload

Only `record_id` is required. All other fields are optional to support partial payloads, duplicate sends, and out-of-order events.

```json
{
  "record_id": "REC-20260409-001",
  "patient_id": "PAT-12345",
  "patient_name": "Jane Smith",
  "date_of_birth": "1985-06-15",
  "ssn_last4": "5678",
  "contact_phone": "555-0100",
  "facility": "Lakeview ED - Main Campus",
  "timestamp": "2026-04-09T08:00:00Z",
  "event_type": "REGISTRATION",
  "acuity_level": 3,
  "chief_complaint": "Chest pain",
  "disposition": null,
  "diagnosis_codes": ["R07.9"]
}
```

### Key behaviours

| Behaviour | Details |
|---|---|
| **Idempotent** | Sending the same `record_id` twice updates the record (200), not duplicates it (201 on first send). |
| **Partial upsert** | Only non-null fields overwrite existing values. Re-sending `{"record_id": "REC-001"}` alone won't erase previously ingested fields. |
| **Patient auto-creation** | If `patient_id` is present and the patient doesn't exist, it's created automatically. If it exists, patient-level fields are merged. |
| **Visit assembly** | After every ingest, the record is automatically assigned to a Visit (see [How Visit Assembly Works](#how-visit-assembly-works)). |

### Event types

Send these values in the `event_type` field to track the patient journey:

| Event type | When to send |
|---|---|
| `REGISTRATION` | Patient arrives and is registered |
| `TRIAGE` | Patient is triaged |
| `BED_ASSIGNMENT` | Patient is assigned a bed |
| `TREATMENT` | Treatment begins |
| `DISPOSITION` | Discharge/admit decision is made |
| `DEPARTURE` | Patient physically leaves the ED |

### Disposition values

| Value | Meaning |
|---|---|
| `DISCHARGED` | Patient discharged home |
| `ADMITTED` | Patient admitted to hospital |
| `TRANSFERRED` | Patient transferred to another facility |
| `LEFT_WITHOUT_TREATMENT` | Patient left before treatment |

### Example: full patient journey

```bash
API="http://localhost:8000/api/v1/records/"
KEY="X-API-Key: <your-key>"
CT="Content-Type: application/json"

# 1. Registration
curl -X POST "$API" -H "$KEY" -H "$CT" -d '{
  "record_id": "REC-001", "patient_id": "PAT-100",
  "patient_name": "Jane Smith", "facility": "Lakeview ED",
  "timestamp": "2026-04-09T08:00:00Z", "event_type": "REGISTRATION",
  "acuity_level": 3, "chief_complaint": "Chest pain"
}'

# 2. Triage (15 min later)
curl -X POST "$API" -H "$KEY" -H "$CT" -d '{
  "record_id": "REC-002", "patient_id": "PAT-100",
  "timestamp": "2026-04-09T08:15:00Z", "event_type": "TRIAGE"
}'

# 3. Bed assignment
curl -X POST "$API" -H "$KEY" -H "$CT" -d '{
  "record_id": "REC-003", "patient_id": "PAT-100",
  "timestamp": "2026-04-09T08:30:00Z", "event_type": "BED_ASSIGNMENT"
}'

# 4. Treatment
curl -X POST "$API" -H "$KEY" -H "$CT" -d '{
  "record_id": "REC-004", "patient_id": "PAT-100",
  "timestamp": "2026-04-09T09:00:00Z", "event_type": "TREATMENT"
}'

# 5. Disposition
curl -X POST "$API" -H "$KEY" -H "$CT" -d '{
  "record_id": "REC-005", "patient_id": "PAT-100",
  "timestamp": "2026-04-09T10:00:00Z", "event_type": "DISPOSITION",
  "disposition": "DISCHARGED"
}'

# 6. Departure
curl -X POST "$API" -H "$KEY" -H "$CT" -d '{
  "record_id": "REC-006", "patient_id": "PAT-100",
  "timestamp": "2026-04-09T10:30:00Z", "event_type": "DEPARTURE"
}'
```

After this sequence, a `COMPLETED` visit exists with a duration of **9000 seconds** (2.5 hours).

---

## Querying Analytical Endpoints

### Visit Durations

Returns the time (in seconds) between registration and departure for every completed visit.

```bash
curl -H "X-API-Key: <your-key>" \
  "http://localhost:8000/api/v1/analytics/visit-durations"
```

**Filtering by date range:**

```bash
curl -H "X-API-Key: <your-key>" \
  "http://localhost:8000/api/v1/analytics/visit-durations?date_from=2026-04-01T00:00:00Z&date_to=2026-04-09T23:59:59Z"
```

**Paginating:**

```bash
curl -H "X-API-Key: <your-key>" \
  "http://localhost:8000/api/v1/analytics/visit-durations?offset=0&limit=50"
```

**Response:**

```json
{
  "count": 42,
  "results": [
    {
      "id": 7,
      "patient_id": "PAT-100",
      "registration_at": "2026-04-09T08:00:00Z",
      "departure_at": "2026-04-09T10:30:00Z",
      "duration_seconds": 9000
    }
  ]
}
```

### Incomplete Visits

Returns visits that are still open (`IN_PROGRESS`) or missing boundary events (`INCOMPLETE`).

```bash
curl -H "X-API-Key: <your-key>" \
  "http://localhost:8000/api/v1/analytics/incomplete-visits"
```

**Response:**

```json
{
  "count": 5,
  "results": [
    {
      "id": 12,
      "patient_id": "PAT-200",
      "status": "IN_PROGRESS",
      "is_registration_missing": false,
      "is_departure_missing": true,
      "registration_at": "2026-04-09T14:00:00Z"
    }
  ]
}
```

Use `is_registration_missing` and `is_departure_missing` flags to identify data quality issues in your EHR feed.

### Query Parameters (both endpoints)

| Param | Type | Default | Description |
|---|---|---|---|
| `date_from` | ISO 8601 datetime | — | Filter by `registration_at >= date_from` |
| `date_to` | ISO 8601 datetime | — | Filter by `registration_at <= date_to` |
| `offset` | int | `0` | Skip this many results |
| `limit` | int | `20` | Max results per page (capped at 100) |

---

## Patient Management

### List patients (paginated, no PII)

```bash
curl -H "X-API-Key: <your-key>" \
  "http://localhost:8000/api/v1/patients/?offset=0&limit=20"
```

Returns `patient_id` and `patient_name` only — no SSN, phone, or date of birth.

### Get a single patient (includes PII)

```bash
curl -H "X-API-Key: <your-key>" \
  "http://localhost:8000/api/v1/patients/PAT-100"
```

### Create a patient manually

```bash
curl -X POST -H "X-API-Key: <your-key>" -H "Content-Type: application/json" \
  "http://localhost:8000/api/v1/patients/" \
  -d '{"patient_id": "PAT-NEW", "patient_name": "New Patient"}'
```

> **Note:** Patients are also auto-created during record ingest if `patient_id` is provided. Manual creation is only needed if you want to pre-populate patient records.

---

## How Visit Assembly Works

Every time a record is ingested, it is automatically grouped into a **Visit**:

1. **REGISTRATION** events always create a new visit.
2. Other events attach to the most recent open visit for that patient (if one exists within the time gap threshold).
3. If no compatible open visit exists, a new visit is created and flagged with `is_registration_missing = True`.
4. **DEPARTURE** events mark the visit as `COMPLETED`.
5. Events more than **24 hours** apart (configurable via `VISIT_GAP_THRESHOLD_HOURS`) are treated as belonging to different visits.

### Concurrency safety

Visit assembly runs inside a database transaction with row-level locks. Multiple records for the same patient can be ingested concurrently without creating duplicate visits.

### Missing event handling

| Scenario | What happens |
|---|---|
| No REGISTRATION received | Visit created with `is_registration_missing = True` |
| No DEPARTURE received | Visit stays `IN_PROGRESS` with `is_departure_missing = True` |
| Both present | Visit is `COMPLETED`, both flags `False` |

---

## Environment Variables Reference

| Variable | Default | Description |
|---|---|---|
| `DJANGO_SECRET_KEY` | `insecure-default-key-change-me` | Django cryptographic signing key — **must change in production** |
| `DJANGO_DEBUG` | `0` | Set to `1` for debug mode (never in production) |
| `DJANGO_ALLOWED_HOSTS` | `localhost` | Comma-separated allowed hostnames |
| `POSTGRES_DB` | `health_analytic_db` | PostgreSQL database name |
| `POSTGRES_USER` | `health_user` | PostgreSQL user |
| `POSTGRES_PASSWORD` | `change-me` | PostgreSQL password — **must change in production** |
| `POSTGRES_HOST` | `db` | Database hostname (Docker service name) |
| `POSTGRES_PORT` | `5432` | Database port |
| `DJANGO_SUPERUSER_USERNAME` | `admin` | Auto-created admin username |
| `DJANGO_SUPERUSER_EMAIL` | `admin@example.com` | Auto-created admin email |
| `DJANGO_SUPERUSER_PASSWORD` | `change-me` | Auto-created admin password — **must change in production** |
| `VISIT_GAP_THRESHOLD_HOURS` | `24` | Max hours between events in the same visit |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:3000` | Comma-separated allowed CORS origins |
| `DJANGO_LOG_LEVEL` | `INFO` | Root logger level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `DB_CONN_MAX_AGE` | `600` | DB connection lifetime in seconds |

---

## Running Tests

```bash
# Full suite (92 tests)
docker compose exec backend pytest -v

# Specific file
docker compose exec backend pytest analytics/tests/test_analytics_api.py -v

# With short tracebacks
docker compose exec backend pytest -v --tb=short
```

### Linting & type checking

```bash
# Linter
docker compose exec backend flakeheaven lint analytics/ health_analytic_service/ --exclude="*/migrations/*"

# Type checker
docker compose exec backend mypy analytics/ health_analytic_service/ --exclude="migrations/"
```

---

## Monitoring & Logging

The service outputs structured logs to stdout (captured by Docker). Key events logged:

| Event | Logger | Level |
|---|---|---|
| Visit created (REGISTRATION) | `analytics` | INFO |
| Visit created (missing registration) | `analytics` | INFO |
| Record re-attached to existing visit | `analytics` | DEBUG |
| Authentication failure | `health_analytic_service` | WARNING |
| IntegrityError (duplicate record) | `health_analytic_service` | WARNING |

View logs:

```bash
docker compose logs -f backend
```

### Rate limiting

All endpoints are rate-limited to **100 requests/minute** per API key. Exceeding the limit returns `429 Too Many Requests`.

### Health check

```bash
curl http://localhost:8000/healthcheck/
# → {"status": "ok"}
```

### Interactive API docs

Open http://localhost:8000/api/v1/docs for the Swagger UI with all endpoints, schemas, and a "Try it out" feature.

---

## Stopping & Resetting

```bash
# Stop all services (data preserved)
docker compose down

# Stop and delete all data (database, volumes)
docker compose down -v
```

---

## Troubleshooting

| Problem | Solution |
|---|---|
| `401 Unauthorized` | Check the `X-API-Key` header. The key must be active — verify in the admin panel. |
| `429 Too Many Requests` | You've exceeded 100 req/min. Wait 60 seconds or use a different API key. |
| `409 Conflict` | You tried to create a patient/record with a duplicate identifier. |
| `422 Unprocessable Entity` | Request body is invalid — check the error detail for the specific field. |
| Container won't start | Check `docker compose logs backend` for migration or connection errors. Ensure `.env` is present and `POSTGRES_PASSWORD` matches. |
| API key lost | Keys cannot be recovered after creation. Create a new one in the admin panel and deactivate the old one. |
| Visits not being created | Records need both `patient_id` and `timestamp` for visit assembly. Records without either are stored but not assigned to a visit. |
