import json
from typing import List, Union
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # App Settings
    PROJECT_NAME: str = "SmartDist AI"
    PROJECT_VERSION: str = "0.1.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    API_V1_STR: str = "/api/v1"

    # CORS Settings
    CORS_ORIGINS: Union[List[str], str] = [
        "http://localhost:3000",
        "http://localhost:3030",
        "http://localhost:8000",
        "http://localhost:8035",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3030",
        "http://127.0.0.1:8000",
        "http://127.0.0.1:8035",
    ]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            if not v.strip():
                return []
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return parsed
            except Exception:
                pass
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, list):
            return v
        raise ValueError(f"Invalid CORS_ORIGINS format: {v}")

    # Security & Authentication Settings
    SECRET_KEY: str = Field(
        default="smartdist_dev_secret_key_change_in_production_super_safe_32chars",
        description="Secret key for signing JWT tokens. Must be changed in production.",
    )
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    ALGORITHM: str = "HS256"
    INITIAL_ADMIN_EMAIL: str = "admin@smartdist.ai"
    INITIAL_ADMIN_USERNAME: str = "admin"
    INITIAL_ADMIN_PASSWORD: str = "Admin@SmartDist2026!"
    RATE_LIMIT_LOGIN_PER_MINUTE: int = 5
    RATE_LIMIT_ASSISTANT_PER_MINUTE: int = 30

    # Database Settings
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: int = 5435
    POSTGRES_DB: str = "smartdist_db"
    POSTGRES_USER: str = "smartdist_user"
    POSTGRES_PASSWORD: str = "smartdist_secure_password"
    POSTGRES_MIGRATION_URL: Union[str, None] = None
    POSTGRES_READONLY_USER: str = "smartdist_readonly"
    POSTGRES_READONLY_PASSWORD: str = "smartdist_readonly_password"
    POSTGRES_READONLY_URL: Union[str, None] = None
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20
    DATABASE_POOL_TIMEOUT: int = 30
    DATABASE_URL: Union[str, None] = None

    @property
    def sync_database_uri(self) -> str:
        if self.DATABASE_URL:
            return self.DATABASE_URL
        return (
            f"postgresql+psycopg2://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@"
            f"{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def migration_database_uri(self) -> str:
        if self.POSTGRES_MIGRATION_URL:
            return self.POSTGRES_MIGRATION_URL
        return self.sync_database_uri

    @property
    def readonly_database_uri(self) -> str:
        if self.POSTGRES_READONLY_URL:
            return self.POSTGRES_READONLY_URL
        return (
            f"postgresql+psycopg2://{self.POSTGRES_READONLY_USER}:{self.POSTGRES_READONLY_PASSWORD}@"
            f"{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    # Redis Settings
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6380
    REDIS_PASSWORD: str = "smartdist_redis_pass"
    REDIS_DB: int = 0
    REDIS_SOCKET_TIMEOUT: float = 5.0

    @property
    def redis_url(self) -> str:
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    # Celery Settings
    CELERY_BROKER_URL: Union[str, None] = None
    CELERY_RESULT_BACKEND: Union[str, None] = None
    CELERY_TASK_ALWAYS_EAGER: bool = False

    @property
    def broker_url(self) -> str:
        if self.CELERY_BROKER_URL:
            return self.CELERY_BROKER_URL
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/1"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/1"

    @property
    def result_backend_url(self) -> str:
        if self.CELERY_RESULT_BACKEND:
            return self.CELERY_RESULT_BACKEND
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/2"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/2"

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"

    @model_validator(mode="after")
    def validate_production_secrets(self) -> "Settings":
        if self.ENVIRONMENT.lower() in ("production", "prod"):
            if len(self.SECRET_KEY) < 32:
                raise ValueError("In production, SECRET_KEY must be at least 32 characters long.")
            insecure_markers = ["dev", "change_in_production", "default", "example"]
            if any(marker in self.SECRET_KEY.lower() for marker in insecure_markers):
                raise ValueError(
                    "In production, SECRET_KEY must not contain default or insecure placeholder values."
                )
        return self

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()
