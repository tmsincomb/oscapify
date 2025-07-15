"""Tests for validators module."""

import pandas as pd

from oscapify.models import HeaderMapping
from oscapify.validators import DataCleaner, HeaderValidator


class TestHeaderValidator:
    """Test header validation functionality."""

    def test_validate_headers_success(self, sample_csv_data):
        """Test successful header validation."""
        validator = HeaderValidator(HeaderMapping())
        is_valid, corrections = validator.validate_headers(sample_csv_data)

        assert is_valid is True
        assert corrections is None

    def test_validate_headers_case_insensitive(self):
        """Test case-insensitive header matching."""
        df = pd.DataFrame({"PMID": [1, 2], "Sentence": ["test1", "test2"]})

        validator = HeaderValidator(HeaderMapping())
        is_valid, corrections = validator.validate_headers(df)

        assert is_valid is False
        assert corrections == {"PMID": "pmid", "Sentence": "sentence"}

    def test_validate_headers_missing(self):
        """Test missing required headers."""
        df = pd.DataFrame({"id": [1, 2], "text": ["test1", "test2"]})

        validator = HeaderValidator(HeaderMapping())
        is_valid, corrections = validator.validate_headers(df)

        assert is_valid is False

    def test_debug_headers(self, sample_csv_with_header_issues):
        """Test header debugging information."""
        validator = HeaderValidator(HeaderMapping())
        debug_info = validator.debug_headers(sample_csv_with_header_issues)

        assert "found_headers" in debug_info
        assert "header_stats" in debug_info
        assert debug_info["header_stats"]["whitespace_issues"] == ["  sentence  "]
        assert debug_info["header_stats"]["empty_headers"] == [""]

    def test_suggest_mapping(self):
        """Test header mapping suggestions."""
        headers = ["PMID", "text", "pubmed_link", "identifier"]
        validator = HeaderValidator(HeaderMapping())

        suggestions = validator.suggest_mapping(headers)

        assert suggestions["PMID"] == "pmid"
        assert suggestions["text"] == "sentence"
        assert suggestions["pubmed_link"] == "pubmed_url"
        assert suggestions["identifier"] == "ID"


class TestDataCleaner:
    """Test data cleaning functionality."""

    def test_clean_id_field(self):
        """Test ID field cleaning."""
        assert DataCleaner.clean_id_field("12345") == "12345"
        assert DataCleaner.clean_id_field("PMC12345") == "12345"
        assert DataCleaner.clean_id_field("PMID:12345") == "12345"
        assert DataCleaner.clean_id_field("  12345  ") == "12345"
        assert DataCleaner.clean_id_field("nan") is None
        assert DataCleaner.clean_id_field("") is None
        assert DataCleaner.clean_id_field(None) is None
        assert DataCleaner.clean_id_field(pd.NA) is None

    def test_extract_pmcid_from_url(self):
        """Test PMCID extraction from URLs."""
        url1 = "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC1234567/"
        assert DataCleaner.extract_pmcid_from_url(url1) == "PMC1234567"

        url2 = "https://pubmed.ncbi.nlm.nih.gov/pmc1234567/"
        assert DataCleaner.extract_pmcid_from_url(url2) == "PMC1234567"

        url3 = "https://pubmed.ncbi.nlm.nih.gov/12345678/"
        assert DataCleaner.extract_pmcid_from_url(url3) is None

        assert DataCleaner.extract_pmcid_from_url(None) is None
        assert DataCleaner.extract_pmcid_from_url("") is None

    def test_standardize_dataframe(self, sample_csv_data):
        """Test dataframe standardization."""
        # Add some issues to test
        df = sample_csv_data.copy()
        df.columns = [
            "  ID  ",
            "pmid",
            "pmcid",
            "sentence",
            "structure_1",
            "structure_2",
            "relation",
            "score",
            "pubmed_url",
        ]
        df.loc[0, "pmid"] = "PMID:12345678"
        df.loc[1, "pmcid"] = "PMC87654321"

        header_mapping = HeaderMapping()
        cleaned_df = DataCleaner.standardize_dataframe(df, header_mapping)

        # Check column names are stripped
        assert "ID" in cleaned_df.columns
        assert "  ID  " not in cleaned_df.columns

        # Check ID cleaning
        assert cleaned_df.loc[0, "pmid"] == "12345678"
        assert cleaned_df.loc[1, "pmcid"] == "87654321"

    def test_validate_real_csv_headers(self, real_csv_data):
        """Test validation with real CSV data from test files."""
        validator = HeaderValidator(HeaderMapping())
        is_valid, corrections = validator.validate_headers(real_csv_data)

        # Real test data should have valid headers (possibly with case differences)
        if not is_valid and corrections:
            # Apply corrections
            real_csv_data.rename(columns=corrections, inplace=True)
            is_valid_after, _ = validator.validate_headers(real_csv_data)
            assert is_valid_after is True
        else:
            assert is_valid is True
