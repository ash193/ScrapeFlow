# ScrapeFlow

**Asynchronous Web Data Extraction & Background Job Processing Platform**

ScrapeFlow is a Python-based backend application for extracting structured information from webpages through asynchronous HTTP requests and distributed background job processing.

Built with FastAPI, Celery, Redis, and PostgreSQL, it supports configurable CSS selectors, concurrent scraping, persistent job tracking, retry handling, and fault-tolerant processing of webpage batches.

The application also incorporates configurable scraping destinations, URL and DNS validation, a restricted HTTP transport, database migrations, health checks, and automated testing.

> **Project Status:** Functional, self-hosted backend application. Successfully verified through automated tests and a fresh Docker Compose installation. Not currently deployed as a public hosted service.

---

## Tech Stack

| Category | Technologies |
|---|---|
| Language | Python 3.13 |
| API Framework | FastAPI, Pydantic |
| Web Extraction | HTTPX, HTTP Core, Beautiful Soup |
| Asynchronous Processing | asyncio |
| Background Processing | Celery, Redis |
| Database | PostgreSQL 17, SQLAlchemy, Psycopg |
| Database Migrations | Alembic |
| Infrastructure | Docker, Docker Compose |
| Testing | pytest, pytest-asyncio, respx |
| CI/CD | GitHub Actions |

## Architecture

ScrapeFlow separates API request handling from background processing so clients can submit scraping jobs without waiting for the entire batch to finish.

```text
                   CLIENT / SWAGGER UI
                           |
                           v
                       FASTAPI
                           |
                  Validates requests
                           |
                 Creates Job Record
                           |
              +------------+------------+
              |                         |
              v                         v
          POSTGRESQL                 REDIS BROKER
              ^                         |
              |                         v
              |                    CELERY WORKER
              |                         |
              |                 Concurrent Processing
              |                         |
              |                 URL/DNS Validation
              |                         |
              |                 Secure HTTP Transport
              |                         |
              |                   HTTPX Requests
              |                         |
              |                  BEAUTIFUL SOUP
              |                         |
              +------ Stores Results ---+
```

### Processing Workflow

1. A client submits a batch of approved URLs and CSS selectors through the REST API.
2. FastAPI validates the URLs, creates a PostgreSQL job record, and submits a task through Redis.
3. A Celery worker retrieves the task and processes URLs concurrently using `asyncio` and HTTPX.
4. URL and DNS validation restrict scraping destinations, while the custom HTTP transport connects to validated IP addresses.
5. Beautiful Soup extracts webpage metadata and user-specified HTML elements.
6. Extraction results, progress, and job statuses are stored in PostgreSQL.
7. Clients retrieve job progress and saved results through the API.

The persistent job workflow is the primary implementation. Direct extraction and nonpersistent Celery endpoints are retained for comparison and testing.

---

## Features

### Configurable Data Extraction

- Extracts webpage titles, meta descriptions, and content using user-defined CSS selectors.
- Supports single-page and multi-URL batch extraction.
- Uses asynchronous HTTP requests to improve performance for I/O-bound workloads.
- Allows deployment operators to configure approved scraping websites through environment variables.
- Extracts the first matching element for each specified CSS selector.

### Background Job Processing

- Uses Celery and Redis to process jobs independently of the FastAPI request lifecycle.
- Returns unique job identifiers for asynchronous submissions.
- Tracks job states including `pending`, `running`, `completed`, `partial`, and `failed`.
- Supports concurrent URL processing within background tasks.
- Limits simultaneous scraping operations to five per batch.

### Reliability and Error Handling

- Retries supported recoverable network failures.
- Handles individual URL failures without discarding successful results.
- Uses bounded concurrency to limit simultaneous HTTP requests.
- Prevents duplicate job/URL records using PostgreSQL uniqueness constraints and conflict-aware inserts.
- Includes detection of potentially stalled jobs using worker heartbeat timestamps.
- Records job lifecycle events and unexpected failures through application logging.

### Persistent Storage and Progress Tracking

