from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict


class ProjectSettings(BaseSettings):
    HOST: str
    PORT: int

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="PROJECT_",
        extra="ignore"
    )

PROJECT_SETTINGS = ProjectSettings()


class DatabaseSettings(BaseSettings):
    # Discrete connection params, used for local docker-compose Postgres.
    # Ignored when DJANGO_SETTINGS's DjangoSettings.DATABASE_URL is set
    # (e.g. Render managed Postgres, which provides a single connection
    # string instead of discrete params). All fields are optional here so
    # this class doesn't fail to load in environments that only set
    # DATABASE_URL.
    NAME: str | None = None
    USER: str | None = None
    PASSWORD: str | None = None
    HOST: str | None = None
    PORT: int | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="POSTGRES_",
        extra="ignore"
    )

DATABASE_SETTINGS = DatabaseSettings()


class DjangoSettings(BaseSettings):
    # Django-specific deployment settings, read directly from the process
    # environment (with local-dev defaults via `.env`), following the same
    # pydantic-settings pattern as ProjectSettings/DatabaseSettings above.
    SECRET_KEY: str = "django-insecure-3-o=j&l2#1v2&mcuh4t2rtqy&(+*4yprvetl5+-0@-5*z@d5g2"
    DEBUG: bool = False
    ALLOWED_HOSTS: str = ""
    CORS_ALLOWED_ORIGINS: str = ""
    CSRF_TRUSTED_ORIGINS: str = ""
    # Single connection string (e.g. Render managed Postgres). When unset,
    # DATABASE_SETTINGS (discrete POSTGRES_* vars) is used instead.
    DATABASE_URL: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="DJANGO_",
        extra="ignore"
    )

DJANGO_SETTINGS = DjangoSettings()


class RenderSettings(BaseSettings):
    # Render sets RENDER_EXTERNAL_HOSTNAME automatically (no DJANGO_ prefix)
    # for every web service on deploy. Read separately so it can be added to
    # ALLOWED_HOSTS/CSRF_TRUSTED_ORIGINS out of the box, without the user
    # having to duplicate the hostname into DJANGO_ALLOWED_HOSTS manually.
    EXTERNAL_HOSTNAME: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="RENDER_",
        extra="ignore"
    )

RENDER_SETTINGS = RenderSettings()


class RailwaySettings(BaseSettings):
    # Railway sets RAILWAY_PUBLIC_DOMAIN automatically (no DJANGO_ prefix)
    # for every public service on deploy. Read separately so it can be added
    # to ALLOWED_HOSTS/CSRF_TRUSTED_ORIGINS out of the box, mirroring
    # RenderSettings.EXTERNAL_HOSTNAME above.
    PUBLIC_DOMAIN: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="RAILWAY_",
        extra="ignore"
    )

RAILWAY_SETTINGS = RailwaySettings()