from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from app.database import SessionLocal
from app.db_models import Job

def _is_job_stalled(status, heartbeat_at, now, minutes=10):
    # check whether a running job's heartbeat is too old
    
    # only running jobs can be considered stalled
    if status != "running":
        return False
    
    # a missing heartbeat needs separate handling
    if heartbeat_at is None:
        return False
    
    # calculate the max allowable heartbeat age
    cutoff = now - timedelta(minutes=minutes)
    
    # return true if the heartbeat is older than the cutoff
    return heartbeat_at < cutoff

# a running job is potentially stalled if its heartbeat
# has not been updated within the past 10 minutes
STALE_AFTER_MINUTES = 10

def check_stalled_jobs():
    # get the current UTC time
    now = datetime.now(timezone.utc)
    
    # calculate the cutoff time for identifying stale jobs
    cutoff = now - timedelta(minutes=STALE_AFTER_MINUTES)
    
    # open a database session
    # similar to using a prisma client to query PostgreSQL
    with SessionLocal() as db:
        # retrieve running jobs whose last heartbeat
        # is older than our cutoff time
        stmt = select(Job).where(
            Job.status == "running",
            Job.heartbeat_at < cutoff,
        )
        
        stalled_jobs = db.scalars(stmt).all()
        
        # no potentially stalled jobs were found
        if not stalled_jobs:
            print("No potentially stalled jobs found.")
            return
        
        # display information about each potentially stalled job
        print(f"Found {len(stalled_jobs)} potentially stalled job(s):")
        
        for job in stalled_jobs:
            print(
                f"Job ID: {job.id} | "
                f"Status: {job.status} | "
                f"Last heartbeat: {job.heartbeat_at}"
            )

# only execute this function when this file is run directly
# similar to checking require.main === module in Node.js
if __name__ == "__main__":
    check_stalled_jobs()