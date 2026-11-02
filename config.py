"""Application configuration.

All settings come from environment variables (optionally loaded from a local
``.env`` file) so that credentials never live in the source code.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def _bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-change-me")

    # Database
    DB_ENGINE = os.getenv("DB_ENGINE", "sqlite").strip().lower()  # "sqlite" | "mysql"
    SQLITE_PATH = os.getenv("SQLITE_PATH", str(BASE_DIR / "ecommerce_bi.db"))
    MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
    MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
    MYSQL_USER = os.getenv("MYSQL_USER", "root")
    MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
    MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "ecommerce_bi")

    # Behaviour
    AUTO_SEED = _bool("AUTO_SEED", True)
    CURRENCY_SYMBOL = os.getenv("CURRENCY_SYMBOL", "₹")
    DEBUG = _bool("FLASK_DEBUG", False)
