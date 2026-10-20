import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# load env variables from the project's .env file
# similar to dotenv.config() in Node.js
load_dotenv()

# read the database connection string
DATABASE_URL = os.environ["DATABASE_URL"]

# create the SQLAlchemy engine
# the engine manages database connections and pooling
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True
)

# a factory for creating database session
# a session is used to query and modify records
SessionLocal = sessionmaker(bind=engine)

# base class that our database models will inherit from
class Base(DeclarativeBase):
    pass