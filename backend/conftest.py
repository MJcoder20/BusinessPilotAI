
import pytest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.core.config import settings
from app.core.database import Base, get_db
from app.models import (
    Customer,
    Product,
    SalesOrder,
    OrderItem,
    Invoice,
    Opportunity,
    Conversation,
    ChatMessage,
)


TEST_DATABASE_URL = make_url(
    settings.resolved_database_url
).set(
    database="businesspilot_test_db"
).render_as_string(hide_password=False)


@pytest.fixture(scope="session")
def test_engine():
    engine = create_engine(
        TEST_DATABASE_URL,
        pool_pre_ping=True,
    )

    Base.metadata.create_all(bind=engine)

    yield engine

    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture
def db_session(test_engine):
    connection = test_engine.connect()
    transaction = connection.begin()

    TestingSessionLocal = sessionmaker(
        bind=connection,
        autoflush=False,
        autocommit=False,
        join_transaction_mode="create_savepoint",
    )

    session = TestingSessionLocal()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    # Do not enter the TestClient context manager:
    # this prevents application startup from initializing
    # the real LangGraph checkpoint storage.
    test_client = TestClient(app)

    yield test_client

    test_client.close()
    app.dependency_overrides.clear()