- Stores job metadata and extracted results in PostgreSQL.
- Uses SQLAlchemy for database interactions.
- Stores flexible extraction results using PostgreSQL `JSONB`.
- Tracks completed URLs, failed URLs, remaining work, and completion percentage.
- Records worker activity timestamps.
- Supports retrieving completed results independently of Celery's temporary Redis result storage.

### Security Safeguards

- Configurable hostname allowlist.
- HTTPS-only scraping.
- Rejection of embedded URL credentials, IP-address literals, and nonstandard ports.
- DNS validation that rejects destinations resolving to non-global IP addresses.
- Custom HTTPX/HTTP Core network transport that connects to validated IP addresses.
- Disabled automatic HTTP redirects.
- Disabled inherited proxy environment settings.
- URL revalidation inside Celery workers.

These safeguards reduce exposure to server-side request forgery (SSRF), but additional infrastructure protections are required before operating an unrestricted public service.

---

## Getting Started

The recommended way to run ScrapeFlow is through Docker Compose.

### Prerequisites

- Git
- Docker Desktop or Docker Engine with Docker Compose

Python, PostgreSQL, and Redis do not need to be installed separately when using Docker.

### 1. Clone the Repository

```bash
git clone https://github.com/ash193/ScrapeFlow.git
cd ScrapeFlow
```

### 2. Configure Environment Variables

Create your local Docker environment file from the provided template:

```bash
cp .env.example .env.docker
```

Open `.env.docker` and configure the required PostgreSQL variables:

```dotenv
POSTGRES_USER=scrapeflow
POSTGRES_PASSWORD=replace_with_your_password
POSTGRES_DB=scrapeflow

ALLOWED_HOSTS=books.toscrape.com,quotes.toscrape.com
```

Replace `replace_with_your_password` with your own password.

The `ALLOWED_HOSTS` variable accepts a comma-separated list of approved hostnames. Do not include `https://` or URL paths.

For example:

```dotenv
ALLOWED_HOSTS=books.toscrape.com,quotes.toscrape.com,example.org
```

Only configure websites that you are authorized to access.

**Important:** The `.env.docker` file is excluded from Git through `.gitignore`. Do not commit actual database credentials.

Docker Compose constructs the internal database connection and Redis URLs from its service configuration.

### 3. Build and Start the Application

Validate the configuration:

```bash
docker compose --env-file .env.docker config --quiet
```

Build and start the services:

```bash
docker compose --env-file .env.docker up --build -d
```

Docker Compose starts the following services:

| Service | Purpose |
|---|---|
| `api` | FastAPI REST application |
| `worker` | Celery background task processor |
| `redis` | Message broker and temporary result backend |
| `db` | PostgreSQL database |
| `migrate` | Runs Alembic database migrations |

The migration service initializes or upgrades the database schema before FastAPI and Celery begin processing work.

### 4. Verify the Containers

```bash
docker compose --env-file .env.docker ps -a
```

Expected states:

| Service | Status |
|---|---|
| `api` | Healthy |
| `worker` | Healthy |
| `redis` | Healthy |
| `db` | Healthy |
| `migrate` | Exited (0) |

The migration container exiting successfully is expected because Alembic runs as a one-time initialization process.

### 5. Access the Application

Once the services are running:

- **Swagger UI:** http://localhost:8000/docs
- **Health endpoint:** http://localhost:8000/health

Swagger UI provides interactive documentation for all available API endpoints.

### 6. Stop the Application

```bash
docker compose --env-file .env.docker down
```

This stops and removes the containers without deleting the persistent PostgreSQL volume.

Avoid using `down --volumes` unless you intentionally want to delete stored database data.

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | Check API availability |
| POST | `/extract` | Extract information from one webpage |
| POST | `/extract/batch` | Concurrently extract multiple webpages |
| POST | `/jobs` | Submit a single background extraction job |
| GET | `/jobs/{job_id}` | Retrieve Celery task status and results |
| POST | `/jobs/batch` | Submit a background batch job |
| POST | `/jobs/persisted/batch` | Submit a PostgreSQL-backed extraction job |
| GET | `/jobs/persisted/{job_id}` | Retrieve persistent job progress and results |

The persistent job endpoints are recommended for workloads that require stored results and progress monitoring.

