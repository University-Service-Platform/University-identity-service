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


def _env_float(name: str, default: float) -> float:
    value = _env(name)
    return float(value) if value is not None else default


API_V1_PREFIX = "/api/v1"

DEVELOPMENT_JWT_SECRET = "development_secret_key_change_in_production"
SUPPORTED_JWT_ALGORITHMS = ("RS256", "HS256")


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
    jwt_private_key_path: Optional[str]
    jwt_public_key_path: Optional[str]
    jwt_issuer: str
    jwt_audience: str
    access_token_expire_minutes: int
    log_level: str
    # Directory Service integration; None disables it (dependent features return 503)
    directory_service_base_url: Optional[str]
    directory_service_timeout_seconds: float

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"

    def validate(self) -> None:
        """Refuse to start with an unsupported algorithm or, in production, development-only secrets."""
        if self.jwt_algorithm not in SUPPORTED_JWT_ALGORITHMS:
            raise RuntimeError(f"JWT_ALGORITHM must be one of {SUPPORTED_JWT_ALGORITHMS}.")
        if not self.is_production:
            return
        if self.jwt_algorithm == "HS256" and self.jwt_secret_key == DEVELOPMENT_JWT_SECRET:
            raise RuntimeError(
                "JWT_SECRET_KEY must be set to a non-default value when ENVIRONMENT=production."
            )
        if self.jwt_algorithm == "RS256" and not (self.jwt_private_key_path and self.jwt_public_key_path):
            raise RuntimeError(
                "JWT_PRIVATE_KEY_PATH and JWT_PUBLIC_KEY_PATH must be set when ENVIRONMENT=production."
            )


@lru_cache
def get_settings() -> Settings:
    settings = Settings(
        service_name="identity-service",
        environment=_env("ENVIRONMENT", "development"),
        database_url=_env("DATABASE_URL", "sqlite:///./identity.db"),
        jwt_algorithm=_env("JWT_ALGORITHM", "RS256").upper(),
        jwt_secret_key=_env("JWT_SECRET_KEY", DEVELOPMENT_JWT_SECRET),
        jwt_private_key_path=_env("JWT_PRIVATE_KEY_PATH"),
        jwt_public_key_path=_env("JWT_PUBLIC_KEY_PATH"),
        jwt_issuer=_env("JWT_ISSUER", "university-identity-service"),
        jwt_audience=_env("JWT_AUDIENCE", "university-services-platform"),
        access_token_expire_minutes=_env_int("ACCESS_TOKEN_EXPIRE_MINUTES", 60),
        log_level=_env("LOG_LEVEL", "INFO"),
        directory_service_base_url=_env("DIRECTORY_SERVICE_BASE_URL"),
        directory_service_timeout_seconds=_env_float("DIRECTORY_SERVICE_TIMEOUT_SECONDS", 3.0),
    )
    settings.validate()
    return settings
