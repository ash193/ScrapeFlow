import asyncio
from app.models import BatchExtractionRequest
from app.tasks import extract_batch_task

import httpx
from fastapi import FastAPI, HTTPException
from soupsieve.util import SelectorSyntaxError
from app.models import ExtractionRequest, ExtractionResponse
from app.extractor import extract_page

from celery.result import AsyncResult
from fastapi import status
from app.celery_app import celery_app
from app.tasks import extract_task

import uuid
from sqlalchemy import select
from kombu.exceptions import OperationalError

from app.database import SessionLocal
from app.db_models import Job, ScrapedPage
from app.persistent_tasks import persistent_batch_task


# create the fastapi app
# similar to const app = express() in node.js
app = FastAPI(
    title="ScrapeFlow API",
    version="0.1.0"
)

ALLOWED_HOSTS = {"books.toscrape.com"}

@app.get("/health")
async def health_check():
    # returns JSON indicating that the API is running
    return {"status": "healthy"}

@app.post("/extract", response_model=ExtractionResponse)
async def extract(request: ExtractionRequest):
    # httpURL provides a parsed, validated URL object
    # restrict requests to our practice website for now
    if request.url.host not in ALLOWED_HOSTS:
        raise HTTPException(
            status_code=400,
            detail="This URL is not an approved scraping target"
        )
    
    try:
        # pass the validated url and selectors to our service
        # similar to calling a service function from an express route
        result = await extract_page(
            url=str(request.url),
            selectors=request.selectors
        )
        
        return result
    
    except SelectorSyntaxError:
        # a user submitted an invalid CSS selector
        raise HTTPException(
            status_code=422,
            detail="One or more CSS selects are invalid"
        )
    
    except httpx.HTTPStatusError as error:
        # the website returned an error or redirect status
        raise HTTPException(
            status_code=502,
            detail=f"Upstream HTTP status: {error.response.status_code}"
        )
    
    except httpx.RequestError:
        # the network request failed or timed out
        raise HTTPException(
            status_code=502,
            detail="Unable to retrieve the requested webpage"
        )

@app.post("/extract/batch")
async def extract_batch(request: BatchExtractionRequest):
    # verify that every submitted url is an approved target
    # we validate the entire batch before sending http requests
    for url in request.urls:
        if url.host not in ALLOWED_HOSTS:
            raise HTTPException(
                status_code=400,
                detail=f"URL host is not approved: {url.host}"
            )

    # prevent too many simultaneous requests
    # a semaphore limits the number of tasks inside a code section
    semaphore = asyncio.Semaphore(5)
    
    async def process_url(url):
        # only 5 scraping operations can execute
        # inside this block at any given time
        async with semaphore:
            try:
                # reuse the extraction engine we already built
                result = await extract_page(
                    url=str(url),
                    selectors=request.selectors
                )
                return {
                    "status": "completed",
                    "data": result
                }
            
            except (
                httpx.RequestError,
                httpx.HTTPStatusError
            ):
                # a single failed website should't automatically
                # discard results from the rest of the batch
                return {
                    "status": "failed",
                    "url" : str(url),
                    "error": "Unable to retrieve webpage"
                }
            
            except SelectorSyntaxError:
                return {
                    "status": "failed",
                    "url": str(url),
                    "error": "Invalid CSS selectors"
                }
    
    # create one coroutine per url
    # similar to building an array of Promises in JS
    tasks = [process_url(url) for url in request.urls]
    
    # execute requests concurrently
    # equivalent in concept to await Promise.all(tasks)
    results = await asyncio.gather(*tasks)
    
    # count how many URLs succeeded or failed
    completed = sum(
        result["status"] == "completed"
        for result in results
    )
    
    return {
        "total_urls": len(request.urls),
        "completed": completed,
        "failed": len(request.urls) - completed,
        "results": results
    }

@app.post("/jobs", status_code=status.HTTP_202_ACCEPTED)
async def submit_job(request: ExtractionRequest):
    # validate the destination before adding work to the queue
    if request.url.host not in ALLOWED_HOSTS:
        raise HTTPException(
            status_code=400,
            detail="Url is not an approved scraping target"
        )

    # send a task message to redis
    # unlike calling extract_page(), this does not execute
    # the scraping operation in the API process
    # .delay() schedules work and immediately returns
    # a Celery result object containing the task id
    task = extract_task.delay(
        str(request.url),
        request.selectors
    )

    # http 202 indicates the request was accepted
    # but processing has not necessarily finished
    return {
        "job_id": task.id,
        "status": "submitted"
    }

