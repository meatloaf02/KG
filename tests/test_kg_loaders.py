"""
Tests for the Knowledge Graph loaders module.

These tests verify the idempotent MERGE operations work correctly.
Requires a running Memgraph instance for integration tests.
"""

import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch

from kg.loaders import KGLoader, LoadResult, BatchLoadResult
from kg.schema import (
    DocumentNode,
    CapabilityNode,
    ProductNode,
    RiskTopicNode,
    EventNode,
    Evidence,
)


# =============================================================================
# Unit Tests (No Database Required)
# =============================================================================


class TestLoadResult:
    """Test LoadResult data class."""

    def test_ok_result(self):
        result = LoadResult.ok("test-id", created=True)
        assert result.success is True
        assert result.node_id == "test-id"
        assert result.created is True
        assert result.error is None

    def test_fail_result(self):
        result = LoadResult.fail("Something went wrong")
        assert result.success is False
        assert result.node_id is None
        assert result.error == "Something went wrong"


class TestBatchLoadResult:
    """Test BatchLoadResult data class."""

    def test_success_rate_calculation(self):
        result = BatchLoadResult(
            total=100,
            loaded=95,
            created=50,
            failed=5,
            errors=["error1", "error2"],
        )
        assert result.success_rate == 95.0

    def test_success_rate_empty(self):
        result = BatchLoadResult(
            total=0,
            loaded=0,
            created=0,
            failed=0,
            errors=[],
        )
        assert result.success_rate == 0.0


class TestEvidence:
    """Test Evidence data class."""

    def test_to_dict(self):
        evidence = Evidence(
            text="AI-powered features",
            sentence_id="s-001",
            start_char=10,
            end_char=30,
            confidence=0.95,
        )
        d = evidence.to_dict()
        assert d["evidence_text"] == "AI-powered features"
        assert d["sentence_id"] == "s-001"
        assert d["start_char"] == 10
        assert d["end_char"] == 30
        assert d["confidence"] == 0.95
        assert "extracted_at" in d


class TestDocumentNode:
    """Test DocumentNode data class."""

    def test_to_dict(self):
        doc = DocumentNode(
            content_hash="abc123",
            url_hash="def456",
            title="Test Document",
            doc_type="10-K",
            source_type="sec_filing",
            publish_date="2024-01-15",
            source_url="https://example.com/doc",
        )
        d = doc.to_dict()
        assert d["content_hash"] == "abc123"
        assert d["url_hash"] == "def456"
        assert d["title"] == "Test Document"
        assert d["doc_type"] == "10-K"
        assert d["source_type"] == "sec_filing"


class TestKGLoaderUnit:
    """Unit tests for KGLoader (mocked database)."""

    def test_build_evidence_params_from_evidence(self):
        loader = KGLoader(driver=MagicMock())
        evidence = Evidence(
            text="test text",
            sentence_id="s-001",
            start_char=0,
            end_char=10,
            confidence=0.9,
        )
        params = loader._build_evidence_params(evidence)
        assert params["evidence_text"] == "test text"
        assert params["confidence"] == 0.9

    def test_build_evidence_params_from_dict(self):
        loader = KGLoader(driver=MagicMock())
        evidence = {
            "text": "test text",
            "sentence_id": "s-001",
            "start_char": 0,
            "end_char": 10,
            "confidence": 0.85,
        }
        params = loader._build_evidence_params(evidence)
        assert params["evidence_text"] == "test text"
        assert params["confidence"] == 0.85

    def test_build_evidence_params_none(self):
        loader = KGLoader(driver=MagicMock())
        params = loader._build_evidence_params(None)
        assert params["evidence_text"] is None
        assert params["confidence"] == 1.0
        assert params["extracted_at"] is not None

    def test_context_manager(self):
        mock_driver = MagicMock()
        with KGLoader(driver=mock_driver) as loader:
            assert loader.driver == mock_driver
        # Driver should be closed after context exit (if owned)

    def test_load_document_missing_content_hash(self):
        loader = KGLoader(driver=MagicMock())
        result = loader.load_document({"title": "No Hash"})
        assert result.success is False
        assert "content_hash is required" in result.error


