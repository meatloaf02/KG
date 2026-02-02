"""
SQLAlchemy models for PostgreSQL document metadata tracking.

This module handles raw document metadata storage in PostgreSQL.
The Knowledge Graph entities and relationships will be stored in Memgraph (M3+).
"""

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from config import DATABASE_URL, setup_logging

logger = setup_logging(__name__)

Base = declarative_base()


class FetchStatus(enum.Enum):
    """Status of document fetch operation."""

    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class RawDocument(Base):
    """
    Raw document metadata for tracking fetched content.

    This table stores metadata about fetched documents including their
    URLs, fetch status, content hashes, and file paths. The actual
    content is stored in the filesystem using content-addressable storage.
    """

    __tablename__ = "raw_documents"

    id = Column(Integer, primary_key=True)

    # URL information
    url = Column(String(2048), nullable=False)
    url_hash = Column(String(16), nullable=False, unique=True, index=True)
    normalized_url = Column(String(2048))
    domain = Column(String(255), index=True)
    source_type = Column(String(50), index=True)

    # Fetch metadata
    fetched_at = Column(DateTime)
    status = Column(Enum(FetchStatus), default=FetchStatus.PENDING, index=True)
    http_status_code = Column(Integer)
    error_message = Column(Text)

    # Content metadata
    content_hash = Column(String(64), index=True)
    content_type = Column(String(100))
    content_size = Column(Integer)
    file_path = Column(String(512))
    title = Column(Text)

    # SEC-specific fields
    sec_accession_number = Column(String(25), index=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<RawDocument(id={self.id}, url_hash={self.url_hash}, status={self.status})>"


# Engine and session factory
_engine = None
_session_factory = None


def get_engine(url: str = DATABASE_URL, echo: bool = False):
    """
    Get or create SQLAlchemy engine.

    Args:
        url: Database connection URL
        echo: Whether to echo SQL statements

    Returns:
        SQLAlchemy Engine instance
    """
    global _engine
    if _engine is None:
        _engine = create_engine(url, echo=echo)
        logger.info(f"Created database engine for {url.split('@')[-1]}")
    return _engine


def get_session(engine=None) -> Session:
    """
    Get a new database session.

    Args:
        engine: SQLAlchemy engine (uses default if None)

    Returns:
        SQLAlchemy Session instance
    """
    global _session_factory
    if engine is None:
        engine = get_engine()
    if _session_factory is None:
        _session_factory = sessionmaker(bind=engine)
    return _session_factory()


def create_tables(engine=None) -> None:
    """
    Create all database tables.

    Args:
        engine: SQLAlchemy engine (uses default if None)
    """
    if engine is None:
        engine = get_engine()
    Base.metadata.create_all(engine)
    logger.info("Created database tables")


def drop_tables(engine=None) -> None:
    """
    Drop all database tables.

    WARNING: This will delete all data.

    Args:
        engine: SQLAlchemy engine (uses default if None)
    """
    if engine is None:
        engine = get_engine()
    Base.metadata.drop_all(engine)
    logger.warning("Dropped all database tables")


def get_document_by_url_hash(session: Session, url_hash: str) -> Optional[RawDocument]:
    """
    Get a document by its URL hash.

    Args:
        session: Database session
        url_hash: URL hash to look up

    Returns:
        RawDocument or None if not found
    """
    return session.query(RawDocument).filter(RawDocument.url_hash == url_hash).first()


def get_document_by_content_hash(
    session: Session, content_hash: str
) -> Optional[RawDocument]:
    """
    Get the first document with a given content hash.

    Args:
        session: Database session
        content_hash: Content hash to look up

    Returns:
        RawDocument or None if not found
    """
    return (
        session.query(RawDocument)
        .filter(RawDocument.content_hash == content_hash)
        .first()
    )


def count_documents_by_status(session: Session) -> dict[FetchStatus, int]:
    """
    Count documents by fetch status.

    Args:
        session: Database session

    Returns:
        Dictionary mapping status to count
    """
    from sqlalchemy import func

    results = (
        session.query(RawDocument.status, func.count(RawDocument.id))
        .group_by(RawDocument.status)
        .all()
    )
    return {status: count for status, count in results}
