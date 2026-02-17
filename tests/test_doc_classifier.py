"""
Tests for document type classifier (process/doc_classifier.py).

Covers:
- Invalid/edge-case inputs
- Promoted filings (misclassified sec_other → correct primary type)
- SEC-other subtypes via _get_sec_other_subtype()
"""

import pytest

from process.doc_classifier import DocumentClassifier, DocType


@pytest.fixture
def classifier():
    return DocumentClassifier()


# =========================================================================
# A. Invalid / edge-case inputs
# =========================================================================


class TestInvalidInputs:
    """Classifier should handle missing or empty inputs gracefully."""

    def test_all_none_inputs(self, classifier):
        result = classifier.classify(url=None, title=None, text=None, source_type=None)
        assert result.doc_type == DocType.UNKNOWN
        assert result.confidence == 0.0

    def test_empty_strings(self, classifier):
        result = classifier.classify(url="", title="", text="", source_type="")
        assert result.doc_type == DocType.UNKNOWN

    def test_none_text_with_valid_url(self, classifier):
        result = classifier.classify(
            url="https://www.sec.gov/Archives/edgar/data/1327811/filing.htm",
            title=None,
            text=None,
        )
        # Should at least classify as sec_other from the URL
        assert result.doc_type == DocType.SEC_OTHER

    def test_whitespace_only_text(self, classifier):
        result = classifier.classify(
            url=None,
            title=None,
            text="   \n\t  \n  ",
        )
        # Whitespace shouldn't trigger content patterns
        assert result.doc_type == DocType.UNKNOWN


# =========================================================================
# B. Promoted filings (fix misclassifications)
# =========================================================================


class TestPromotedFilings:
    """Documents with filing indicators in URL/content should promote out of sec_other."""

    def test_8k_url_d_prefix(self, classifier):
        """URL like d604263d8k.htm should classify as sec_8k."""
        result = classifier.classify(
            url="https://www.sec.gov/Archives/edgar/data/1327811/000119312515123456/d604263d8k.htm",
            source_type="sec_filing",
        )
        assert result.doc_type == DocType.SEC_8K

    def test_10q_url_x_prefix(self, classifier):
        """URL like wday-10312015x10q.htm should classify as sec_10q."""
        result = classifier.classify(
            url="https://www.sec.gov/Archives/edgar/data/1327811/000119312515123456/wday-10312015x10q.htm",
            source_type="sec_filing",
        )
        assert result.doc_type == DocType.SEC_10Q

    def test_10k_url_x_prefix(self, classifier):
        """URL like wday-01312020x10k.htm should classify as sec_10k."""
        result = classifier.classify(
            url="https://www.sec.gov/Archives/edgar/data/1327811/000119312520123456/wday-01312020x10k.htm",
            source_type="sec_filing",
        )
        assert result.doc_type == DocType.SEC_10K

    def test_8k_content_override(self, classifier):
        """Text containing 'FORM 8-K' with a generic EDGAR URL should classify as sec_8k."""
        result = classifier.classify(
            url="https://www.sec.gov/Archives/edgar/data/1327811/000119312515123456/filing.htm",
            text="UNITED STATES SECURITIES AND EXCHANGE COMMISSION\nFORM 8-K\nCURRENT REPORT",
            source_type="sec_filing",
        )
        assert result.doc_type == DocType.SEC_8K


# =========================================================================
# C. SEC-other subtypes (_get_sec_other_subtype)
# =========================================================================


