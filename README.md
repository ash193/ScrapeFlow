# ScrapeFlow (In Progress)

**Asynchronous Web Data Extraction & Background Job Processing Platform**

ScrapeFlow is a Python-based backend application designed to automate web data extraction through concurrent HTTP requests and distributed background task processing. Built with FastAPI, Celery, Redis, and PostgreSQL, it supports configurable extraction rules, persistent job tracking, and fault-tolerant processing of webpage batches.

The project explores practical backend engineering concepts including asynchronous I/O, task queues, database persistence, retry strategies, and job lifecycle management.

> **Project Status:** Active development. Core API functionality, background processing, and PostgreSQL persistence are implemented. Containerization, expanded automated testing, and deployment are planned.

## Tech Stack

| Category | Technologies |
|---|---|
| Language | Python |
| API Framework | FastAPI, Pydantic |
| Web Extraction | HTTPX, Beautiful Soup |
| Asynchronous Processing | asyncio |
| Task Queue | Celery, Redis |
| Database | PostgreSQL, SQLAlchemy, Psycopg |
| Testing | Pytest |
| Planned Infrastructure | Docker, Docker Compose, GitHub Actions |

## Architecture

ScrapeFlow separates API request handling from background processing so that clients can submit extraction jobs without waiting for the entire batch to complete.

```text
                     CLIENT
                        |
                        v
                   FASTAPI API
                        |
                 Creates Job Record
                        |
                        v
                    POSTGRESQL
                        ^
                        |
                        | Stores results
                        |
                  CELERY WORKER
                        ^
                        |
                    REDIS QUEUE
                        ^
                        |
                     FASTAPI
```

**Processing workflow:**

1. A client submits a batch of URLs and optional CSS selectors through the REST API.
2. FastAPI validates the request, creates a PostgreSQL job record, and queues the task through Redis.
3. A Celery worker retrieves the task and processes URLs concurrently using `asyncio` and HTTPX.
4. Beautiful Soup extracts page metadata and user-specified HTML elements.
5. Extraction results and job statuses are persisted in PostgreSQL.
6. The client retrieves job progress and saved results through the API.

## Features

### Configurable Data Extraction

- Extracts webpage titles, metadata, and content using user-defined CSS selectors.
- Supports multiple URLs per batch.
- Uses asynchronous HTTP requests to improve I/O-bound processing efficiency.
- Currently restricts extraction to an approved practice website while URL security protections are developed.

### Background Job Processing

- Uses Celery and Redis to process jobs outside the API request lifecycle.
- Returns unique job identifiers for asynchronous submissions.
- Tracks job states including `pending`, `running`, `completed`, `partial`, and `failed`.
- Supports concurrent URL processing within individual background tasks.

### Reliability and Error Handling

- Retries recoverable network failures using exponential backoff.
- Handles individual URL failures without necessarily failing the entire batch.
- Applies concurrency limits to control simultaneous requests.
- Uses PostgreSQL uniqueness constraints and conflict-aware inserts to prevent duplicate job/URL records.
- Includes basic detection of potentially stalled jobs.

### Persistent Storage and Progress Tracking

- Stores job metadata and extracted results in PostgreSQL.
- Uses SQLAlchemy for database interactions.
- Stores flexible extraction results using PostgreSQL `JSONB`.
- Tracks processed URLs, completion percentage, and worker activity timestamps.
- Supports retrieving completed results independently of Celery's temporary Redis result retention.

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | Check API availability |
| POST | `/extract` | Extract information from one webpage |
| POST | `/extract/batch` | Concurrently extract multiple webpages |
| POST | `/jobs` | Submit a single background extraction job |
| POST | `/jobs/batch` | Submit a background batch job |
| GET | `/jobs/{job_id}` | Retrieve temporary Celery task status |
| POST | `/jobs/persisted/batch` | Submit a PostgreSQL-backed extraction job |
| GET | `/jobs/persisted/{job_id}` | Retrieve persistent job progress and results |

The persistent job endpoints are the primary workflow. Earlier endpoints are retained for development and comparison.

Interactive API documentation is available through FastAPI at `/docs`.

## Example Usage

### Submit a Persistent Batch Job

**POST** `/jobs/persisted/batch`

```json
{
  "urls": [
    "https://books.toscrape.com/catalogue/page-1.html",
    "https://books.toscrape.com/catalogue/page-2.html",
    "https://books.toscrape.com/catalogue/page-3.html"
  ],
  "selectors": {
    "first_book_title": "article.product_pod h3 a",
    "first_book_price": "article.product_pod .price_color",
    "availability": "article.product_pod .availability"
  }
}
```

**Example response:**

```json
{
  "job_id": "generated-uuid",
  "status": "pending",
  "total_urls": 3
}
```

The API responds with HTTP `202 Accepted` without waiting for extraction to finish.

### Retrieve Job Results

**GET** `/jobs/persisted/{job_id}`

An example of a completed job response:

