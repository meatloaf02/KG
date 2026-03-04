"""
SQLAlchemy model for external media document manifest.

Tracks metadata for crawled external media articles (CNBC, Forbes, VentureBeat, etc.)
separate from the existing RawDocument table used for SEC filings.
"""

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from ingest.models import Base, get_engine, get_session


class DocumentManifest(Base):
    """
    Metadata manifest for crawled external media articles.

    Upsert key: content_hash (UNIQUE). Stores one row per unique article.
    Actual article text blobs live in data/interim/{hash[:2]}/{hash}.json.
    """

    __tablename__ = "document_manifest"

    id = Column(Integer, primary_key=True)
    content_hash = Column(String(64), unique=True, nullable=False, index=True)
    url = Column(String(2048), nullable=False)
    canonical_url = Column(String(2048))
    url_hash = Column(String(64), index=True)
    source_type = Column(String(50), index=True)  # always "external_media"
    publisher = Column(String(255))
    domain = Column(String(255), index=True)
    tier = Column(String(10))  # "tier1" or "tier2"
    title = Column(Text)
    author = Column(Text)
    publish_date = Column(Date)
    publish_date_confidence = Column(String(20))  # "high", "medium", "low"
    fetched_at = Column(DateTime)
    http_status = Column(Integer)
    mime = Column(String(50))
    size_bytes = Column(Integer)
    language = Column(String(10))
    is_paywalled = Column(Boolean, default=False)
    workday_match_type = Column(String(50))  # "primary" | "disambiguation"
    ai_keyword_hit = Column(Boolean)
    near_dup_cluster_id = Column(String(64))
    dup_of_hash = Column(String(64))
    parser_version = Column(String(20))

    def __repr__(self) -> str:
        return f"<DocumentManifest(content_hash={self.content_hash!r}, domain={self.domain!r})>"


def create_manifest_table(engine=None) -> None:
    """Create document_manifest table if it doesn't exist."""
    if engine is None:
        engine = get_engine()
    DocumentManifest.__table__.create(engine, checkfirst=True)


def upsert_manifest(session: Session, doc: DocumentManifest) -> None:
    """
    Insert or update a DocumentManifest row.

    Conflict target: content_hash. On conflict, updates all mutable fields.
    """
    values = {
        col.key: getattr(doc, col.key)
        for col in DocumentManifest.__table__.columns
        if col.key != "id"
    }

    stmt = (
        insert(DocumentManifest.__table__)
        .values(**values)
        .on_conflict_do_update(
            index_elements=["content_hash"],
            set_={
                k: v
                for k, v in values.items()
                if k != "content_hash"
            },
        )
    )
    session.execute(stmt)
    session.commit()
