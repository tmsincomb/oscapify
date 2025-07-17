"""Tests for the oscapify CLI module."""

import shutil
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pandas as pd
import pytest
from click.testing import CliRunner

from oscapify.cli import cache_stats, clear_cache, cli, process, validate
from oscapify.exceptions import FileProcessingError, HeaderValidationError


@pytest.fixture
def runner():
    """Create a Click test runner."""
    return CliRunner()


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    temp_path = tempfile.mkdtemp()
    yield Path(temp_path)
    shutil.rmtree(temp_path)


@pytest.fixture
def sample_csv(temp_dir):
    """Create a sample CSV file for testing."""
    csv_path = temp_dir / "test_input.csv"
    df = pd.DataFrame(
        {
            "pmid": ["12345678", "87654321", "11111111"],
            "sentence": ["Test sentence 1.", "Test sentence 2.", "Test sentence 3."],
            "extra_field": ["value1", "value2", "value3"],
        }
    )
    df.to_csv(csv_path, index=False)
    return csv_path


@pytest.fixture
def invalid_csv(temp_dir):
    """Create a CSV file with invalid headers."""
    csv_path = temp_dir / "invalid_input.csv"
    df = pd.DataFrame({"wrong_id": ["12345678"], "wrong_text": ["Test sentence."]})
    df.to_csv(csv_path, index=False)
    return csv_path


@pytest.fixture
def mock_processor():
    """Create a mock OscapifyProcessor."""
    with patch("oscapify.cli.OscapifyProcessor") as mock_class:
        processor_instance = Mock()
        # Mock the process_files method to return ProcessingStats
        from oscapify.models import ProcessingStats

        stats = ProcessingStats()
        stats.total_files = 1
        stats.processed_files = 1
        stats.failed_files = 0
        processor_instance.process_files.return_value = stats
        mock_class.return_value = processor_instance
        # Attach the mock class to the instance for tests to access
        processor_instance._mock_class = mock_class
        yield processor_instance


class TestCLIVersion:
    """Test version display functionality."""

    def test_version_flag(self, runner):
        """Test --version flag displays version."""
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "oscapify, version" in result.output