@app.get("/jobs/{job_id}")
async def get_job(job_id: str):
    # look up the task's current state and stored result
    task = AsyncResult(job_id, app=celery_app)
    
    response = {
        "job_id": job_id,
        "status": task.state
    }
    
    # if the worker completed successfully, return the data
    if task.successful():
        response["result"] = task.result
    
    # if the worker failed, return a safe error message
    elif task.failed():
        response["error"] = "The scraping task failed"
    
    return response

@app.post(
    "/jobs/batch",
    status_code=status.HTTP_202_ACCEPTED
)
async def submit_batch_job(request: BatchExtractionRequest):
    # validate all urls before submitting the batch
    for url in request.urls:
        if (
            url.scheme != "https"
            or url.host not in ALLOWED_HOSTS
        ):
            raise HTTPException(
                status_code=400,
                detail=f"URL is not approved: {url}"
            )
    
    # convert pydantic httpURl objects into strings
    # celery needs JSON-serializable tasks arguments
    urls = [str(url) for url in request.urls]
    
    # queue the complete batch as one celery task
    # this returns without waiting for extraction
    task = extract_batch_task.delay(
        urls,
        request.selectors
    )
    
    return {
        "job_id": task.id,
        "status": "submitted",
        "total_urls": len(urls)
    }

@app.post(
    "/jobs/persisted/batch",
    status_code=202
)
async def submit_persistent_batch(request: BatchExtractionRequest):
    # validate every url before saving or queuing the job
    for url in request.urls:
        if (
            url.scheme != "https"
            or url.host not in ALLOWED_HOSTS
        ):
            raise HTTPException(
                status_code=400,
                detail=f"URL is not approved: {url}"
            )
    
    urls = [str(url) for url in request.urls]
    
    # create a new UUID that identifies the job
    job_id = uuid.uuid4()
    
    with SessionLocal.begin() as session:
        job = Job(
            id=job_id,
            status="pending",
            total_urls=len(urls)
        )
        session.add(job)
    
    try:
        # publish the job to redis through celery
        # we reuse the postgresql job id as the celery task id
        persistent_batch_task.apply_async(
            args=[
                str(job_id),
                urls,
                request.selectors
            ],
            task_id=str(job_id)
        )
    except OperationalError:
        # if the message broker cannot accept the task,
        # mark the database job as failed
        with SessionLocal.begin() as session:
            job = session.get(Job, job_id)
            job.status = "failed"
        
        raise HTTPException(
            status_code=503,
            detail="Task queue is unavailable"
        )
    
    # http 202 means that the task was accepted for processing
    return {
        "job_id": str(job_id),
        "status": "pending",
        "total_urls": len(urls)
    }

@app.get("/jobs/persisted/{job_id}")
async def get_persistent_job(job_id: uuid.UUID):
    # retrieve the job and its associated URL results
    with SessionLocal() as session:
        job = session.get(Job, job_id)
        
        if job is None:
            raise HTTPException(
                status_code=404,
                detail="Job not found"
            )
        
        # fetch individual webpage records for this job
        pages = session.scalars(
            select(ScrapedPage)
            .where(ScrapedPage.job_id == job_id)
            .order_by(ScrapedPage.id)
        ).all()
        
        # convert database records into JSON compatible data
        results = [
            {
                "url": page.url,
                "status": page.status,
                "data": page.data,
                "error": page.error
            }
            for page in pages
        ]
        
        # count successfully processed pages
        completed = sum(
            page.status == "completed"
            for page in pages
        )
        
        # count the number of URL results saved in PostgreSQL
        processed = len(pages)
        
        # calculate how many URLs haven't finished processing
        remaining = max(job.total_urls - processed, 0)
        
        # calculate the percentage of URLs processed
        # the max() and min() keep the result between 0 and 100
        progress_percent = (
            round(min(processed / job.total_urls * 100, 100), 1)
            if job.total_urls > 0
            else 0.0
        )
        
        return {
            "job_id": str(job.id),
            "status": job.status,
            "total_urls": job.total_urls,
            "processed_urls": len(pages),
            "completed": completed,
            "failed": len(pages) - completed,
            "created_at": job.created_at,
            "remaining": remaining,
            "progress_percent": progress_percent,
            "heartbeat_at": job.heartbeat_at,
            "results": results,
        }