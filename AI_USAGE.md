# AI Usage Log

## Tools Used

- **IDE** — Visual Studio Code
- **Github Copilot Agents** — Planning and Agent modes
- **Model** — Claude Opus 4.6

---

## 1. Project Scaffold

### Prompt

> I want a django app, ready to run, lets build a prompt for an agent to create this:
>
> django 4.2, postgress 16, docker, docker compose with 2 services (the backend itself and the database), define a persistent volume for the postgress database and also set the variables, for the db create a .env for the critical ones, gunicorn environment.
>
> I need this service ready to run.
> The project name will be: `health-analytic-service`

### Goal

Wanted to create a solid prompt/plan for the agent to follow, to create a Django service running with Docker Compose and Gunicorn.

### AI Response

<details>
<summary>Click to expand — generated plan</summary>

```
# Task: Create a fully runnable Django project from scratch

## Project Overview
- Project name: health-analytic-service (Python module: health_analytic_service)
- Working directory: /home/alexcampos/personal/health-analytic-service
- The workspace is completely empty — create every file from scratch.
- The project must be ready to run with a single `docker compose up --build` command.

## Tech Stack & Versions
| Component        | Version / Tool       |
|------------------|----------------------|
| Python           | 3.11 (slim image)    |
| Django           | 4.2.*                |
| PostgreSQL       | 16                   |
| WSGI Server      | Gunicorn             |
| Containerization | Docker + Compose     |

## File Tree to Create

health-analytic-service/
├── docker-compose.yml
├── Dockerfile
├── .env                    # actual secrets (git-ignored)
├── .env.example            # safe placeholder copy
├── .gitignore
├── .dockerignore
├── requirements.txt
├── gunicorn.conf.py
├── entrypoint.sh           # wait for DB, migrate, collect static, start gunicorn
├── manage.py
├── health_analytic_service/
│   ├── __init__.py
│   ├── settings.py
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
└── README.md

## Detailed File Specifications

### 1. requirements.txt
Django>=4.2,<4.3
gunicorn>=21.2,<23
psycopg2-binary>=2.9,<3

### 2. .env (git-ignored, real values)
DJANGO_SECRET_KEY=change-me-to-a-real-secret-key-in-production
DJANGO_DEBUG=1
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,0.0.0.0
POSTGRES_DB=health_analytic_db
POSTGRES_USER=health_user
POSTGRES_PASSWORD=health_secret_pass
POSTGRES_HOST=db
POSTGRES_PORT=5432

### 3. .env.example
Same keys as .env but with empty or placeholder values and comments.

### 4. Dockerfile
- Base image: python:3.11-slim
- Set PYTHONDONTWRITEBYTECODE=1 and PYTHONUNBUFFERED=1
- Install system deps for psycopg2-binary (libpq-dev gcc) then clean up
- Set workdir to /app
- Copy requirements.txt first and pip install (leverage layer caching)
- Copy the rest of the project
- Copy entrypoint.sh, make it executable
- Expose port 8000
- Set ENTRYPOINT ["./entrypoint.sh"]

### 5. docker-compose.yml
version: "3.9"
services:
  db:
    image: postgres:16
    restart: unless-stopped
    env_file: [.env]
    volumes: [postgres_data:/var/lib/postgresql/data]
    ports: ["5432:5432"]
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U $$POSTGRES_USER -d $$POSTGRES_DB"]
      interval: 5s / timeout: 5s / retries: 5
  backend:
    build: .
    restart: unless-stopped
    env_file: [.env]
    ports: ["8000:8000"]
    depends_on: db (service_healthy)
    volumes: [static_data:/app/staticfiles]
volumes:
  postgres_data:
  static_data:

### 6. entrypoint.sh
1. python manage.py migrate --noinput
2. python manage.py collectstatic --noinput
3. exec gunicorn health_analytic_service.wsgi:application -c gunicorn.conf.py

### 7. gunicorn.conf.py
bind = "0.0.0.0:8000"
workers = 3
threads = 2
timeout = 120

### 8. settings.py
- Read all sensitive values from os.environ with sensible defaults
- DATABASES config using POSTGRES_* env vars
- STATIC_URL / STATIC_ROOT configured
- DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

### 9–14. Standard Django files
urls.py, wsgi.py, asgi.py, manage.py, .gitignore, .dockerignore, README.md

## Acceptance Criteria
1. Build the backend image without errors.
2. Start PostgreSQL 16 with a persistent named volume.
3. Run Django migrations automatically.
4. Serve the app on http://localhost:8000/ via Gunicorn.
5. GET / returns {"status": "ok"}.
6. GET /admin/ shows the Django admin login page.
```

</details>

### What worked well

Now I have an actual plan to send to the agent to start working.

### What I didn't like

I sent this follow-up prompt to change a few details:

> 1. Use a multi-stage build for the Dockerfile, and use `--wheel-dir` option on pip to make the Docker image lighter
> 2. The endpoint `GET /`, change the name to healthcheck and use this endpoint in the docker compose to check the health of the backend service
> 3. At the end in the acceptance criteria create an admin user to log inside the admin page
> 4. Use specific versions of the packages in requirements

### What was not working

Static files were not loaded successfully.

---

## 2. API Endpoints, Models, Auth & Tests

### Prompt