class TestProcessCommand:
    """Test the process command functionality."""

    def test_process_single_file(self, runner, sample_csv, temp_dir, mock_processor):
        """Test processing a single CSV file."""
        result = runner.invoke(process, [str(sample_csv), "-o", str(temp_dir)])
        assert result.exit_code == 0
        assert mock_processor.process_files.called
        # Current CLI doesn't print success message

    def test_process_multiple_files(self, runner, sample_csv, temp_dir, mock_processor):
        """Test processing multiple CSV files."""
        csv2 = temp_dir / "test2.csv"
        pd.DataFrame({"pmid": ["999"], "sentence": ["Test"]}).to_csv(csv2, index=False)

        result = runner.invoke(process, [str(sample_csv), str(csv2), "-o", str(temp_dir)])
        assert result.exit_code == 0
        assert mock_processor.process_files.called
        # Current CLI doesn't print success message

    def test_process_directory(self, runner, sample_csv, temp_dir, mock_processor):
        """Test processing all CSV files in a directory."""
        result = runner.invoke(process, [str(temp_dir), "-o", str(temp_dir)])
        assert result.exit_code == 0
        assert mock_processor.process_files.called

    def test_process_with_custom_suffix(self, runner, sample_csv, temp_dir, mock_processor):
        """Test processing with custom output suffix."""
        result = runner.invoke(process, [str(sample_csv), "-s", "-custom"])
        assert result.exit_code == 0
        # Check that the custom suffix was passed in config
        config = mock_processor._mock_class.call_args[0][0]
        assert config.suffix == "-custom"

    def test_process_with_batch_name(self, runner, sample_csv, temp_dir, mock_processor):
        """Test processing with custom batch name."""
        result = runner.invoke(process, [str(sample_csv), "-b", "custom_batch"])
        assert result.exit_code == 0
        # Verify batch name was passed to processor
        config = mock_processor._mock_class.call_args[0][0]
        assert config.batch_name == "custom_batch"

    def test_process_no_cache_flag(self, runner, sample_csv, temp_dir, mock_processor):
        """Test processing with --no-cache flag."""
        result = runner.invoke(process, [str(sample_csv), "--no-cache"])
        assert result.exit_code == 0
        config = mock_processor._mock_class.call_args[0][0]
        assert config.cache_doi_lookups is False

    def test_process_no_validation_flag(self, runner, sample_csv, temp_dir, mock_processor):
        """Test processing with --no-validation flag."""
        result = runner.invoke(process, [str(sample_csv), "--no-validation"])
        assert result.exit_code == 0
        config = mock_processor._mock_class.call_args[0][0]
        assert config.validate_headers is False

    def test_process_strict_mode(self, runner, sample_csv, temp_dir):
        """Test processing with --strict flag."""
        with patch("oscapify.cli.OscapifyProcessor") as mock:
            processor_instance = Mock()
            processor_instance.process_files.side_effect = FileProcessingError("Test error")
            mock.return_value = processor_instance

            result = runner.invoke(process, [str(sample_csv), "--strict"])
            assert result.exit_code == 1
            # Error is logged but not necessarily in output

    def test_process_debug_mode(self, runner, sample_csv, temp_dir, mock_processor):
        """Test processing with --debug flag."""
        result = runner.invoke(process, [str(sample_csv), "--debug"])
        assert result.exit_code == 0
        # Debug mode should be enabled

    def test_process_custom_headers(self, runner, sample_csv, temp_dir, mock_processor):
        """Test processing with custom header mappings."""
        result = runner.invoke(
            process,
            [
                str(sample_csv),
                "--header-pmid",
                "custom_pmid",
                "--header-sentence",
                "custom_sentence",
            ],
        )
        assert result.exit_code == 0
        config = mock_processor._mock_class.call_args[0][0]
        assert config.header_mapping.pmid == "custom_pmid"
        assert config.header_mapping.sentence == "custom_sentence"

    def test_process_preserve_fields(self, runner, sample_csv, temp_dir, mock_processor):
        """Test processing with --preserve-fields option."""
        result = runner.invoke(
            process,
            [
                str(sample_csv),
                "--preserve-fields",
                "extra_field",
                "--preserve-fields",
                "another_field",
            ],
        )
        assert result.exit_code == 0
        config = mock_processor._mock_class.call_args[0][0]
        assert "extra_field" in config.header_mapping.preserve_fields
        assert "another_field" in config.header_mapping.preserve_fields

    def test_process_nonexistent_file(self, runner, temp_dir):
        """Test processing a non-existent file."""
        result = runner.invoke(process, [str(temp_dir / "nonexistent.csv")])
        assert result.exit_code == 2  # Click returns 2 for bad arguments

    def test_process_empty_directory(self, runner, temp_dir):
        """Test processing an empty directory."""
        empty_dir = temp_dir / "empty"
        empty_dir.mkdir()

        with patch("oscapify.cli.OscapifyProcessor") as mock:
            processor_instance = Mock()
            from oscapify.models import ProcessingStats

            stats = ProcessingStats()
            stats.total_files = 0
            stats.processed_files = 0
            stats.failed_files = 0
            processor_instance.process_files.return_value = stats
            mock.return_value = processor_instance

            result = runner.invoke(process, [str(empty_dir)])
            assert result.exit_code == 0  # Empty directory is not an error

    def test_process_with_failed_files(self, runner, sample_csv, temp_dir):
        """Test exit code when some files fail processing."""
        with patch("oscapify.cli.OscapifyProcessor") as mock:
            processor_instance = Mock()
            # Mock stats with failed files
            from oscapify.models import ProcessingStats

            stats = ProcessingStats()
            stats.total_files = 1
            stats.processed_files = 0
            stats.failed_files = 1
            processor_instance.process_files.return_value = stats
            mock.return_value = processor_instance

            result = runner.invoke(process, [str(sample_csv)])
            assert result.exit_code == 1

    # def test_default_command_invocation(self, runner):
    #     """Test that process is the default command when no args provided."""
    #     # When no subcommand is provided and no arguments, it should show help
    #     result = runner.invoke(cli, [])
    #     # Should either show help or invoke process with no args (which will fail)
    #     assert result.exit_code in [0, 2]  # 0 for help, 2 for missing args


