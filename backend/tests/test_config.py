from backend.app.core.config import Settings, settings


def test_settings_loading():
    """Verify settings load default and configured parameters correctly."""
    assert settings.PROJECT_NAME == "SmartDist AI"
    assert settings.API_V1_STR == "/api/v1"
    assert settings.POSTGRES_DB == "smartdist_db"
    assert settings.REDIS_PORT == 6380 or settings.REDIS_PORT == 6379


def test_database_uri_generation():
    """Verify SQLAlchemy URI is constructed properly with driver and credentials."""
    uri = settings.sync_database_uri
    assert uri.startswith("postgresql+psycopg2://")
    assert "smartdist_user" in uri
    assert "smartdist_db" in uri


def test_redis_url_generation():
    """Verify Redis URL is constructed properly."""
    url = settings.redis_url
    assert url.startswith("redis://")
    assert f":{settings.REDIS_PORT}/0" in url


def test_cors_origins_parsing():
    """Verify CORS origins string or list parser handles valid inputs."""
    custom_settings = Settings(
        CORS_ORIGINS='["http://localhost:3000", "http://example.com"]'
    )
    assert "http://localhost:3000" in custom_settings.CORS_ORIGINS
    assert "http://example.com" in custom_settings.CORS_ORIGINS
