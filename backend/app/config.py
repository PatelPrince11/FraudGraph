"""Settings come from environment variables, never hard-coded in code.

Locally they come from backend/.env; in Docker/production from the container's env.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg://fraud:fraud@localhost:5432/fraud")