## Example Usage

### Submit a Persistent Batch Job

**POST `/jobs/persisted/batch`**

```json
{
  "urls": [
    "https://books.toscrape.com/",
    "https://quotes.toscrape.com/"
  ],
  "selectors": {
    "heading": "h1",
    "page_title": "title"
  }
}
```

Both websites must be included in `ALLOWED_HOSTS`.

The API responds with HTTP `202 Accepted` and a generated job identifier:

```json
{
  "job_id": "generated-uuid",
  "status": "pending",
  "total_urls": 2
}
```

The job is processed asynchronously by Celery.

### Retrieve Job Results

**GET `/jobs/persisted/{job_id}`**

After the job finishes, the response contains its status, progress, and extracted information.

Example abbreviated response:

```json
{
  "job_id": "generated-uuid",
  "status": "completed",
  "total_urls": 2,
  "processed_urls": 2,
  "completed": 2,
  "failed": 0,
  "remaining": 0,
  "progress_percent": 100.0,
  "results": [
    {
      "url": "https://books.toscrape.com/",
      "status": "completed",
      "data": {
        "url": "https://books.toscrape.com/",
        "title": "All products | Books to Scrape - Sandbox",
        "description": null,
        "extracted": {
          "heading": "All products"
        }
      },
      "error": null
    }
  ]
}
```

The example is shortened for readability. Actual responses also include timestamps and individual records for each processed URL.

---

## Database and Migrations

ScrapeFlow uses PostgreSQL for durable storage.

The database contains two primary tables:

**Jobs**

Stores information about submitted scraping jobs, including status, total URLs, timestamps, and worker heartbeat activity.

**Scraped Pages**

Stores individual extracted webpage results, associated job IDs, processing status, extracted JSON data, and error information.

PostgreSQL uniqueness constraints prevent duplicate page records for the same job and URL.

### Alembic Migrations

Alembic manages versioned database schema changes.

Docker Compose automatically executes:

```bash
python -m alembic upgrade head
```

through its dedicated migration service.

To inspect the current migration revision:

```bash
docker compose --env-file .env.docker run --rm api \
  python -m alembic current
```

To apply outstanding migrations manually:

```bash
docker compose --env-file .env.docker run --rm api \
  python -m alembic upgrade head
```

This provides repeatable database initialization without manually creating application tables.

---

## Testing

ScrapeFlow includes automated tests covering:

- FastAPI endpoint behavior
- HTTP extraction and CSS selectors
- Asynchronous Celery tasks
- Network retries and error handling
- PostgreSQL persistence
- Duplicate prevention
- Job lifecycle transitions
- Configurable hostname validation
- DNS validation
- Restricted network connections
- Secure HTTP transport behavior
- Partial batch failures
- Stalled-job detection

### Running the Tests

Install the Python dependencies in a Python 3.13 environment:

```bash
python -m pip install -r requirements.txt
```

Run the complete test suite:

```bash
python -m pytest -v
```

### Database Tests

Database integration tests require a separate PostgreSQL database named `scrapeflow_test`.

With the Docker database running, create the test database if it doesn't already exist:

```bash
docker compose --env-file .env.docker exec db \
  psql -U scrapeflow -d postgres \
  -c "CREATE DATABASE scrapeflow_test;"
```

If you changed `POSTGRES_USER`, substitute the configured username.

Configure the test database URL in your local `.env.docker`:

```dotenv
TEST_DATABASE_URL=postgresql+psycopg://scrapeflow:your_password@127.0.0.1:5433/scrapeflow_test
```

Replace `your_password` with the PostgreSQL password you configured.

The test fixtures verify that database integration tests connect only to `scrapeflow_test` and roll back test database changes.

### Continuous Integration

GitHub Actions provides automated continuous integration.

The workflow includes:

- **Python test job:** Installs dependencies, initializes a PostgreSQL service, and executes pytest.
- **Docker build job:** Builds the application image to verify that the Docker configuration remains buildable.

A successful workflow confirms that tests and the Docker build pass. The workflow does not automatically deploy the application.

---

## Monitoring and Logging

ScrapeFlow includes basic operational monitoring.

