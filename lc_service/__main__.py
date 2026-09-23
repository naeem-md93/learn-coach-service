#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys
import dotenv
from lc_service.settings.project import PROJECT_SETTINGS


ENV_PATH = dotenv.find_dotenv(".env")
ENV_LOADED = dotenv.load_dotenv(ENV_PATH)

print(f"{ENV_LOADED=} | {ENV_PATH=}")


def main():
    """Run administrative tasks."""

    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(["", "runserver", f"{PROJECT_SETTINGS.HOST}:{PROJECT_SETTINGS.PORT}"])


if __name__ == '__main__':
    main()