> Now I need to create 1 POST endpoint and 2 GET endpoints:
>
> The POST endpoint will receive this JSON:
> ```json
> {
>   "record_id": "string",
>   "patient_id": "string",
>   "patient_name": "string",
>   "date_of_birth": "YYYY-MM-DD",
>   "ssn_last4": "string",
>   "contact_phone": "string",
>   "facility": "string",
>   "timestamp": "ISO 8601 datetime",
>   "event_type": "REGISTRATION | TRIAGE | BED_ASSIGNMENT | TREATMENT | DISPOSITION | DEPARTURE",
>   "acuity_level": "1-5",
>   "chief_complaint": "string",
>   "disposition": "DISCHARGED | ADMITTED | TRANSFERRED | LEFT_WITHOUT_TREATMENT",
>   "diagnosis_codes": ["string"]
> }
> ```
>
> The 2 GET endpoints will be analytical but we will implement them after, for now just create the endpoint and the function and return a 200 always, with the names `analytical_endpoint_1` and `analytical_endpoint_2`.
>
> Also create the models for the POST endpoint: I need a model for the patients and a model for the records, make the relations between them, and make all the fields nullable.
>
> Also create a CRUD for the patients model, a very simple one to be able to create, modify and get patients. The endpoints will require auth — use and create an API key auth for this. Version the API to be able to make changes without breaking other services. Add a rate limiter for the endpoints. And create the tests for all the endpoints and functions: add unit tests and integration tests.

### Goal

Wanted to give the most basic endpoints and the first structure of the project, and create the most important models, also have all of this with some standards like rate limiter, auth, versioning, and testing.

### AI Response

<details>
<summary>Click to expand — generated plan</summary>

```
Plan: Health Analytic API with Auth, CRUD, Tests & Rate Limiting

Build a versioned REST API (/api/v1/) on top of the existing bare Django 4.2 +
PostgreSQL scaffold. This involves creating a new Django app, adding DRF with
API key authentication, rate limiting, models for patients and records, a patient
CRUD, a record ingest POST endpoint, two stub analytics GET endpoints, and full
test coverage.

Steps:

1. Add dependencies to requirements.txt: djangorestframework, django-filter,
   djangorestframework-api-key (for API key auth), and add pytest, pytest-django,
   factory-boy to requirements-dev.txt.

2. Create a new Django app ed_analytics with the standard files (models.py,
   views.py, serializers.py, urls.py, admin.py, apps.py). Register it plus
   rest_framework and rest_framework_api_key in INSTALLED_APPS. Add DRF settings
   including default throttle rates and set DEFAULT_AUTHENTICATION_CLASSES /
   DEFAULT_PERMISSION_CLASSES to use HasAPIKey.

3. Define models in ed_analytics/models.py:
   - Patient — fields: patient_id (unique), patient_name, date_of_birth,
     ssn_last4, contact_phone — all nullable.
   - Record — fields: record_id (unique), patient (FK → Patient, nullable),
     facility, timestamp, event_type (choices), acuity_level (1–5),
     chief_complaint, disposition (choices), diagnosis_codes (JSONField) —
     all nullable. Generate migrations.

4. Create serializers in ed_analytics/serializers.py:
   - PatientSerializer for CRUD operations on Patient.
   - RecordSerializer for the POST ingest endpoint — accepts the flat JSON,
     resolves/creates the Patient, then creates the Record.

5. Create views & wire URLs:
   - PatientViewSet (full CRUD), RecordCreateView (POST),
     AnalyticalEndpoint1View and AnalyticalEndpoint2View (stubs returning 200).
   - Register routes under DRF router + explicit paths for analytics stubs.
   - urls.py: path("api/v1/", include("ed_analytics.urls")).

6. Write tests in ed_analytics/tests/:
   - test_models.py — unit tests for model creation, nullable fields, FK.
   - test_serializers.py — unit tests for validation, patient resolution logic.
   - test_views.py — integration tests for every endpoint, including auth
     (without API key → 403), rate limiting headers, and correct status codes.
   - Add pytest config in pyproject.toml with DJANGO_SETTINGS_MODULE.

Further Considerations:
- Rate limiter scope: per API key using DRF's UserRateThrottle.
- Patient upsert on record POST: get-or-create using patient_id as lookup key.
- Diagnosis codes: JSONField (PostgreSQL jsonb) for now since analytics are stubs.
```

</details>

### What I didn't like

- I forgot to specify the libraries, so the AI was using basic **DRF** and I wanted to use **django-ninja**.
- The AI wanted to create a single app for everything; my scope was to have the CRUD/POST endpoints in one app (`health_analytic_service`) and the analytical endpoints inside another app (`analytics`).
- It was not specifying what would happen if two identical records arrive, so I explained the upsert behaviour I wanted for those cases.

---

## 3. Examples where the AI output was wrong, incomplete, or misleading.

- The AI created an app where the staticfiles where not being collected, so I had to move the staticfiles to the main project folder and change the settings to make it work.
- The AI was not creating the superuser for the admin page, so I had to create it manually.
- The AI was not following the standards for mypy and flake8, so I had to change the code in some places to make it work with those tools.
- The AI was not creating the tests for the analytical endpoints, so I had to aks specifically for that and then it created the tests for those endpoints.
- The AI was leaving the API key free to read in the admin page.
- The AI was not creating a double stage build for the Dockerfile, so I had to change the Dockerfile to make it work with a multi-stage build and make the image lighter.
- The AI was not adding typings to the code, so I had to ask for the typings explicitly to make it work with mypy.


## 3. What I verified by myself

- I verified that the API key was working correctly and that the endpoints were protected by the API key authentication.
- I verified that the admin panel was working and that I could log in with the superuser credentials.
- I verified that the static files were being collected and served correctly.
- I verified that the tests were running and that they were covering the expected functionality.
- I verified that the Docker Compose setup was working and that I could start the services without errors.
- I verified that the api docs where working properly and that the endpoints were correctly documented.