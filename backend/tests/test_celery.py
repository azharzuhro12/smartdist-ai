from backend.app.core.redis import check_redis_connection
from backend.app.workers.celery_app import celery_app
from backend.app.workers.tasks import verify_infrastructure


def test_celery_configuration():
    """Verify Celery application settings and registered tasks."""
    assert celery_app.conf.task_serializer == "json"
    assert "json" in celery_app.conf.accept_content
    assert celery_app.conf.timezone == "UTC"
    assert "backend.app.workers.tasks.verify_infrastructure" in celery_app.tasks


def test_celery_task_direct_execution():
    """
    Test direct execution of verify_infrastructure background task.
    Verifies that the task callable logic runs and returns structured verification.
    """
    result = verify_infrastructure.apply(kwargs={"payload": {"test_run": True}})
    data = result.get(timeout=10)
    assert data["status"] == "success"
    assert "Celery infrastructure worker verified successfully" in data["message"]
    assert data["input_payload"] == {"test_run": True}


def test_celery_live_worker_execution():
    """
    Test asynchronous task dispatch and result retrieval via Redis broker and live worker.
    """
    if not check_redis_connection():
        import pytest
        pytest.fail("Redis server is unreachable for Celery live task test.")

    async_res = verify_infrastructure.delay({"test_mode": "live_worker_test"})
    data = async_res.get(timeout=10)
    assert data["status"] == "success"
    assert data["input_payload"] == {"test_mode": "live_worker_test"}
