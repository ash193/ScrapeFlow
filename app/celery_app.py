from celery import Celery

# create our celery application
# similar to init a shared service client in node.js
celery_app = Celery(
    "scraperflow",
    
    # Redis database 0 holds queued task messages
    broker="redis://localhost:6379/0",
    
    # Redis database 1 temp stores task results
    backend="redis://localhost:6379/1",
    
    # Tell Celery where our task functions are defined
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