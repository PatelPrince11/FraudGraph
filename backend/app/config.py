"""Settings come from environment variables, never hard-coded in code.

Locally they come from backend/.env; in Docker/CI from the container's environment.
load_dotenv never overrides a variable that is already set, so the container's
values win over any .env file.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg://fraud:fraud@localhost:5432/fraud")

# Where model.json/meta.json live. Default is the repo's data/models; the container
# sets MODEL_DIR=/models and mounts the files there.
MODEL_DIR = Path(os.getenv("MODEL_DIR", Path(__file__).resolve().parents[2] / "data" / "models"))
