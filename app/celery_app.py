import os
from celery import Celery
from dotenv import load_dotenv

# load env variables from .env for local development
# Docker Compose provides these variables directly
load_dotenv()

# read redis connection URLs from env variables
# default to localhost when running outside Docker
broker_url = os.getenv(
    "CELERY_BROKER_URL",
    "redis://localhost:6379/0"
)

result_backend = os.getenv(
    "CELERY_RESULT_BACKEND",
    "redis://localhost:6379/1"
)

# create the celery application
celery_app = Celery(
    "scraperflow",
    broker=broker_url,
    backend=result_backend,
    include=["app.tasks", "app.persistent_tasks"]
)

# Configure how Celery handles task messages
celery_app.conf.update(
    # JSON is used for task arguments and results
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    
    # retain results for one hour development
    result_expires=3600,
    
    # allow worker processes to report that tasks started
    task_track_started=True,
)