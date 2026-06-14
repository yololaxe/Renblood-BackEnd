import os
from pathlib import Path

from dotenv import load_dotenv


VALID_ENVIRONMENTS = {"local", "staging", "production"}


def load_environment(base_dir: Path) -> tuple[str, Path]:
    environment = os.getenv("DJANGO_ENV", "local").strip().lower()
    if environment not in VALID_ENVIRONMENTS:
        raise RuntimeError(
            "Invalid DJANGO_ENV. Expected one of: local, staging, production."
        )

    env_file = base_dir / f".env.{environment}"
    load_dotenv(env_file)
    os.environ.setdefault("DJANGO_ENV", environment)
    return environment, env_file
