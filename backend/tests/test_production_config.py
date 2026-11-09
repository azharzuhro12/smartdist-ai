import pytest
from backend.app.core.config import Settings


def test_production_settings_rejects_weak_secret():
    """In production, SECRET_KEY with < 32 characters or default markers must raise ValueError."""
    with pytest.raises(ValueError) as exc_info:
        Settings(
            ENVIRONMENT="production",
            SECRET_KEY="short_dev_key",
        )
    assert "at least 32 characters" in str(exc_info.value) or "insecure" in str(exc_info.value)


def test_production_settings_rejects_default_marker():
    """In production, SECRET_KEY containing 'dev' or 'change_in_production' must raise ValueError."""
    with pytest.raises(ValueError) as exc_info:
        Settings(
            ENVIRONMENT="production",
            SECRET_KEY="this_is_a_very_long_secret_key_but_contains_dev_marker_which_is_bad",
        )
    assert "default or insecure placeholder" in str(exc_info.value)


def test_production_settings_accepts_strong_secret():
    """In production, a 64-hex char strong key must be accepted cleanly."""
    valid_key = "a1b2c3d4e5f67890123456789abcdef0123456789abcdef0123456789abcdef0"
    s = Settings(
        ENVIRONMENT="production",
        SECRET_KEY=valid_key,
    )
    assert s.SECRET_KEY == valid_key

