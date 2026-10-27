import asyncio
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from sqlalchemy import select, func
from sqlalchemy.orm import sessionmaker

from app.db_models import Job, ScrapedPage
from app.persistent_tasks import process_batch, persistent_batch_task

# use approved URLs, even though extraction is mocked
URL_1 = "https://books.toscrape.com/"
URL_2 = "https://books.toscrape.com/catalogue/page-2.html"

@pytest.fixture
def persistent_db(db_session, monkeypatch):
    # our persistence code imports SessionLocal directly
    # replace it with a factory connected to the test
    # transaction instead of the development database
    TestSessionLocal = sessionmaker(
        bind=db_session.connection(),
        join_transaction_mode="create_savepoint"
    )
    
    monkeypatch.setattr(
        "app.persistent_tasks.SessionLocal",
        TestSessionLocal
    )
    
    # the existing db_session fixture will roll back
    # all changes after each test
    return db_session

@patch(
    "app.persistent_tasks.extract_with_retry",
    new_callable=AsyncMock
)
def test_persist_successful_page(mock_extract, persistent_db):
    # set up a parent job in PostgreSQL
    job = Job(total_urls=1)
    persistent_db.add(job)
    persistent_db.flush()
    
    # simulate a successful scraping response
    mock_extract.return_value = {
        "title": "Books to Scrape",
        "extracted": {"heading": "Books"}
    }
    
    # run the real persistence logic
    # only the network extraction is mocked
    asyncio.run(
        process_batch(job.id, [URL_1], {"heading": "h1"})
    )
    
    # retrieve the page written to PostgreSQL
    page = persistent_db.scalar(
        select(ScrapedPage).where(
            ScrapedPage.job_id == job.id
        )
    )
    
    assert page is not None
    assert page.status == "completed"
    assert page.url == URL_1
    assert page.data["title"] == "Books to Scrape"
    
    mock_extract.assert_awaited_once()
    
@patch(
    "app.persistent_tasks.extract_with_retry",
    new_callable=AsyncMock
)
def test_persist_partial_failure(mock_extract, persistent_db):
    # set up a job containing two URLs
    job = Job(total_urls=2)
    persistent_db.add(job)
    persistent_db.flush()
    
    # make one webpage succeed and the other fail
    async def fake_extract(url, selectors):
        if url == URL_2:
            raise httpx.ConnectError("Connection failed")

        return {"title": "Books to Scrape"}
    
    mock_extract.side_effect = fake_extract
    
    asyncio.run(
        process_batch(job.id, [URL_1, URL_2], {})
    )
    
    # query both persisted results
    pages = persistent_db.scalars(
        select(ScrapedPage).where(
            ScrapedPage.job_id == job.id
        )
    ).all()
    
    assert len(pages) == 2
    
    statuses = {page.url: page.status for page in pages}
    
    assert statuses[URL_1] == "completed"
    assert statuses[URL_2] == "failed"
    
    failed_page = next(
        page for page in pages if page.url == URL_2
    )
    
    assert failed_page.error == "ConnectError"
    
@patch(
    "app.persistent_tasks.extract_with_retry",
    new_callable=AsyncMock
)
def test_duplicate_page_is_not_inserted(
    mock_extract,
    persistent_db
):
    # create the parent job
    job = Job(total_urls=1)
    persistent_db.add(job)
    persistent_db.flush()
    
    mock_extract.return_value = {"title": "Example"}
    
    # simulate the same batch being processed twice
    asyncio.run(process_batch(job.id, [URL_1], {}))
    asyncio.run(process_batch(job.id, [URL_1], {}))
    
    # PostgreSQl's unique constraint and ON CONFLICT
    # should keep only one saved record for this URL
    count = persistent_db.scalar(
        select(func.count())
        .select_from(ScrapedPage)
        .where(
            ScrapedPage.job_id == job.id,
            ScrapedPage.url == URL_1
        )
    )
    
    assert count == 1

@patch(
    "app.persistent_tasks.extract_with_retry",
    new_callable=AsyncMock
)
def test_persistent_job_completes(mock_extract, persistent_db):
    # create a new job in the pending state
    job = Job(status="pending", total_urls=1)
    persistent_db.add(job)
    persistent_db.flush()
    
    job_id = job.id
    
    # simulate a successful HTTP extraction
    mock_extract.return_value = {
        "url": URL_1,
        "title": "Books to Scrape",
        "description": None,
        "extracted": {"heading": "Books"}
    }
    
    # execute the task directly without using Redis
    # the real SQLAlchemy persistence code still runs
    result = persistent_batch_task(
        str(job_id),
        [URL_1],
        {"heading": "h1"}
    )
    
    # verify the summary returned by the celery task
    assert result["status"] == "completed"
    assert result["completed"] == 1
    assert result["failed"] == 0
    assert result["remaining"] == 0
    
    # refresh the job because another session updated it
    persistent_db.expire_all()
    saved_job = persistent_db.get(Job, job_id)
    
    # verify PostgreSQL contains the final status
    assert saved_job.status == "completed"
    assert saved_job.heartbeat_at is not None
    
    # verify the worker actually called the extractor
    mock_extract.assert_awaited_once()