class TestSecOtherSubtypes:
    """Documents that remain sec_other should get a meaningful sub_type."""

    def test_subtype_index_page(self, classifier):
        """URL ending in -index.htm → subtype 'index_page'."""
        result = classifier.classify(
            url="https://www.sec.gov/Archives/edgar/data/1327811/000119312515123456/0001193125-15-123456-index.htm",
            source_type="sec_filing",
        )
        assert result.doc_type == DocType.SEC_OTHER
        assert result.sub_type == "index_page"

    def test_subtype_exhibit_certification(self, classifier):
        """URL with ex311 → subtype 'exhibit_certification'."""
        result = classifier.classify(
            url="https://www.sec.gov/Archives/edgar/data/1327811/000119312515123456/d604263dex311.htm",
            source_type="sec_filing",
        )
        assert result.doc_type == DocType.SEC_OTHER
        assert result.sub_type == "exhibit_certification"

    def test_subtype_exhibit_press_release(self, classifier):
        """URL with ex991 → subtype 'exhibit_press_release'."""
        result = classifier.classify(
            url="https://www.sec.gov/Archives/edgar/data/1327811/000119312515123456/d604263dex991.htm",
            source_type="sec_filing",
        )
        assert result.doc_type == DocType.SEC_OTHER
        assert result.sub_type == "exhibit_press_release"

    def test_subtype_exhibit_agreement(self, classifier):
        """URL with ex101 → subtype 'exhibit_agreement'."""
        result = classifier.classify(
            url="https://www.sec.gov/Archives/edgar/data/1327811/000119312515123456/d604263dex101.htm",
            source_type="sec_filing",
        )
        assert result.doc_type == DocType.SEC_OTHER
        assert result.sub_type == "exhibit_agreement"

    def test_subtype_exhibit_consent(self, classifier):
        """URL with ex231 → subtype 'exhibit_consent'."""
        result = classifier.classify(
            url="https://www.sec.gov/Archives/edgar/data/1327811/000119312515123456/d604263dex231.htm",
            source_type="sec_filing",
        )
        assert result.doc_type == DocType.SEC_OTHER
        assert result.sub_type == "exhibit_consent"

    def test_subtype_exhibit_subsidiaries(self, classifier):
        """URL with ex211 → subtype 'exhibit_subsidiaries'."""
        result = classifier.classify(
            url="https://www.sec.gov/Archives/edgar/data/1327811/000119312515123456/d604263dex211.htm",
            source_type="sec_filing",
        )
        assert result.doc_type == DocType.SEC_OTHER
        assert result.sub_type == "exhibit_subsidiaries"

    def test_subtype_exhibit_other(self, classifier):
        """URL with ex41 (not a known category) → subtype 'exhibit_other'."""
        result = classifier.classify(
            url="https://www.sec.gov/Archives/edgar/data/1327811/000119312515123456/d604263dex41.htm",
            source_type="sec_filing",
        )
        assert result.doc_type == DocType.SEC_OTHER
        assert result.sub_type == "exhibit_other"

    def test_subtype_content_fallback_sox(self, classifier):
        """No exhibit URL, content has 'certif' + 'sarbanes' → 'exhibit_certification'."""
        result = classifier.classify(
            url="https://www.sec.gov/Archives/edgar/data/1327811/000119312515123456/generic.htm",
            text="I certify pursuant to the Sarbanes-Oxley Act of 2002 that the report...",
            source_type="sec_filing",
        )
        assert result.doc_type == DocType.SEC_OTHER
        assert result.sub_type == "exhibit_certification"

    def test_subtype_content_fallback_press(self, classifier):
        """Content has 'forward-looking statements' → 'exhibit_press_release'."""
        result = classifier.classify(
            url="https://www.sec.gov/Archives/edgar/data/1327811/000119312515123456/generic.htm",
            text="This report contains forward-looking statements regarding future results...",
            source_type="sec_filing",
        )
        assert result.doc_type == DocType.SEC_OTHER
        assert result.sub_type == "exhibit_press_release"

    def test_subtype_default_filing_document(self, classifier):
        """No exhibit or content signals → subtype 'filing_document'."""
        result = classifier.classify(
            url="https://www.sec.gov/Archives/edgar/data/1327811/000119312515123456/filing.htm",
            text="Some generic SEC document content here.",
            source_type="sec_filing",
        )
        assert result.doc_type == DocType.SEC_OTHER
        assert result.sub_type == "filing_document"


# =========================================================================
# D. Exhibit promotion guard
# =========================================================================


class TestExhibitPromotionGuard:
    """Exhibits with filing-type content must NOT be promoted out of sec_other."""

    def test_sox_cert_with_10k_content_stays_sec_other(self, classifier):
        """EX-31.1 (SOX cert) references 'Form 10-K' but should stay sec_other."""
        result = classifier.classify(
            url="https://www.sec.gov/Archives/edgar/data/1327811/000132781123000024/wday-01312023xex311.htm",
            text="Exhibit 31.1\nI have reviewed this Annual Report on Form 10-K of Workday, Inc.",
            source_type="sec_filing",
        )
        assert result.doc_type == DocType.SEC_OTHER
        assert result.sub_type == "exhibit_certification"

    def test_press_release_x991_with_10k_content_stays_sec_other(self, classifier):
        """EX-99.1 press release references 'Form 10-K' but should stay sec_other."""
        result = classifier.classify(
            url="https://www.sec.gov/Archives/edgar/data/1327811/000132781120000021/wday-4302020x991.htm",
            text="This press release... FORM 10-K For the fiscal year ended January 31, 2020",
            source_type="sec_filing",
        )
        assert result.doc_type == DocType.SEC_OTHER

    def test_real_10k_still_promoted(self, classifier):
        """Actual 10-K filing URL should still be promoted correctly."""
        result = classifier.classify(
            url="https://www.sec.gov/Archives/edgar/data/1327811/000132781123000024/wday-01312023x10k.htm",
            text="FORM 10-K ANNUAL REPORT For the fiscal year ended January 31, 2023",
            source_type="sec_filing",
        )
        assert result.doc_type == DocType.SEC_10K

    def test_index_page_with_filing_content_stays_sec_other(self, classifier):
        """EDGAR index page with filing content should stay sec_other."""
        result = classifier.classify(
            url="https://www.sec.gov/Archives/edgar/data/1327811/000132781123000024/0001327811-23-000024-index.htm",
            text="FORM 10-K Annual Report filing index",
            source_type="sec_filing",
        )
        assert result.doc_type == DocType.SEC_OTHER
        assert result.sub_type == "index_page"
