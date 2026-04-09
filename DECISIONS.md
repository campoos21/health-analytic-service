# Design Decisions, Assumptions & Tradeoffs

This document captures the key architectural choices made while building the Health Analytic Service, the assumptions behind them, and their tradeoffs.

---

## 1. Framework: Django + Django Ninja

**Decision:** Use Django 4.2 LTS with Django Ninja instead of Django REST Framework (DRF) or FastAPI.

**Rationale:**
- Django provides a battle-tested ORM, migrations, admin panel, and middleware ecosystem — all critical for a health data service that needs reliability.
- Django Ninja gives us Pydantic-based request/response validation with automatic OpenAPI docs, combining DRF's productivity with FastAPI's ergonomics.
- Django 4.2 is the current LTS release, ensuring long-term security patches.

**Tradeoff:** Django Ninja is less widely adopted than DRF, so some team members may be less familiar with it. However, the learning curve is small and the Swagger UI at `/api/v1/docs` helps discoverability.

---

## 2. Two-App Architecture

**Decision:** Split the project into two Django apps — `health_analytic_service` (core domain) and `analytics` (visit aggregation & analytical endpoints).

**Rationale:**
- **Separation of concerns** — the core app owns patients, records, auth, and ingest; the analytics app owns visit assembly and analytical queries.
- This allows the analytics layer to evolve independently (e.g. adding new aggregation endpoints) without touching the ingest pipeline.
- Each app has its own models, services, schemas, and tests.

**Tradeoff:** Two apps add some import overhead and a foreign key across app boundaries (`Record.visit → analytics.Visit`). We accept this for cleaner boundaries.

---

## 3. Visit Assembly On Ingest (Synchronous)

**Decision:** Group records into visits synchronously during `POST /records/` rather than via a background job or batch process.

**Rationale:**
- Visits are immediately available for querying after ingest — no eventual-consistency delay.
- The assembly logic is lightweight (one or two DB queries per record), so it doesn't materially slow down the ingest endpoint.
- Simpler infrastructure — no message queue (Celery, RabbitMQ) needed.

**Assumption:** Ingest volume is moderate (hundreds/thousands of records per minute, not millions). If throughput requirements grow significantly, moving assembly to an async worker would be the next step.

**Tradeoff:** A very high burst of concurrent records for the same patient could create contention on row-level locks. We mitigate this with `transaction.atomic()` + `select_for_update()`.

---

## 4. Time-Proximity Heuristic for Visit Grouping

**Decision:** Use a configurable time-gap threshold (`VISIT_GAP_THRESHOLD_HOURS`, default 24h) to group events into visits when boundary events are missing.

**Rationale:**
- Real-world ED systems often have missing or out-of-order REGISTRATION/DEPARTURE events.
- A time-based heuristic is simple, predictable, and works well for the vast majority of cases.
- The threshold is configurable per deployment — hospitals with shorter average stays can lower it.

**Assumption:** Events for the same patient that are more than 24 hours apart almost certainly belong to different visits.

**Tradeoff:** Edge cases exist — a patient who stays 25+ hours in the ED with a missing REGISTRATION could be split into two visits. The `is_registration_missing` flag makes this detectable and auditable.

---

## 5. Denormalised Stage Timestamps on Visit

**Decision:** Store each event-stage timestamp (`registration_at`, `triage_at`, `bed_assignment_at`, etc.) directly on the `Visit` model rather than joining back to `Record` rows.

**Rationale:**
- Analytical queries (duration calculations, stage timelines) can read a single row instead of joining six records.
- The `/visit-durations` endpoint uses `F('departure_at') - F('registration_at')` as a pure DB annotation — no Python-level computation needed.

**Tradeoff:** Data is duplicated between `Record.timestamp` and `Visit.<stage>_at`. The `_refresh_visit()` function keeps them in sync on every ingest, so the denormalisation is maintained automatically.

---

## 6. Offset/Limit Pagination (Not Cursor-Based)

**Decision:** Use simple `offset`/`limit` pagination for all list endpoints, capped at 100 results per page.

