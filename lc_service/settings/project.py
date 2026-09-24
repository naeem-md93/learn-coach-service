from pydantic import Field
from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict


class ProjectSettings(BaseSettings):
    # Only consulted by local dev tooling (e.g. `manage.py runserver`).
    # Optional with dev-friendly defaults so importing settings doesn't
    # hard-fail in production environments (Railway, Render, ...) that
    # don't set PROJECT_HOST/PROJECT_PORT — the actual bind address/port
    # in production comes from gunicorn's --bind / $PORT instead.
    HOST: str = "localhost"
    PORT: int = 8008

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
    # Optional, comma-separated Python regex patterns (each matched against
    # the *full* origin, e.g. r"^https://learn-coach-ui-.*\.vercel\.app$").
    # Lets one pattern cover every Vercel preview-deployment subdomain
    # (which Vercel generates per-branch/per-PR, e.g.
    # learn-coach-ui-git-<branch>-<team>.vercel.app) without having to add
    # each preview URL to CORS_ALLOWED_ORIGINS by hand. Empty by default —
    # only exact-match CORS_ALLOWED_ORIGINS applies until this is set.
    CORS_ALLOWED_ORIGIN_REGEXES: str = ""
    CSRF_TRUSTED_ORIGINS: str = ""
    # Single connection string (e.g. Render/Railway managed Postgres). When
    # unset, DATABASE_SETTINGS (discrete POSTGRES_* vars) is used instead.
    # Managed Postgres add-ons set the unprefixed DATABASE_URL (no DJANGO_
    # prefix) themselves, so this reads that name directly via
    # validation_alias instead of the model's usual DJANGO_ prefix.
    DATABASE_URL: str | None = Field(default=None, validation_alias="DATABASE_URL")
    # Controls both the root logger level and the request-logging
    # middleware's verbosity (DEBUG also turns on masked request/response
    # body logging — see lc_service.api.common.middleware). Defaults to
    # INFO so normal request/response summary lines always show, without
    # needing any env var set, in dev or on Railway.
    LOG_LEVEL: str = "INFO"

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


class LogicSettings(BaseSettings):
    # learn-coach-logic (FastAPI) is a stateless compute service Django
    # calls out to (title extraction, chat, quiz generation, page
    # rendering — see CONTEXT.md Service Boundaries). No DB of its own.
    #
    # BASE_URL: where *Django* reaches FastAPI to call its endpoints
    # (e.g. POST {BASE_URL}/extract-title). Defaults to the local dev
    # FastAPI port; on docker-compose/Railway/Render this should be the
    # internal service hostname (e.g. http://logic:8001).
    BASE_URL: str = "http://localhost:8001"
    # DJANGO_INTERNAL_BASE_URL: the address at which *this Django
    # instance* is reachable from FastAPI, used to build the file URL
    # Django hands to FastAPI so it can download the PDF itself (per
    # CONTEXT.md: a single HTTP-fetchable URL, not a shared volume path).
    # This is deliberately a separate setting from Django's own public
    # ALLOWED_HOSTS/browser-facing URL: in a container network the two
    # sides usually see each other under different hostnames (e.g. the
    # browser hits `https://api.example.com` while FastAPI, on the same
    # docker network, must use `http://django:8000`). Defaults to
    # localhost for local dev where both processes run on the host.
    DJANGO_INTERNAL_BASE_URL: str = "http://localhost:8008"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="LOGIC_",
        extra="ignore"
    )

LOGIC_SETTINGS = LogicSettings()


class GunicornSettings(BaseSettings):
    # Gunicorn's own defaults (sync worker, 1 worker, 30s --timeout) are
    # unsafe for this app: Resource upload (and, per CONTEXT.md, chat/quiz
    # later) synchronously calls learn-coach-logic (FastAPI) and waits for
    # its full response — which can legitimately take up to
    # EXTRACT_TITLE_TIMEOUT_SECONDS (45s, see resources/services.py) when
    # FastAPI has to download a large PDF from a remote URL and/or call an
    # AI model. Gunicorn's default 30s --timeout kills the worker (SIGKILL,
    # "WORKER TIMEOUT") well before our own 45s timeout has a chance to
    # return a graceful fallback, turning a merely slow-but-valid request
    # into a hard crash. These values are read by the Dockerfile/Procfile
    # start command via env vars (not hardcoded in gunicorn's CLI flags) so
    # they can be tuned per-environment without an image rebuild.
    #
    # TIMEOUT: worker kill threshold, in seconds. Must stay comfortably
    # above the slowest known synchronous FastAPI call. 60s gives ~15s of
    # margin over the 45s extract-title timeout.
    TIMEOUT: int = 60
    # WORKERS: number of OS processes. Each sync/gthread worker can only
    # handle one request at a time per thread, so a single slow upload must
    # not be able to starve every other concurrent user. 3 is a small,
    # deliberately-not-over-engineered value for an MVP (Railway's default
    # free/starter plans are typically 1-2 vCPUs; the common "2 x CPU + 1"
    # gunicorn sizing guideline lands around this for 1 vCPU).
    WORKERS: int = 3
    # THREADS: with the `gthread` worker class (set below), each worker
    # process can serve this many requests concurrently via threads, so an
    # I/O-bound request blocked on `requests.post(...)` to FastAPI doesn't
    # occupy an entire process by itself. 2 threads/worker x 3 workers = 6
    # concurrent in-flight requests, enough headroom for MVP traffic without
    # tuning further.
    THREADS: int = 2
    # WORKER_CLASS: `gthread` (threaded sync worker) instead of the default
    # `sync`, specifically so THREADS above actually takes effect. Plain
    # `sync` ignores --threads entirely (1 request per worker process).
    WORKER_CLASS: str = "gthread"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="GUNICORN_",
        extra="ignore"
    )

GUNICORN_SETTINGS = GunicornSettings()