### Container Health Checks

Docker Compose checks the health of:

- FastAPI
- Celery
- Redis
- PostgreSQL

### Application Logging

Python logging records important application events, including:

- FastAPI initialization
- Celery worker initialization
- Persistent scraping job starts
- Job completion summaries
- Unexpected processing failures

Inspect FastAPI logs:

```bash
docker compose --env-file .env.docker logs --tail=100 api
```

Inspect Celery worker logs:

```bash
docker compose --env-file .env.docker logs --tail=100 worker
```

### Stalled Job Detection

Persistent jobs record worker heartbeat timestamps.

The project includes `check_stalled_jobs.py`, which can identify jobs that may have stopped making progress.

This provides detection and visibility, but not automatic worker recovery.

---

## Project Structure

```text
scraperflow/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── models.py
│   ├── extractor.py
│   ├── config.py
│   ├── url_validator.py
│   ├── dns_validator.py
│   ├── secure_network.py
│   ├── secure_transport.py
│   ├── celery_app.py
│   ├── tasks.py
│   ├── persistent_tasks.py
│   ├── retry.py
│   ├── database.py
│   ├── db_models.py
│   └── logging_config.py
├── alembic/
├── tests/
├── .github/
│   └── workflows/
│       └── ci.yml
├── alembic.ini
├── compose.yaml
├── Dockerfile
├── requirements.txt
├── .env.example
├── .gitignore
├── check_stalled_jobs.py
└── README.md
```

Additional development scripts are included for benchmarking and standalone scraping experiments.

---

## Security and Limitations

ScrapeFlow is designed as a self-hosted backend application with security safeguards for configurable scraping destinations.

### Implemented Safeguards

- Approved-hostname configuration through environment variables.
- HTTPS-only destination validation.
- Restrictions on URL credentials, nonstandard ports, and IP-address literals.
- DNS checks that reject destinations resolving to non-global addresses.
- Restricted HTTP transport that connects to previously validated IP addresses.
- Disabled automatic redirect following.
- Disabled inherited HTTP proxy configuration.
- Worker-side URL revalidation.
- TLS certificate verification.

### Current Limitations

ScrapeFlow is not intended to operate as an unrestricted public scraping proxy without additional hardening.

A public deployment would require further protections, including:

- Authentication and authorization.
- Rate limits and resource quotas.
- Network-level outbound traffic restrictions.
- Explicit DNS resolution timeouts.
- Response-size and download limits.
- Monitoring and operational controls.
- Additional security testing of the custom HTTP transport.
- A strategy for automatic recovery of interrupted jobs.

The custom HTTP transport also relies on internal HTTPX implementation details, so dependency upgrades require compatibility testing.

ScrapeFlow currently focuses on publicly accessible HTML pages. It does not automatically support JavaScript-rendered content, authenticated sessions, CAPTCHAs, or extracting every matching element for a selector.

Users are responsible for respecting website access policies and applicable laws.

---

## Engineering Considerations

**Concurrency vs. Background Processing**

`asyncio` allows multiple network requests within a job to overlap. Celery processes entire jobs independently of the FastAPI request lifecycle.

**Persistence vs. Task Queueing**

PostgreSQL stores durable job history and extraction results. Redis transports queued tasks and temporarily retains Celery results.

**Idempotency**

PostgreSQL uniqueness constraints and conflict-aware inserts reduce duplicate records when scraping tasks execute repeatedly.

**Fault Tolerance**

Recoverable network failures use bounded retries. Individual URL failures are recorded without automatically discarding successful results from the batch.

**Database Schema Management**

Alembic provides repeatable schema migrations and supports database evolution without relying on manual table creation.

**Security**

URL allowlisting, DNS validation, and a restricted HTTP transport provide multiple layers of destination validation. These measures reduce risks but are not a substitute for network-level protections in public deployments.

---

## Project Purpose

ScrapeFlow was developed to explore practical backend engineering through a distributed data-processing application.

The project emphasizes asynchronous Python programming, REST API development, task queues, database persistence, concurrency, reliability, security considerations, Docker infrastructure, automated testing, and maintainable backend architecture.