```json
{
  "job_id": "generated-uuid",
  "status": "completed",
  "total_urls": 3,
  "processed_urls": 3,
  "completed": 3,
  "failed": 0,
  "remaining": 0,
  "progress_percent": 100,
  "heartbeat_at": "2026-10-19T23:39:53-04:00",
  "results": [
    {
      "url": "https://books.toscrape.com/catalogue/page-1.html",
      "status": "completed",
      "data": {
        "title": "All products | Books to Scrape - Sandbox",
        "description": null,
        "extracted": {
          "first_book_title": "A Light in the Attic",
          "first_book_price": "£51.77"
        }
      },
      "error": null
    }
  ]
}
```

The results array is abbreviated for readability. Actual responses contain one record per processed URL.

## Local Development

### Prerequisites

- Python 3.13
- PostgreSQL 17
- Redis
- Git

The application has been developed locally on macOS. Containerized setup is planned.

### 1. Clone the Repository

```bash
git clone https://github.com/YOUR_USERNAME/ScrapeFlow.git
cd ScrapeFlow
```

Replace `YOUR_USERNAME` with your GitHub username.

### 2. Create a Virtual Environment

```bash
python3.13 -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies

```bash
python -m pip install -r requirements.txt
```

### 4. Configure Environment Variables

Create a `.env` file in the project root:

```dotenv
DATABASE_URL=postgresql+psycopg:///scraperflow
```

This example uses a local PostgreSQL connection through a Unix socket. Database configuration may vary by operating system.

Ensure PostgreSQL is running and create the database:

```bash
createdb scraperflow
```

Then initialize the tables:

```bash
python create_tables.py
```

The project currently uses SQLAlchemy for schema creation. Versioned database migrations are planned.

### 5. Start Redis

Make sure Redis is running locally.

On macOS with Homebrew:

```bash
brew services start redis
redis-cli ping
```

A successful connection returns `PONG`.

### 6. Start the Celery Worker

In a terminal with the virtual environment activated:

```bash
python -m celery -A app.celery_app:celery_app worker --loglevel=INFO --pool=solo
```

The `solo` pool is used for the current macOS development setup. Standard multiprocessing workers will be tested during containerization.

### 7. Start FastAPI

In a separate terminal:

```bash
python -m uvicorn app.main:app --reload
```

The API is available at:

- `http://127.0.0.1:8000`
- Interactive documentation: `http://127.0.0.1:8000/docs`

**Configuration note:** Redis broker and result-backend addresses are currently configured for local development in `app/celery_app.py`. They will become environment-driven as part of containerization.

## Testing

ScrapeFlow uses Pytest to verify selected backend functionality, including retry behavior under simulated network failures.

Run the available tests with:

```bash
python -m pytest -v
```

The project also includes a sequential-versus-asynchronous scraping benchmark:

```bash
python benchmark.py
```

Benchmark results depend on network conditions and the availability of the target website. More controlled performance and integration tests are planned.

## Project Structure

```text
scraperflow/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── models.py
│   ├── extractor.py
│   ├── celery_app.py
│   ├── tasks.py
│   ├── persistent_tasks.py
│   ├── retry.py
│   ├── database.py
│   └── db_models.py
├── tests/
│   └── test_retry.py
├── scraper.py
├── async_scraper.py
├── benchmark.py
├── create_tables.py
├── check_stalled_jobs.py
├── requirements.txt
├── .gitignore
└── README.md
```

## Roadmap

- [x] Configurable HTML extraction
- [x] Concurrent batch scraping
- [x] FastAPI REST endpoints
- [x] Celery and Redis background processing
- [x] PostgreSQL and SQLAlchemy persistence
- [x] Retry handling with exponential backoff
- [x] Duplicate-result prevention
- [x] Progress tracking and worker activity timestamps
- [x] Basic stalled-job detection
- [ ] Docker and Docker Compose
- [ ] Environment-driven service configuration
- [ ] Alembic database migrations
- [ ] Expanded unit and integration test coverage
- [ ] GitHub Actions CI/CD
- [ ] Production-oriented URL validation and SSRF protection
- [ ] Automated worker recovery and safer task redelivery
- [ ] Expanded performance benchmarking
- [ ] Deployment

## Engineering Considerations

**Concurrency vs. background processing:** `asyncio` allows network requests within a job to overlap, while Celery processes jobs separately from the FastAPI request lifecycle.

**Idempotency:** Database uniqueness constraints and conflict-aware inserts reduce the risk of duplicate results when tasks are executed repeatedly.

**Fault tolerance:** Recoverable network failures use bounded retries. Individual URL failures are recorded rather than automatically discarding successful results.

**Persistence:** PostgreSQL stores durable job history while Redis transports queued tasks and temporarily retains Celery results.

**Current limitations:** The project does not yet provide automatic recovery from worker crashes, full arbitrary-URL security, or a production deployment. These are intentionally tracked as future improvements.

## Purpose

ScrapeFlow was developed to explore backend engineering concepts through a practical data-processing system, with an emphasis on asynchronous Python programming, API development, distributed task execution, persistence, reliability, and testability.