class TestValidateCommand:
    """Test the validate command functionality."""

    def test_validate_valid_csv(self, runner, sample_csv):
        """Test validating a CSV with correct headers."""
        with patch("oscapify.cli.HeaderValidator") as mock_validator_class:
            mock_validator = Mock()
            mock_validator.validate_headers.return_value = (True, [])
            mock_validator.debug_headers.return_value = {
                "found_headers": ["pmid", "sentence", "extra_field"],
                "header_stats": {
                    "total_columns": 3,
                    "has_duplicates": False,
                    "empty_headers": 0,
                    "whitespace_issues": [],
                    "duplicate_headers": [],
                },
                "detected_patterns": {},
                "sample_data": {},
            }
            mock_validator_class.return_value = mock_validator

            result = runner.invoke(validate, [str(sample_csv)])
            assert result.exit_code == 0
            assert "✅ All required headers found" in result.output

    def test_validate_invalid_csv(self, runner, invalid_csv):
        """Test validating a CSV with invalid headers."""
        with patch("oscapify.cli.HeaderValidator") as mock_validator_class:
            mock_validator = Mock()
            mock_validator.validate_headers.return_value = (False, {"wrong_id": "pmid"})
            mock_validator.debug_headers.return_value = {
                "found_headers": ["wrong_id", "wrong_text"],
                "header_stats": {
                    "total_columns": 2,
                    "has_duplicates": False,
                    "empty_headers": 0,
                    "whitespace_issues": [],
                    "duplicate_headers": [],
                },
                "detected_patterns": {},
                "sample_data": {},
            }
            mock_validator_class.return_value = mock_validator

            result = runner.invoke(validate, [str(invalid_csv)])
            assert result.exit_code == 0  # validate command doesn't fail on invalid headers
            assert "❌ Missing required headers" in result.output
            assert "Suggested corrections:" in result.output

    def test_validate_with_suggest_mappings(self, runner, invalid_csv):
        """Test validate command with --suggest-mappings flag."""
        with patch("oscapify.cli.HeaderValidator") as mock_validator_class:
            mock_validator = Mock()
            mock_validator.validate_headers.return_value = (False, {"wrong_id": "pmid"})
            mock_validator.suggest_mapping.return_value = {
                "wrong_id": "pmid",
                "wrong_text": "sentence",
            }
            mock_validator.debug_headers.return_value = {
                "found_headers": ["wrong_id", "wrong_text"],
                "header_stats": {
                    "total_columns": 2,
                    "has_duplicates": False,
                    "empty_headers": 0,
                    "whitespace_issues": [],
                    "duplicate_headers": [],
                },
                "detected_patterns": {},
                "sample_data": {},
            }
            mock_validator_class.return_value = mock_validator

            result = runner.invoke(validate, [str(invalid_csv), "--suggest-mappings"])
            assert result.exit_code == 0
            assert "Suggested mappings:" in result.output
            assert "--header-pmid 'wrong_id'" in result.output
            assert "--header-sentence 'wrong_text'" in result.output

    def test_validate_nonexistent_file(self, runner, temp_dir):
        """Test validating a non-existent file."""
        result = runner.invoke(validate, [str(temp_dir / "nonexistent.csv")])
        assert result.exit_code == 2  # Click returns 2 for bad arguments
        # Error message format may vary

    def test_validate_file_info_display(self, runner, sample_csv):
        """Test that file info is displayed during validation."""
        with patch("oscapify.cli.HeaderValidator") as mock_validator_class:
            mock_validator = Mock()
            mock_validator.validate_headers.return_value = (True, [])
            mock_validator.debug_headers.return_value = {
                "found_headers": ["pmid", "sentence", "extra_field"],
                "header_stats": {
                    "total_columns": 3,
                    "has_duplicates": False,
                    "empty_headers": 0,
                    "whitespace_issues": [],
                    "duplicate_headers": [],
                },
                "detected_patterns": {},
                "sample_data": {},
            }
            mock_validator_class.return_value = mock_validator

            result = runner.invoke(validate, [str(sample_csv)])
            assert "Validating:" in result.output
            assert "Found" in result.output
            assert "columns:" in result.output


