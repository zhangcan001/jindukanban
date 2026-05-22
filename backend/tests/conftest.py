import os
from pathlib import Path
import sys
import asyncio

import pytest

os.environ["DATABASE_URL"] = "sqlite:///./test_progress_dashboard.db"
os.environ["DISABLE_SQLITE_WAL"] = "1"

if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from app.database import Base, engine  # noqa: E402
import app.models  # noqa: E402,F401


@pytest.fixture(autouse=True)
def reset_test_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    Path("test_progress_dashboard.db").unlink(missing_ok=True)
