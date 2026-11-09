import pytest
from backend.app.core.redis import check_redis_connection, get_redis_client


def test_redis_client_initialization():
    """Verify Redis client initializes with configured connection parameters."""
    client = get_redis_client()
    assert client is not None


def test_redis_live_connectivity():
    """
    Test live Redis connectivity.
    Pings the Redis server and tests basic key write/read/delete.
    """
    is_connected = check_redis_connection()
    if not is_connected:
        pytest.fail(
            "Redis server is currently unreachable. Ensure the Redis container is running and healthy."
        )

    client = get_redis_client()
    # Ping
    assert client.ping() is True

    # Key write, read, delete verification
    test_key = "smartdist:infra_test"
    test_value = "pong_verification_value"
    client.set(test_key, test_value, ex=60)
    read_value = client.get(test_key)
    assert read_value == test_value
    client.delete(test_key)
