"""Tests for core processing functionality."""

from pathlib import Path
from unittest.mock import Mock, patch

import pandas as pd
import pytest

from oscapify.core import OscapifyProcessor
from oscapify.exceptions import FileProcessingError, HeaderValidationError
from oscapify.models import ProcessingConfig


class TestOscapifyProcessor:
    """Test OscapifyProcessor class."""

    @pytest.fixture()
    def processor(self):
        """Create processor instance."""
        config = ProcessingConfig(cache_doi_lookups=False)  # Disable caching for tests
        return OscapifyProcessor(config)

    def test_collect_csv_files(self, processor, temp_dir):
        """Test CSV file collection."""
        # Create test files
        (temp_dir / "file1.csv").touch()
        (temp_dir / "file2.csv").touch()
        (temp_dir / "file3.txt").touch()
        subdir = temp_dir / "subdir"
        subdir.mkdir()
        (subdir / "file4.csv").touch()

        # Test file collection
        files = processor._collect_csv_files([str(temp_dir)])

        assert len(files) == 2  # Only top-level CSV files
        assert all(f.suffix == ".csv" for f in files)

    def test_collect_csv_files_mixed_inputs(self, processor, temp_dir):
        """Test collecting files from mixed inputs."""
        file1 = temp_dir / "file1.csv"
        file1.touch()

        dir1 = temp_dir / "dir1"
        dir1.mkdir()
        (dir1 / "file2.csv").touch()

        files = processor._collect_csv_files([str(file1), str(dir1)])

        assert len(files) == 2

    def test_read_csv_safely(self, processor, temp_dir, sample_csv_data):
        """Test safe CSV reading with encoding detection."""
        csv_file = temp_dir / "test.csv"
        sample_csv_data.to_csv(csv_file, index=False)

        df = processor._read_csv_safely(csv_file)

        assert len(df) == len(sample_csv_data)
        assert list(df.columns) == list(sample_csv_data.columns)

    def test_read_csv_safely_empty_file(self, processor, temp_dir):
        """Test reading empty CSV file."""
        csv_file = temp_dir / "empty.csv"
        csv_file.touch()

        with pytest.raises(FileProcessingError) as exc_info:
            processor._read_csv_safely(csv_file)

        assert "Empty CSV file" in str(exc_info.value)

    def test_validate_and_fix_headers(self, processor, sample_csv_with_header_issues):
        """Test header validation and fixing."""
        # Should fix case issues
        fixed_df = processor._validate_and_fix_headers(
            sample_csv_with_header_issues, Path("test.csv")
        )

        assert "pmid" in fixed_df.columns
        assert "PMID" not in fixed_df.columns

    def test_validate_and_fix_headers_fail(self, processor):
        """Test header validation failure."""
        df = pd.DataFrame({"wrong_column": [1, 2]})

        with pytest.raises(HeaderValidationError):
            processor._validate_and_fix_headers(df, Path("test.csv"))

    @patch("requests.get")
    def test_get_doi_from_api(self, mock_get, processor, mock_doi_response):
        """Test DOI retrieval from API."""
        mock_response = Mock()
        mock_response.json.return_value = mock_doi_response
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = processor._get_doi_from_api("12345678")

        assert result.doi == "10.1234/test.doi.12345"
        assert result.pmid == "12345678"
        mock_get.assert_called_once()

    def test_process_dataframe(self, processor, sample_csv_data):
        """Test dataframe processing."""
        with patch.object(processor, "_get_doi_cached") as mock_doi:
            # Mock DOI responses
            mock_doi.return_value = Mock(doi="10.1234/test", pmid="12345678", pmcid="PMC1234567")

            result_df = processor._process_dataframe(sample_csv_data)

            # Check basic structure
            assert len(result_df) == len(sample_csv_data)
            assert "id" in result_df.columns
            assert "doi" in result_df.columns
            assert "out_of_scope" in result_df.columns

            # Check ID format
            assert all(result_df["id"].str.startswith("nlp-"))

            # Check DOI was retrieved
            assert result_df.iloc[0]["doi"] == "10.1234/test"
            assert result_df.iloc[0]["out_of_scope"] == "no"

    def test_save_output(self, processor, test_output_dir, sample_csv_data):
        """Test saving output file."""
        output_file = test_output_dir / "test_output.csv"

        processor._save_output(sample_csv_data, output_file)

        assert output_file.exists()
        loaded_df = pd.read_csv(output_file)
        assert len(loaded_df) == len(sample_csv_data)

    def test_process_files_integration(self, processor, sample_input_csv_path, test_output_dir):
        """Test full file processing integration with real test data."""
        # Read the actual data to get expected record count
        df = pd.read_csv(sample_input_csv_path)

        # Mock DOI retrieval
        with patch.object(processor, "_get_doi_cached") as mock_doi:
            mock_doi.return_value = None  # No DOI found

            # Process files
            processor.config.output_dir = str(test_output_dir)
            stats = processor.process_files([str(sample_input_csv_path)])

            # Check stats
            assert stats.total_files == 1
            assert stats.processed_files == 1
            assert stats.failed_files == 0
            assert stats.total_records == len(df)

            # Check output file exists
            output_files = list(Path(processor.config.output_dir).glob("*.csv"))
            assert len(output_files) >= 1  # At least one output file

    def test_process_all_input_files(self, processor, test_input_csv_files, test_output_dir):
        """Test processing all CSV files from input directory."""
        # Mock DOI retrieval to avoid API calls
        with patch.object(processor, "_get_doi_cached") as mock_doi:
            mock_doi.return_value = None

            # Process all test input files
            processor.config.output_dir = str(test_output_dir)
            input_paths = [str(f) for f in test_input_csv_files]
            stats = processor.process_files(input_paths)

            # Check stats
            assert stats.total_files == len(test_input_csv_files)
            assert stats.processed_files == len(test_input_csv_files)
            assert stats.failed_files == 0

            # Check output files
            output_files = list(test_output_dir.glob("*.csv"))
            assert len(output_files) >= len(test_input_csv_files)

    def test_read_real_csv_data(self, processor, sample_input_csv_path):
        """Test reading real CSV data from test files."""
        df = processor._read_csv_safely(sample_input_csv_path)

        # Check expected columns exist (ID is optional in some files)
        required_columns = ["pmid", "sentence", "structure_1", "structure_2", "relation", "score"]
        for col in required_columns:
            assert col in df.columns or col.lower() in df.columns

        # Check data is not empty
        assert len(df) > 0
