import os
import pytest
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.engine import make_url
from app.database import Base

# import the SQLAlchemy models so Base knows which
# PostgreSQL tables need to be created
import app.db_models # noqa: F401

# load the local Docker database credentials
load_dotenv(".env.docker")

@pytest.fixture(scope="session")
def test_engine():
    # read the test database URL only when a database
    # test actually requests this fixture
    test_database_url = os.getenv("TEST_DATABASE_URL")
    
    if not test_database_url:
        raise RuntimeError(
            "TEST_DATABASE_URL is required for database tests"
        )
    
    # verify that the URL points to the dedicated test DB
    parsed_url = make_url(test_database_url)
    
    if parsed_url.database != "scrapeflow_test":
        raise RuntimeError(
            "Refusing to run against a non-test database"
        )
    
    # create a separate engine for integration testing
    engine = create_engine(
        test_database_url,
        pool_pre_ping=True
    )
    
    try:
        # verify the database name after connecting
        with engine.connect() as connection:
            actual_database = connection.execute(
                text("SELECT current_database()")
            ).scalar_one()
            
            if actual_database != "scrapeflow_test":
                raise RuntimeError(
                    "Unsafe database connection"
                )
        
        # ensure SQLAlchemy's registered tables exist
        Base.metadata.create_all(bind=engine)
        yield engine
    
    finally:
        # release connections when testing finishes
        engine.dispose()

@pytest.fixture
def db_session(test_engine):
    # open a database connection and start a transaction
    connection = test_engine.connect()
    transaction = connection.begin()
    
    # bind a session to this test-specific connection
    TestSession = sessionmaker(
        bind=connection,
        join_transaction_mode="create_savepoint"
    )
    
    session = TestSession()
    
    # give the test access to its temporary session
    yield session
    
    # close the session, then undo changes made by the test
    session.close()
    transaction.rollback()
    connection.close()