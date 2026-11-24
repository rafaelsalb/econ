import pytest

from econ.ingest import load_observations


@pytest.fixture(scope="session")
def obs():
    return load_observations()