**Rationale:**
- Simple to implement, understand, and use from any HTTP client.
- The current dataset size (thousands of visits) doesn't warrant cursor-based pagination.
- The response includes `count` (total matching rows) so consumers know the full result size.

**Tradeoff:** Offset pagination degrades on very large datasets (high offsets cause sequential scans). If the dataset grows to millions of rows, switching to keyset/cursor pagination would be recommended.

---

## 7. API Key Authentication (Not JWT/OAuth)

**Decision:** Authenticate API consumers via a static `X-API-Key` header rather than JWT tokens or OAuth 2.0.

**Rationale:**
- API keys are the simplest model for service-to-service communication, which is the primary use case (EHR systems pushing records).
- No token refresh flow needed — keys are long-lived and can be rotated via the admin panel.
- Keys are cached in-memory (60s TTL) to avoid a DB query on every request.

**Assumption:** The service is consumed by backend systems, not directly by end users in browsers. If browser-based access is needed later, adding OAuth 2.0 alongside API keys would be straightforward.

**Tradeoff:** API keys don't carry claims or scopes — every key has the same access level. Role-based access (e.g. read-only analytics keys vs. full ingest keys) would require extending the `ApiKey` model with a `scope` field.

---

## 8. PII Protection in List Endpoints

**Decision:** The patient list endpoint (`GET /patients/`) returns `PatientSummaryOut` (id, patient_id, patient_name only). Sensitive fields (`ssn_last4`, `contact_phone`, `date_of_birth`) are only returned on the single-patient detail endpoint.

**Rationale:**
- Minimises PII exposure surface — a single API call cannot dump all patients' sensitive data.
- Follows the principle of least privilege for a health analytics service.
- The detail endpoint still returns full PII for legitimate use cases (patient lookup by ID).

**Tradeoff:** Consumers that need PII for a batch of patients must make N individual requests. This is intentional friction for sensitive data access.

---

## 9. Race Condition Mitigation via Row-Level Locks

**Decision:** The `assign_record_to_visit()` function wraps all logic in `transaction.atomic()` and uses `select_for_update()` when querying open visits.

**Rationale:**
- Concurrent ingestion of events for the same patient (e.g. from parallel HL7 feeds) could otherwise create duplicate visits.
- Row-level locks serialise access per-patient without blocking unrelated patients.

**Tradeoff:** Under very high concurrency for the same patient, requests will queue on the lock. This is acceptable because events for one patient rarely arrive simultaneously, and the critical section is small (< 10ms).

---

## 10. In-Memory Cache for Auth (LocMemCache)

**Decision:** Use Django's `LocMemCache` (process-local memory) to cache API key lookups for 60 seconds, rather than Redis or Memcached.

**Rationale:**
- Zero additional infrastructure — no Redis container needed.
- With Gunicorn's 3 workers, each process maintains its own cache, which is acceptable for a small key set.
- 60-second TTL means a deactivated key is rejected within at most 1 minute.

**Tradeoff:** Each Gunicorn worker has its own cache, so deactivation takes effect independently per worker. For stricter real-time revocation, switching to Redis would allow a single shared cache with pub/sub invalidation.

---

## 11. CONN_MAX_AGE for Connection Pooling

**Decision:** Set `CONN_MAX_AGE=600` (10 minutes) to reuse database connections across requests.

**Rationale:**
- Django's default (`CONN_MAX_AGE=0`) opens and closes a TCP connection to PostgreSQL on every request, which adds ~2-5ms of latency.
- With Gunicorn (3 workers × 2 threads = 6 connections max), persistent connections are safe and reduce DB overhead.

**Tradeoff:** Idle connections consume PostgreSQL memory. With 6 max connections this is negligible, but should be reconsidered if the worker count increases significantly.

---

## 12. CORS Configuration

**Decision:** Enable CORS via `django-cors-headers` with explicitly allowed origins (configurable via `CORS_ALLOWED_ORIGINS` env var).

**Rationale:**
- Required if any browser-based frontend or dashboard needs to call the API.
- Explicit origin allowlist (not `*`) follows security best practices.
- The `x-api-key` header is included in `CORS_ALLOW_HEADERS` so browsers can send it in preflight requests.
