import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
    UniqueConstraint
)

from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base

class Job(Base):
    # name of postgresql table
    __tablename__ = "jobs"
    
    # primary key generated using Python's uuid module
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    
    # new jobs begin in the pending state
    status: Mapped[str] = mapped_column(
        String(20),
        default="pending",
        nullable=False
    )
    
    # how many urls were submitted in the batch
    total_urls: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )
    
    # postgresql generates the creation timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    
    # timestamp of the most recent worker activity
    # we update this when processing starts and as URLs finish
    # None means the worker hasn't reported activity yet
    heartbeat_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

class ScrapedPage(Base):
    __tablename__ = "scraped_pages"
    
    __table_args__ = (
        UniqueConstraint(
            "job_id",
            "url",
            name="uq_scraped_pages_job_url"
        ),
    )
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    
    # foreign key linking this result to its parent job
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("jobs.id"),
        nullable=False,
        index=True
    )
    
    url: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )
    
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False
    )
    
    # JSONB stores structured extracted info
    # similar in purpose to PostgreSQL JSON fields with Prisma
    data: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True
    )
    
    # store an error msg if scrapping failed
    error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )