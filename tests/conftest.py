import tempfile
import pytest
from pathlib import Path

from itera_mcp.database import init_db, close_db


@pytest.fixture
def temp_db():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=True) as f:
        path = Path(f.name)
        conn = init_db(str(path))
        yield conn
        close_db()