# =============================================================================
# Integration Tests (Requires Running Memgraph)
# =============================================================================


@pytest.fixture
def memgraph_driver():
    """Get a Memgraph driver for integration tests."""
    try:
        from kg.connection import get_driver, check_connection
        driver = get_driver()
        if not check_connection(driver):
            pytest.skip("Memgraph not available")
        return driver
    except Exception as e:
        pytest.skip(f"Memgraph not available: {e}")


@pytest.fixture
def loader(memgraph_driver):
    """Get a KGLoader with Memgraph connection."""
    return KGLoader(driver=memgraph_driver)


@pytest.fixture
def clean_test_data(memgraph_driver):
    """Clean up test data before and after tests."""
    from kg.connection import execute_write

    # Clean up test nodes before test
    cleanup_query = """
    MATCH (n)
    WHERE n.content_hash STARTS WITH 'test-'
       OR n.id STARTS WITH 'test-'
    DETACH DELETE n
    """
    try:
        execute_write(cleanup_query, driver=memgraph_driver)
    except Exception:
        pass  # Ignore cleanup errors

    yield

    # Clean up after test
    try:
        execute_write(cleanup_query, driver=memgraph_driver)
    except Exception:
        pass


class TestKGLoaderIntegration:
    """Integration tests for KGLoader (requires Memgraph)."""

    def test_load_document(self, loader, clean_test_data):
        """Test loading a document."""
        doc = DocumentNode(
            content_hash="test-doc-001",
            url_hash="test-url-001",
            title="Integration Test Document",
            doc_type="10-K",
            source_type="sec_filing",
        )

        # First load should succeed
        result = loader.load_document(doc)
        assert result.success is True
        assert result.node_id == "test-doc-001"

        # Second load should also succeed (idempotent)
        result2 = loader.load_document(doc)
        assert result2.success is True

    def test_load_capability(self, loader, clean_test_data):
        """Test loading a capability."""
        cap = CapabilityNode(
            id="test-cap-001",
            name="Test AI Capability",
            normalized_name="test ai capability",
            category="artificial_intelligence",
        )

        result = loader.load_capability(cap)
        assert result.success is True
        assert result.node_id == "test-cap-001"

    def test_load_product(self, loader, clean_test_data):
        """Test loading a product."""
        product = ProductNode(
            id="test-product-001",
            name="Test Product",
            normalized_name="test product",
            description="A test product",
        )

        result = loader.load_product(product)
        assert result.success is True
        assert result.node_id == "test-product-001"

    def test_load_mention_with_evidence(self, loader, clean_test_data):
        """Test creating a MENTIONS relationship with evidence."""
        # First create the document and capability
        doc = DocumentNode(
            content_hash="test-doc-mention",
            url_hash="test-url-mention",
            title="Test Mention Document",
            doc_type="10-K",
            source_type="sec_filing",
        )
        cap = CapabilityNode(
            id="test-cap-mention",
            name="Test Capability",
            normalized_name="test capability",
            category="artificial_intelligence",
        )

        loader.load_document(doc)
        loader.load_capability(cap)

        # Create mention with evidence
        evidence = Evidence(
            text="Our AI-powered platform",
            sentence_id="s-001",
            start_char=0,
            end_char=24,
            confidence=0.95,
        )

        result = loader.load_mention_capability(
            doc_hash="test-doc-mention",
            capability_id="test-cap-mention",
            evidence=evidence,
        )
        assert result.success is True

    def test_idempotent_batch_load(self, loader, clean_test_data):
        """Test that batch loading is idempotent."""
        documents = [
            DocumentNode(
                content_hash=f"test-batch-{i}",
                url_hash=f"test-batch-url-{i}",
                title=f"Batch Document {i}",
                doc_type="10-K",
                source_type="sec_filing",
            )
            for i in range(5)
        ]

        # First batch load
        result1 = loader.load_documents_batch(documents, batch_size=2)
        assert result1.loaded == 5
        assert result1.failed == 0

        # Second batch load (should still succeed, no duplicates)
        result2 = loader.load_documents_batch(documents, batch_size=2)
        assert result2.loaded == 5
        assert result2.failed == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
