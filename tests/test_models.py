"""Tests for data models."""

import pytest
from pydantic import ValidationError

from oscapify.models import (
    DOIResponse,
    HeaderMapping,
    InputRecord,
    OutputRecord,
    ProcessingConfig,
)


class TestProcessingConfig:
    """Test ProcessingConfig model."""

    def test_valid_config(self):
        """Test creating valid configuration."""
        config = ProcessingConfig()

        assert config.suffix == "-oscapify"
        assert config.validate_headers is True
        assert config.cache_doi_lookups is True

    def test_custom_header_mapping(self):
        """Test custom header mapping."""
        mapping = HeaderMapping(
            pmid="PubMedID", sentence="text", preserve_fields=["custom1", "custom2"]
        )

        config = ProcessingConfig(header_mapping=mapping)

        assert config.header_mapping.pmid == "PubMedID"
        assert config.header_mapping.sentence == "text"
        assert "custom1" in config.header_mapping.preserve_fields


class TestInputRecord:
    """Test InputRecord model."""

    def test_valid_record(self):
        """Test creating valid input record."""
        record = InputRecord(pmid="12345678", pmcid="PMC1234567", sentence="Test sentence")

        assert record.pmid == "12345678"
        assert record.pmcid == "PMC1234567"
        assert record.sentence == "Test sentence"

    def test_clean_ids(self):
        """Test ID cleaning in validation."""
        record = InputRecord(pmid="  12345678  ", pmcid="nan", sentence="Test")

        assert record.pmid == "12345678"
        assert record.pmcid is None

    def test_extract_pmcid_from_url(self):
        """Test PMCID extraction method."""
        record = InputRecord(
            sentence="Test", pubmed_url="https://www.ncbi.nlm.nih.gov/pmc/articles/PMC7654321/"
        )

        assert record.extract_pmcid_from_url() == "PMC7654321"

    def test_extra_fields_allowed(self):
        """Test that extra fields are allowed."""
        record = InputRecord(sentence="Test", extra_field="value")

        assert record.sentence == "Test"


class TestOutputRecord:
    """Test OutputRecord model."""

    def test_valid_record(self):
        """Test creating valid output record."""
        record = OutputRecord(
            id="nlp-1-20240101",
            sentence="Test sentence",
            batch_name="test_batch",
            sentence_id="nlp-1-20240101",
        )

        assert record.id == "nlp-1-20240101"
        assert record.out_of_scope == "yes"
        assert record.doi == ""

    def test_with_doi(self):
        """Test record with DOI."""
        record = OutputRecord(
            id="nlp-1-20240101",
            sentence="Test",
            batch_name="test",
            sentence_id="nlp-1-20240101",
            doi="10.1234/test",
            out_of_scope="no",
        )

        assert record.doi == "10.1234/test"
        assert record.out_of_scope == "no"

    def test_no_extra_fields(self):
        """Test that extra fields are not allowed in base model."""
        with pytest.raises(ValidationError):
            OutputRecord(
                id="test",
                sentence="test",
                batch_name="test",
                sentence_id="test",
                extra_field="not_allowed",
            )


class TestDOIResponse:
    """Test DOIResponse model."""

    def test_from_api_response_success(self, mock_doi_response):
        """Test parsing successful API response."""
        response = DOIResponse.from_api_response(mock_doi_response)

        assert response.doi == "10.1234/test.doi.12345"
        assert response.pmid == "12345678"
        assert response.pmcid == "PMC1234567"
        assert response.errmsg is None

    def test_from_api_response_error(self):
        """Test parsing error API response."""
        error_response = {"errmsg": "Invalid ID"}

        response = DOIResponse.from_api_response(error_response)

        assert response.doi is None
        assert response.errmsg == "Invalid ID"

    def test_from_api_response_empty(self):
        """Test parsing empty API response."""
        empty_response = {"records": []}

        response = DOIResponse.from_api_response(empty_response)

        assert response.doi is None
        assert response.errmsg == "No records found"
