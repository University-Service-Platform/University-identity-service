import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional


def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return value.strip()


def _env_int(name: str, default: int) -> int:
    value = _env(name)
    return int(value) if value is not None else default


DEVELOPMENT_JWT_SECRET = "development_secret_key_change_in_production"


@dataclass(frozen=True)
class Settings:
    """
    Centralized service configuration read from environment variables.
    Every value has a development-safe default so the service runs locally without a .env file.
    """
    service_name: str
    environment: str
    database_url: str
    jwt_algorithm: str
    jwt_secret_key: str
    access_token_expire_minutes: int
    log_level: str

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"

    def validate(self) -> None:
        """Refuse to start a production deployment with development-only secrets."""
        if self.is_production and self.jwt_secret_key == DEVELOPMENT_JWT_SECRET:
            raise RuntimeError(
                "JWT_SECRET_KEY must be set to a non-default value when ENVIRONMENT=production."
            )


@lru_cache
def get_settings() -> Settings:
    settings = Settings(
        service_name="identity-service",
        environment=_env("ENVIRONMENT", "development"),
        database_url=_env("DATABASE_URL", "sqlite:///./identity.db"),
        jwt_algorithm=_env("JWT_ALGORITHM", "HS256"),
        jwt_secret_key=_env("JWT_SECRET_KEY", DEVELOPMENT_JWT_SECRET),
        access_token_expire_minutes=_env_int("ACCESS_TOKEN_EXPIRE_MINUTES", 60),
        log_level=_env("LOG_LEVEL", "INFO"),
    )
    settings.validate()
    return settings
