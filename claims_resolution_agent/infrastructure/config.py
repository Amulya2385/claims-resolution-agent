import os
from urllib.parse import quote_plus

from dotenv import load_dotenv

load_dotenv()

POSTGRES_DB = os.getenv("POSTGRES_DB")
POSTGRES_USER = os.getenv("POSTGRES_USER")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5433")

_required = {
    "POSTGRES_DB": POSTGRES_DB,
    "POSTGRES_USER": POSTGRES_USER,
    "POSTGRES_PASSWORD": POSTGRES_PASSWORD,
}

_missing = [name for name, value in _required.items() if not value]

if _missing:
    raise RuntimeError(
        f"Missing required environment variables: {', '.join(_missing)}"
    )

DATABASE_URL = (
    f"postgresql+psycopg://"
    f"{quote_plus(POSTGRES_USER)}:"
    f"{quote_plus(POSTGRES_PASSWORD)}@"
    f"{POSTGRES_HOST}:{POSTGRES_PORT}/"
    f"{POSTGRES_DB}"
)