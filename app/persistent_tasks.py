import asyncio
import uuid

import httpx
from soupsieve.util import SelectorSyntaxError
from sqlalchemy import select, func

from app.celery_app import celery_app
from app.database import SessionLocal
from app.db_models import Job, ScrapedPage
from app.extractor import extract_page

from app.retry import extract_with_retry
from sqlalchemy.dialects.postgresql import insert

ALLOWED_HOSTS = {"books.toscrape.com"}

async def process_batch(
    job_id: uuid.UUID,
    urls: list[str],
    selectors: dict[str, str]
):
    # limit concurrent network operations to 5
    semaphore = asyncio.Semaphore(5)
    
    async def process_url(url: str):
        from urllib.parse import urlsplit
        
        # recheck the dest inside the worker
        parsed = urlsplit(url)
        
        if (
            parsed.scheme != "https"
            or parsed.hostname not in ALLOWED_HOSTS
        ): 
            return {
                "url": url,
                "status": "failed",
                "data": None,
                "error": "Unapproved URL"
            }
        
        async with semaphore:
            try:
                # attempt extraction up to 3 times for
                # recoverable network failures
                data = await extract_with_retry(url, selectors)
                
                return {
                    "url": url,
                    "status": "completed",
                    "data": data,
                    "error": None
                }
            
            except (
                httpx.RequestError,
                httpx.HTTPStatusError,
                SelectorSyntaxError
            ) as error:
                return {
                    "url": url,
                    "status": "failed",
                    "data": None,
                    "error": type(error).__name__
                }
    
    # creates one coroutine for each url
    tasks = [process_url(url) for url in urls]
    
    # handle results as soon as each request finishes
    # unlike asyncio.gather(), we don't wait for
    # the entire batch before saving anything
    for completed_task in asyncio.as_completed(tasks):
        # retrieve the next completed scraping result
        result = await completed_task
        
        # open a short database transaction
        with SessionLocal.begin() as session:
            # insert the extracted webpage result
            stmt = insert(ScrapedPage).values(
                id=uuid.uuid4(),
                job_id=job_id,
                url=result["url"],
                status=result["status"],
                data=result["data"],
                error=result["error"]
            )
            
            # prevent duplicate records for the same job and URL
            stmt = stmt.on_conflict_do_nothing(
                constraint="uq_scraped_pages_job_url"
            )
            
            session.execute(stmt)
            
            # find the parent job in PostgreSQL
            job = session.get(Job, job_id)
            
            if job is not None:
                # record the time of the latest completed URl
                job.heartbeat_at = func.now()
    

@celery_app.task(name="scraperflow.persistent_batch")
def persistent_batch_task(
    job_id: str,
    urls: list[str],
    selectors: dict[str, str]
):
    # convert the string job id into a UUID obj
    # our SQLAlchemy model uses PostgreSQL's UUID type
    job_uuid = uuid.UUID(job_id)
    
    # each worker creates its own database session
    # do not share an active session between processes
    with SessionLocal.begin() as session:
        # lock the job row while checking its current status
        # this prevents 2 workers from claiming it simultaneously
        # during this transaction
        job = session.get(Job, job_uuid, with_for_update=True)
        
        if job is None:
            raise ValueError("Job does not exist")
        
        # do not repeat a job that has already finished
        if job.status in ("completed", "partial", "failed"):
            return {
                "job_id": str(job_uuid),
                "status": job.status,
                "message": "Job already processed"
            }
        
        # don't start the same job twice concurrently
        if job.status == "running":
            return {
                "job_id": str(job_uuid),
                "status": "running",
                "message": "Job is already being processed"
            }
        
        # claim the job for processing
        job.status = "running"
        
        # record the current PostgreSQL timestamp
        job.heartbeat_at = func.now()
        
        
    try:
        # process the batch and persis results incrementally
        asyncio.run(
            process_batch(job_uuid, urls, selectors)
        )
        
        # save the results in a single database transaction
        with SessionLocal.begin() as session:
            job = session.get(Job, job_uuid)
            
            if job is None:
                raise ValueError("Job does not exist")

            # count successful webpages stored in PostgreSQL
            completed = session.scalar(
                select(func.count())
                .select_from(ScrapedPage)
                .where(
                    ScrapedPage.job_id == job_uuid,
                    ScrapedPage.status == "completed"
                )
            )
            
            # count all saved webpage results
            processed = session.scalar(
                select(func.count())
                .select_from(ScrapedPage)
                .where(ScrapedPage.job_id == job_uuid)
            )
            
            failed = processed - completed
            remaining = job.total_urls - processed
            
            # determine the overall status from persisted records
            if remaining > 0:
                job.status = "failed"
            elif failed == 0:
                job.status = "completed"
            elif completed == 0:
                job.status = "failed"
            else:
                job.status = "partial"
            
            # record the final worker activity timestamp
            job.heartbeat_at = func.now()
            final_status = job.status
            
        # celery also receives a small result summary
        # postgresql holds the full extracted records
        return {
            "job_id": job_id,
            "status": final_status,
            "completed": completed,
            "failed": failed,
            "remaining": remaining
        }
    
    except Exception:
        # if an unexpected error occurs, try to mark the
        # job as failed before allowing Celery to report it
        with SessionLocal.begin() as session:
            job = session.get(Job, job_uuid)
            
            if job is not None:
                job.status = "failed"
                job.heartbeat_at = func.now()
        
        # preserve the original exception for debugging
        raise
