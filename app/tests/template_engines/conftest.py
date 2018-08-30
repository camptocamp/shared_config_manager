import pytest
import shutil
from tempfile import mkdtemp


@pytest.yield_fixture()
def temp_dir():
    base_dir = str(mkdtemp())
    try:
        yield base_dir
    finally:
        shutil.rmtree(base_dir)
