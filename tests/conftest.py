import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from econ.ingest import load_observations


@pytest.fixture(scope="session")
def obs():
    return load_observations()
