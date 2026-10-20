from app.database import Base, engine

# import the model classes so SQLAlchemy knows
# which tables belong to the Base metadata
from app import db_models

# create tables that don't already exist
# this is useful for initial development
Base.metadata.create_all(bind=engine)

print("Database tables created successfully!")