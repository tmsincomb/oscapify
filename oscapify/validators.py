"""Header validation and debugging utilities."""

import logging
from difflib import get_close_matches
from typing import Dict, List, Optional, Set, Tuple

import pandas as pd

from .exceptions import HeaderValidationError
from .models import HeaderMapping

logger = logging.getLogger(__name__)


class HeaderValidator:
    """Validates and maps CSV headers with intelligent error correction."""

    def __init__(self, header_mapping: HeaderMapping):
        self.header_mapping = header_mapping
        self.required_headers = self._get_required_headers()

    def _get_required_headers(self) -> Set[str]:
        """Get set of required headers from mapping."""
        required = {self.header_mapping.pmid, self.header_mapping.sentence}
        if self.header_mapping.pmcid:
            required.add(self.header_mapping.pmcid)
        return required

    def validate_headers(
        self, df: pd.DataFrame, strict: bool = False
    ) -> Tuple[bool, Optional[Dict[str, str]]]:
        """
        Validate headers and suggest corrections.

        Returns:
            Tuple of (is_valid, correction_mapping)
        """
        headers = set(df.columns)
        missing = self.required_headers - headers

        if not missing:
            return True, None

        # Try case-insensitive matching
        corrections = {}
        remaining_missing = set()

        for missing_header in missing:
            found = False

            # Case-insensitive exact match
            for header in headers:
                if header.lower() == missing_header.lower():
                    corrections[header] = missing_header
                    found = True
                    break

            if not found:
                # Try fuzzy matching
                matches = get_close_matches(missing_header, list(headers), n=1, cutoff=0.8)
                if matches:
                    corrections[matches[0]] = missing_header
                    found = True

            if not found:
                remaining_missing.add(missing_header)

        if remaining_missing and strict:
            raise HeaderValidationError(
                f"Missing required headers: {remaining_missing}",
                missing_headers=list(remaining_missing),
            )

        return len(remaining_missing) == 0, corrections

    def debug_headers(self, df: pd.DataFrame) -> Dict[str, any]:
        """
        Provide detailed header debugging information.

        Returns dictionary with debugging info.
        """
        headers = list(df.columns)
        debug_info = {
            "found_headers": headers,
            "required_headers": list(self.required_headers),
            "optional_headers": [self.header_mapping.pubmed_url, self.header_mapping.id_column],
            "preserve_fields": self.header_mapping.preserve_fields,
            "header_stats": {
                "total_columns": len(headers),
                "has_duplicates": len(headers) != len(set(headers)),
                "duplicate_headers": [h for h in headers if headers.count(h) > 1],
                "empty_headers": [h for h in headers if not h or h.strip() == ""],
                "whitespace_issues": [h for h in headers if h != h.strip()],
            },
            "sample_data": {},
        }

        # Add sample data for each column
        for col in headers[:10]:  # Limit to first 10 columns
            sample = df[col].dropna().head(3).tolist()
            debug_info["sample_data"][col] = {
                "samples": sample,
                "dtype": str(df[col].dtype),
                "null_count": df[col].isnull().sum(),
                "unique_count": df[col].nunique(),
            }

        # Check for common header patterns
        common_patterns = {
            "pmid_variants": ["PMID", "pmid", "PubMedID", "pubmed_id", "pm_id"],
            "pmcid_variants": ["PMCID", "pmcid", "PMC", "pmc", "pmc_id"],
            "doi_variants": ["DOI", "doi", "digital_object_identifier"],
            "text_variants": ["sentence", "text", "abstract", "content", "passage"],
        }

        debug_info["detected_patterns"] = {}
        for pattern_name, variants in common_patterns.items():
            found = [h for h in headers if any(v.lower() in h.lower() for v in variants)]
            if found:
                debug_info["detected_patterns"][pattern_name] = found

        return debug_info

    def suggest_mapping(self, headers: List[str]) -> Dict[str, str]:
        """
        Suggest header mappings based on common patterns.

        Returns dictionary mapping found headers to expected headers.
        """
        suggestions = {}

        # Common mappings
        mapping_rules = {
            "pmid": ["PMID", "pmid", "PubMedID", "pubmed_id", "pm_id"],
            "pmcid": ["PMCID", "pmcid", "PMC", "pmc", "pmc_id"],
            "sentence": ["sentence", "text", "abstract", "content", "passage"],
            "pubmed_url": ["pubmed_url", "url", "link", "pubmed_link"],
            "ID": ["ID", "id", "identifier", "record_id"],
        }

        for expected, variants in mapping_rules.items():
            for header in headers:
                if any(v.lower() == header.lower() for v in variants):
                    suggestions[header] = expected
                    break

        return suggestions


class DataCleaner:
    """Clean and standardize data before processing."""

    @staticmethod
    def clean_id_field(value: any) -> Optional[str]:
        """Clean ID fields (PMID, PMCID)."""
        if pd.isna(value) or value is None:
            return None

        value = str(value).strip()

        # Remove common prefixes
        value = value.replace("PMC", "").replace("PMID:", "").strip()

        # Check if valid
        if value.lower() in ["nan", "none", "null", "n/a", ""]:
            return None

        # Ensure numeric for PMID
        if value.isdigit():
            return value

        return None

    @staticmethod
    def extract_pmcid_from_url(url: str) -> Optional[str]:
        """Extract PMCID from various URL formats."""
        if not url or pd.isna(url):
            return None

        import re

        # Common patterns
        patterns = [r"PMC(\d+)", r"pmc(\d+)", r"articles/PMC(\d+)", r"articleid=(\d+).*type=pmc"]

        for pattern in patterns:
            match = re.search(pattern, str(url), re.IGNORECASE)
            if match:
                return f"PMC{match.group(1)}"

        return None

    @staticmethod
    def standardize_dataframe(df: pd.DataFrame, header_mapping: HeaderMapping) -> pd.DataFrame:
        """Standardize dataframe columns and clean data."""
        # Clean column names
        df.columns = df.columns.str.strip()

        # Remove duplicate columns
        df = df.loc[:, ~df.columns.duplicated()]

        # Clean ID fields
        if header_mapping.pmid in df.columns:
            df[header_mapping.pmid] = df[header_mapping.pmid].apply(DataCleaner.clean_id_field)

        if header_mapping.pmcid in df.columns:
            df[header_mapping.pmcid] = df[header_mapping.pmcid].apply(DataCleaner.clean_id_field)

        # Try to extract PMCID from URL if not present
        if header_mapping.pubmed_url in df.columns and (
            header_mapping.pmcid not in df.columns or df[header_mapping.pmcid].isna().all()
        ):
            df["extracted_pmcid"] = df[header_mapping.pubmed_url].apply(
                DataCleaner.extract_pmcid_from_url
            )

            if header_mapping.pmcid in df.columns:
                df[header_mapping.pmcid] = df[header_mapping.pmcid].fillna(df["extracted_pmcid"])
            else:
                df[header_mapping.pmcid] = df["extracted_pmcid"]

            df = df.drop(columns=["extracted_pmcid"])

        return df