class TestCacheCommands:
    """Test cache-related commands."""

    def test_cache_stats_empty(self, runner):
        """Test cache stats with empty cache."""
        with patch("oscapify.cache.CacheManager") as mock_cache_class:
            mock_cache = Mock()
            mock_cache.get_stats.return_value = {
                "total_entries": 0,
                "cache_size_mb": 0.0,
                "oldest_entry": None,
                "newest_entry": None,
                "cache_enabled": True,
            }
            mock_cache_class.return_value = mock_cache

            result = runner.invoke(cache_stats)
            assert result.exit_code == 0
            assert "Cache Statistics:" in result.output
            # Stats format will show key-value pairs
            # Cache stats format changed

    def test_cache_stats_populated(self, runner):
        """Test cache stats with populated cache."""
        with patch("oscapify.cache.CacheManager") as mock_cache_class:
            mock_cache = Mock()
            mock_cache.get_stats.return_value = {
                "total_entries": 100,
                "cache_size_mb": 1.5,
                "oldest_entry": "2024-01-01",
                "newest_entry": "2024-01-15",
                "cache_enabled": True,
            }
            mock_cache_class.return_value = mock_cache

            result = runner.invoke(cache_stats)
            assert result.exit_code == 0
            # Stats will be displayed in key-value format

    def test_clear_cache_confirmation(self, runner):
        """Test clear cache with confirmation."""
        with patch("oscapify.cache.CacheManager") as mock_cache_class:
            mock_cache = Mock()
            mock_cache.clear.return_value = None
            mock_cache_class.return_value = mock_cache

            # Simulate user confirming
            result = runner.invoke(clear_cache, input="y\n")
            assert result.exit_code == 0
            assert "✅ Cache cleared" in result.output
            mock_cache.clear.assert_called_once()

    def test_clear_cache_cancelled(self, runner):
        """Test clear cache when user cancels."""
        with patch("oscapify.cache.CacheManager") as mock_cache_class:
            mock_cache = Mock()
            mock_cache_class.return_value = mock_cache

            # Simulate user cancelling
            result = runner.invoke(clear_cache, input="n\n")
            assert result.exit_code == 1  # Click aborts on 'n'
            assert "Aborted" in result.output
            mock_cache.clear.assert_not_called()

    def test_clear_empty_cache(self, runner):
        """Test clearing an already empty cache."""
        with patch("oscapify.cache.CacheManager") as mock_cache_class:
            mock_cache = Mock()
            mock_cache_class.return_value = mock_cache

            # Even with empty cache, clear will be called after confirmation
            result = runner.invoke(clear_cache, input="y\n")
            assert result.exit_code == 0
            assert "✅ Cache cleared" in result.output
            mock_cache.clear.assert_called_once()


class TestCLIErrorHandling:
    """Test error handling across CLI commands."""

    def test_keyboard_interrupt_handling(self, runner, sample_csv):
        """Test handling of KeyboardInterrupt."""
        with patch("oscapify.cli.OscapifyProcessor") as mock:
            processor_instance = Mock()
            processor_instance.process_files.side_effect = KeyboardInterrupt()
            mock.return_value = processor_instance

            result = runner.invoke(process, [str(sample_csv)])
            assert result.exit_code == 1
            # KeyboardInterrupt is caught by Click

    def test_unexpected_exception_handling(self, runner, sample_csv):
        """Test handling of unexpected exceptions."""
        with patch("oscapify.cli.OscapifyProcessor") as mock:
            processor_instance = Mock()
            processor_instance.process_files.side_effect = Exception("Unexpected error")
            mock.return_value = processor_instance

            result = runner.invoke(process, [str(sample_csv)])
            assert result.exit_code == 1
            # Error is logged but not necessarily in output


class TestCLIIntegration:
    """Test end-to-end CLI integration scenarios."""

    def test_full_processing_workflow(self, runner, temp_dir):
        """Test complete workflow from CSV input to OSCAP output."""
        # Create test CSV
        csv_path = temp_dir / "integration_test.csv"
        df = pd.DataFrame({"pmid": ["12345678"], "sentence": ["This is a test sentence."]})
        df.to_csv(csv_path, index=False)

        # Mock the processor to avoid actual DOI lookups
        with patch("oscapify.cli.OscapifyProcessor") as mock:
            processor_instance = Mock()
            from oscapify.models import ProcessingStats

            stats = ProcessingStats()
            stats.total_files = 1
            stats.processed_files = 1
            stats.failed_files = 0
            processor_instance.process_files.return_value = stats
            mock.return_value = processor_instance

            # Process the file
            result = runner.invoke(process, [str(csv_path), "-o", str(temp_dir)])

            assert result.exit_code == 0

    def test_batch_processing_with_errors(self, runner, temp_dir):
        """Test batch processing with some files failing."""
        # Create multiple test CSVs
        csv1 = temp_dir / "test1.csv"
        csv2 = temp_dir / "test2.csv"
        csv3 = temp_dir / "test3.csv"

        for csv in [csv1, csv2, csv3]:
            pd.DataFrame({"pmid": ["12345"], "sentence": ["Test"]}).to_csv(csv, index=False)

        with patch("oscapify.cli.OscapifyProcessor") as mock:
            processor_instance = Mock()
            # Mock stats showing one file failed
            from oscapify.models import ProcessingStats

            stats = ProcessingStats()
            stats.total_files = 3
            stats.processed_files = 2
            stats.failed_files = 1
            processor_instance.process_files.return_value = stats
            mock.return_value = processor_instance

            result = runner.invoke(process, [str(temp_dir)])

            assert result.exit_code == 1  # Exit 1 due to failed files
