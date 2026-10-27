import uuid
import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from app.db_models import Job, ScrapedPage

def test_create_job(db_session):
    # create a job using the real SQLAlchemy model
    job = Job(
        status="pending",
        total_urls=2
    )
    
    db_session.add(job)
    db_session.flush()
    
    # sqlalchemy should generate a UUID
    assert isinstance(job.id, uuid.UUID)
    
    # query PostgreSQl to verify the record was stored
    stored_job = db_session.get(Job, job.id)
    
    assert stored_job is not None
    assert stored_job.status == "pending"
    assert stored_job.total_urls == 2

def test_save_scraped_page(db_session):
    # create a parent job
    job = Job(total_urls=1)
    db_session.add(job)
    db_session.flush()
    
    # associate a scraped page with the job
    page = ScrapedPage(
        job_id=job.id,
        url="https://books.toscrape.com/",
        status="completed",
        data={"title": "Books to Scrape"}
    )
    
    db_session.add(page)
    db_session.flush()
    
    # retrieve the persisted page
    stored_page = db_session.scalar(
        select(ScrapedPage).where(
            ScrapedPage.job_id == job.id
        )
    )
    
    assert stored_page is not None
    assert stored_page.data["title"] == "Books to Scrape"
    assert stored_page.status == "completed"
    
def test_duplicate_page_is_rejected(db_session):
    # create a job
    job = Job(total_urls=2)
    db_session.add(job)
    db_session.flush()
    
    url = "https://books.toscrape.com/"
    
    # save the first occurrence of the URL
    db_session.add(
        ScrapedPage(
            job_id=job.id,
            url=url,
            status="completed"
        )
    )
    db_session.flush()
    
    # try inserting the same URL for the same job
    db_session.add(
        ScrapedPage(
            job_id=job.id,
            url=url,
            status="completed"
        )
    )
    
    # PostgreSQL should enforce the unique constraint
    with pytest.raises(IntegrityError):
        db_session.flush()