@patch(
    "app.persistent_tasks.extract_with_retry",
    new_callable=AsyncMock
)
def test_persistent_job_partial_completion(
    mock_extract,
    persistent_db
):
    # Create a pending job containing two URLs.
    job = Job(status="pending", total_urls=2)
    persistent_db.add(job)
    persistent_db.flush()

    job_id = job.id

    # Simulate different results for each URL.
    async def fake_extract(url, selectors):
        # The second webpage experiences a network failure.
        if url == URL_2:
            raise httpx.ConnectError("Connection failed")

        # The first webpage is successfully extracted.
        return {
            "url": url,
            "title": "Books to Scrape",
            "description": None,
            "extracted": {"heading": "Books"}
        }

    mock_extract.side_effect = fake_extract

    # Execute the real Celery task locally.
    # Redis is not required for this test.
    result = persistent_batch_task(
        str(job_id),
        [URL_1, URL_2],
        {"heading": "h1"}
    )

    # Verify the task correctly summarizes both results.
    assert result["status"] == "partial"
    assert result["completed"] == 1
    assert result["failed"] == 1
    assert result["remaining"] == 0

    # Clear any cached ORM attributes before checking
    # changes made by the task's database sessions.
    persistent_db.expire_all()

    saved_job = persistent_db.get(Job, job_id)

    # Verify the final status was stored in PostgreSQL.
    assert saved_job.status == "partial"
    assert saved_job.heartbeat_at is not None

    # Verify both URLs were attempted.
    assert mock_extract.await_count == 2

    # Confirm both page records were persisted.
    pages = persistent_db.scalars(
        select(ScrapedPage).where(
            ScrapedPage.job_id == job_id
        )
    ).all()

    assert len(pages) == 2
    assert {page.status for page in pages} == {
        "completed",
        "failed"
    }

@patch(
    "app.persistent_tasks.extract_with_retry",
    new_callable=AsyncMock
)
def test_completed_job_is_not_reprocessed(
    mock_extract,
    persistent_db
):
    # simulate a job that has already finished
    job = Job(status="completed", total_urls=1)
    persistent_db.add(job)
    persistent_db.flush()
    
    # attempt to execute the same job again
    result = persistent_batch_task(
        str(job.id),
        [URL_1],
        {}
    )
    
    # the task should return without processing the URL
    assert result["status"] == "completed"
    assert result["message"] == "Job already processed"
    
    # no scraping should have occurred
    mock_extract.assert_not_awaited()
    
    # verify the job's original status remains unchanged
    persistent_db.expire_all()
    saved_job = persistent_db.get(Job, job.id)
    assert saved_job.status == "completed"

@patch(
    "app.persistent_tasks.extract_with_retry",
    new_callable=AsyncMock
)
def test_running_job_is_not_reprocessed(
    mock_extract,
    persistent_db
):
    # simulate a job currently claimed by a worker
    job = Job(status="running", total_urls=1)
    persistent_db.add(job)
    persistent_db.flush()
    
    # attempt to execute the job from another worker
    result = persistent_batch_task(
        str(job.id),
        [URL_1],
        {}
    )
    
    # the task must refuse to process it again
    assert result["status"] == "running"
    assert result["message"] == (
        "Job is already being processed"
    )
    
    # no duplicate scraping should take place
    mock_extract.assert_not_awaited()
    
    # confirm the database status is unchanged
    persistent_db.expire_all()
    saved_job = persistent_db.get(Job, job.id)
    assert saved_job.status == "running"

@patch("app.persistent_tasks.process_batch")
def test_persistent_job_unexpected_failure(
    mock_process_batch,
    persistent_db
):
    # create a new pending job in our test database
    job = Job(
        status="pending",
        total_urls=1
    )
    
    persistent_db.add(job)
    persistent_db.flush()
    
    job_id = job.id
    
    # simulate an unexpected failure during batch processing
    # process_batch() is normally asynchronous
    # here, we replace it with a mock coroutine that raises
    # an exception when asyncio.run() execute it
    async def failing_batch(*args, **kwargs):
        raise RuntimeError("Unexpected processing failure")
    
    mock_process_batch.side_effect = failing_batch
    
    # the original exception should propagate to Celery
    with pytest.raises(
        RuntimeError,
        match="Unexpected processing failure"
    ):
        persistent_batch_task(
            str(job_id),
            [URL_1],
            {}
        )
    
    # reload database values changed by another session
    persistent_db.expire_all()
    
    saved_job = persistent_db.get(Job, job_id)
    
    # verify the exception handler marked the job as failed
    assert saved_job.status == "failed"
    
    # verify the worker updated its heartbeat timestamp
    assert saved_job.heartbeat_at is not None
    
    # verify batch processing was attempted once
    mock_process_batch.assert_called_once()
    