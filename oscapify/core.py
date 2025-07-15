"""Core processing logic for Oscapify."""

import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd
import requests

from .cache import CacheManager, cached_function
from .exceptions import DOIRetrievalError, FileProcessingError, HeaderValidationError
from .models import (
    DOIResponse,
    InputRecord,
    OutputRecord,
    ProcessingConfig,
    ProcessingStats,
)
from .validators import DataCleaner, HeaderValidator

logger = logging.getLogger(__name__)


class OscapifyProcessor:
    """Main processor for converting CSV files to OSCAP format."""

    def __init__(self, config: ProcessingConfig):
        self.config = config
        self.cache_manager = CacheManager() if config.cache_doi_lookups else None
        self.header_validator = HeaderValidator(config.header_mapping)
        self.stats = ProcessingStats()

        # Setup logging
        if config.debug_mode:
            logging.basicConfig(
                level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )

        # Setup DOI retrieval with caching if enabled
        if self.cache_manager:
            self._get_doi_cached = cached_function(
                self.cache_manager, expire_days=365, key_prefix="doi"  # DOIs don't change
            )(self._get_doi_from_api)
        else:
            self._get_doi_cached = self._get_doi_from_api

    def process_files(self, input_paths: List[str]) -> ProcessingStats:
        """
        Process multiple CSV files.

        Args:
            input_paths: List of file or directory paths

        Returns:
            ProcessingStats with results
        """
        start_time = time.time()

        # Collect all CSV files
        csv_files = self._collect_csv_files(input_paths)
        self.stats.total_files = len(csv_files)

        logger.info(f"Found {len(csv_files)} CSV files to process")

        # Create output directory
        output_dir = self._create_output_directory()

        # Process each file
        for csv_file in csv_files:
            try:
                self._process_single_file(csv_file, output_dir)
                self.stats.processed_files += 1
            except Exception as e:
                self.stats.failed_files += 1
                self.stats.errors.append(
                    {"file": str(csv_file), "error": str(e), "type": type(e).__name__}
                )
                logger.error(f"Failed to process {csv_file}: {e}")

                if not self.config.skip_doi_errors and isinstance(e, DOIRetrievalError):
                    raise

        self.stats.processing_time = time.time() - start_time

        # Log summary
        self._log_summary()

        return self.stats

    def _collect_csv_files(self, input_paths: List[str]) -> List[Path]:
        """Collect all CSV files from input paths."""
        csv_files = []

        for path_str in input_paths:
            path = Path(path_str)

            if path.is_file() and path.suffix.lower() == ".csv":
                csv_files.append(path)
            elif path.is_dir():
                csv_files.extend(path.glob("*.csv"))
            else:
                logger.warning(f"Skipping invalid path: {path}")

        return sorted(csv_files)

    def _create_output_directory(self) -> Path:
        """Create output directory."""
        if self.config.output_dir:
            output_dir = Path(self.config.output_dir)
        else:
            output_dir = Path(f"oscapify_output_{datetime.now():%Y%m%d_%H%M%S}")

        output_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Output directory: {output_dir}")

        return output_dir

    def _process_single_file(self, input_file: Path, output_dir: Path) -> None:
        """Process a single CSV file."""
        logger.info(f"Processing: {input_file.name}")

        try:
            # Read CSV with error handling
            df = self._read_csv_safely(input_file)

            # Validate and clean headers
            if self.config.validate_headers:
                df = self._validate_and_fix_headers(df, input_file)

            # Clean and standardize data
            df = DataCleaner.standardize_dataframe(df, self.config.header_mapping)

            # Process records
            df = self._process_dataframe(df)

            # Save output
            output_file = output_dir / f"{input_file.stem}{self.config.suffix}.csv"
            self._save_output(df, output_file)

            logger.info(f"Successfully processed {input_file.name} -> {output_file.name}")

        except Exception as e:
            raise FileProcessingError(f"Error processing {input_file}: {e}", str(input_file))

    def _read_csv_safely(self, file_path: Path) -> pd.DataFrame:
        """Read CSV with multiple encoding attempts."""
        encodings = ["utf-8", "latin-1", "iso-8859-1", "cp1252"]

        for encoding in encodings:
            try:
                return pd.read_csv(file_path, encoding=encoding)
            except UnicodeDecodeError:
                continue
            except pd.errors.EmptyDataError:
                raise FileProcessingError(f"Empty CSV file: {file_path}")

        raise FileProcessingError(f"Could not read {file_path} with any encoding")

    def _validate_and_fix_headers(self, df: pd.DataFrame, file_path: Path) -> pd.DataFrame:
        """Validate headers and attempt fixes."""
        is_valid, corrections = self.header_validator.validate_headers(df)

        if not is_valid:
            # Debug headers
            debug_info = self.header_validator.debug_headers(df)
            logger.warning(f"Header validation failed for {file_path.name}")
            logger.debug(f"Debug info: {debug_info}")

            if corrections:
                # Apply corrections
                logger.info(f"Applying header corrections: {corrections}")
                df = df.rename(columns=corrections)

                # Re-validate
                is_valid, _ = self.header_validator.validate_headers(df)
                if not is_valid:
                    raise HeaderValidationError(
                        f"Headers still invalid after corrections in {file_path.name}",
                        missing_headers=list(
                            self.header_validator.required_headers - set(df.columns)
                        ),
                    )
            else:
                # Try to get suggestions
                suggestions = self.header_validator.suggest_mapping(list(df.columns))
                error_msg = f"Missing required headers in {file_path.name}"
                if suggestions:
                    error_msg += f". Suggested mappings: {suggestions}"
                raise HeaderValidationError(error_msg)

        return df

    def _process_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """Process dataframe records."""
        # Reset index and create IDs
        df.index = df.index + 1
        df = df.reset_index().rename(columns={"index": "_row_id"})

        # Process each row
        processed_records = []

        for idx, row in df.iterrows():
            try:
                # Create input record
                input_rec = InputRecord(
                    pmid=row.get(self.config.header_mapping.pmid),
                    pmcid=row.get(self.config.header_mapping.pmcid),
                    sentence=row.get(self.config.header_mapping.sentence, ""),
                    pubmed_url=row.get(self.config.header_mapping.pubmed_url),
                )

                # Extract PMCID from URL if needed
                if not input_rec.pmcid and input_rec.pubmed_url:
                    input_rec.pmcid = input_rec.extract_pmcid_from_url()

                # Create output record
                output_rec = OutputRecord(
                    id=f"nlp-{row['_row_id']}-{datetime.now():%Y%m%d}",
                    pmid=input_rec.pmid or "",
                    pmcid=input_rec.pmcid or "",
                    sentence=input_rec.sentence,
                    batch_name=self.config.batch_name,
                    sentence_id=f"nlp-{row['_row_id']}-{datetime.now():%Y%m%d}",
                    out_of_scope="yes",
                )

                # Try to get DOI
                if input_rec.pmid or input_rec.pmcid:
                    doi_info = self._get_doi(input_rec)
                    if doi_info and doi_info.doi:
                        output_rec.doi = doi_info.doi
                        output_rec.out_of_scope = "no"
                        if doi_info.pmid:
                            output_rec.pmid = doi_info.pmid
                        if doi_info.pmcid:
                            output_rec.pmcid = doi_info.pmcid
                        self.stats.successful_doi_lookups += 1
                    else:
                        self.stats.failed_doi_lookups += 1

                # Add preserved fields
                for field in self.config.header_mapping.preserve_fields:
                    if field in row:
                        output_rec.additional_fields[field] = row[field]

                processed_records.append(output_rec.model_dump())
                self.stats.total_records += 1

            except Exception as e:
                logger.error(f"Error processing row {idx}: {e}")
                if not self.config.skip_doi_errors:
                    raise

        # Convert to dataframe
        result_df = pd.DataFrame(processed_records)

        # Reorder columns
        base_columns = [
            "id",
            "pmid",
            "pmcid",
            "doi",
            "sentence",
            "batch_name",
            "sentence_id",
            "out_of_scope",
        ]
        additional_columns = [col for col in result_df.columns if col not in base_columns]
        ordered_columns = base_columns + additional_columns

        return result_df[ordered_columns]

    def _get_doi(self, record: InputRecord) -> Optional[DOIResponse]:
        """Get DOI information for a record."""
        # Determine which ID to use
        query_id = record.pmcid if record.pmcid else record.pmid

        if not query_id:
            return None

        try:
            return self._get_doi_cached(query_id)
        except Exception as e:
            logger.error(f"DOI retrieval failed for {query_id}: {e}")
            if not self.config.skip_doi_errors:
                raise DOIRetrievalError(
                    f"Failed to retrieve DOI for {query_id}: {e}",
                    pmid=record.pmid,
                    pmcid=record.pmcid,
                )
            return None

    def _get_doi_from_api(self, identifier: str) -> Optional[DOIResponse]:
        """Retrieve DOI from NCBI API."""
        base_url = "https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/"

        params = {"tool": "oscapify", "ids": identifier, "format": "json"}

        if self.config.api_key:
            params["api_key"] = self.config.api_key

        try:
            response = requests.get(base_url, params=params, timeout=30)
            response.raise_for_status()

            data = response.json()
            return DOIResponse.from_api_response(data)

        except requests.RequestException as e:
            logger.error(f"API request failed: {e}")
            raise
        except Exception as e:
            logger.error(f"Error parsing API response: {e}")
            raise

    def _save_output(self, df: pd.DataFrame, output_file: Path) -> None:
        """Save output dataframe to CSV."""
        try:
            df.to_csv(output_file, index=False)
            logger.debug(f"Saved {len(df)} records to {output_file}")
        except Exception as e:
            raise FileProcessingError(f"Could not save output to {output_file}: {e}")

    def _log_summary(self) -> None:
        """Log processing summary."""
        logger.info("=" * 50)
        logger.info("Processing Summary:")
        logger.info(f"Total files: {self.stats.total_files}")
        logger.info(f"Processed successfully: {self.stats.processed_files}")
        logger.info(f"Failed: {self.stats.failed_files}")
        logger.info(f"Total records: {self.stats.total_records}")
        logger.info(f"Successful DOI lookups: {self.stats.successful_doi_lookups}")
        logger.info(f"Failed DOI lookups: {self.stats.failed_doi_lookups}")
        logger.info(f"Processing time: {self.stats.processing_time:.2f} seconds")

        if self.cache_manager:
            cache_stats = self._get_doi_cached.get_cache_stats()
            logger.info(f"Cache stats: {cache_stats}")

        if self.stats.errors:
            logger.warning(f"Errors encountered: {len(self.stats.errors)}")
            for error in self.stats.errors[:5]:  # Show first 5 errors
                logger.warning(f"  - {error['file']}: {error['error']}")

        logger.info("=" * 50)
