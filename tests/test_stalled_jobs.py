from datetime import datetime, timedelta, timezone
from check_stalled_jobs import _is_job_stalled

def test_old_heartbeat_is_stalled():
    # simulate the current time
    now = datetime.now(timezone.utc)
    
    # simulate a worker that last responded 15 min ago
    old_heartbeat = now - timedelta(minutes=15)
    
    # a running job with an old heartbeat should be stalled
    result = _is_job_stalled(
        status="running",
        heartbeat_at=old_heartbeat,
        now=now
    )
    
    assert result is True

def test_recent_heartbeat_is_not_stalled():
    now = datetime.now(timezone.utc)
    
    # simulate a worker that responded just 2 min ago
    recent_heartbeat = now - timedelta(minutes=2)
    
    result = _is_job_stalled(
        status="running",
        heartbeat_at=recent_heartbeat,
        now=now 
    )
    
    assert result is False

def test_completed_job_is_not_stalled():
    now = datetime.now(timezone.utc)
    
    result = _is_job_stalled(
        status="completed",
        heartbeat_at=now - timedelta(minutes=20),
        now=now
    )
    
    assert result is False