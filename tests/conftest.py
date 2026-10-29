import pytest
from fastapi.testclient import TestClient

from fake_repository import FakeRepository
from twin.api.app import create_app
from twin.common.config import Settings


@pytest.fixture
def repo() -> FakeRepository:
    return FakeRepository()


@pytest.fixture
def client(repo: FakeRepository) -> TestClient:
    settings = Settings(live_interval_s=0.02, cors_origins="*")
    return TestClient(create_app(repository=repo, settings=settings))
