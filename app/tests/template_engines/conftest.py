import shutil
from pathlib import Path
from tempfile import mkdtemp

import pytest


@pytest.fixture
def temp_dir():
    base_dir = Path(mkdtemp())
    try:
        yield base_dir
    finally:
        shutil.rmtree(base_dir)
