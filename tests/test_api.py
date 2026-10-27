from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app

# testclient sends requests directly to FastAPI
# no running web server is required
client = TestClient(app)

def test_health_endpoint():
    response = client.get("/health")
    
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}
    
def test_rejects_unapproved_url():
    response = client.post(
        "/jobs",
        json={
            "url": "https://example.com/",
            "selectors": {"heading": "h1"}
        }
    )
    
    # example.com is not in ALLOWED_HOSTS
    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Url is not an approved scraping target"
    )

@patch("app.main.extract_task.delay")
def test_submits_approved_job(mock_delay):
    # replace the real celery .delay() function
    # this prevents the test from sending a task to redis
    mock_delay.return_value.id = "test-task-123"
    
    response = client.post(
        "/jobs",
        json={
            "url": "https://books.toscrape.com/",
            "selectors": {"titles": "h3 a"}
        }
    )
    
    assert response.status_code == 202
    
    assert response.json() == {
        "job_id": "test-task-123",
        "status": "submitted"
    }
    
    # verify celery received the expected arguments
    mock_delay.assert_called_once_with(
        "https://books.toscrape.com/",
        {"titles": "h3 a"}
    )
    
    