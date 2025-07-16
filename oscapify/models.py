"""Data models for Oscapify using Pydantic for validation."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class HeaderMapping(BaseModel):
    """Configuration for mapping input headers to output headers."""

    model_config = ConfigDict(extra="forbid")

    # Required input fields
    pmid: str = Field(default="pmid", description="Column name for PubMed ID")
    sentence: str = Field(default="sentence", description="Column name for sentence text")

    # Optional input fields
    pmcid: Optional[str] = Field(default="pmcid", description="Column name for PubMed Central ID")
    pubmed_url: Optional[str] = Field(
        default="pubmed_url", description="Column name for PubMed URL"
    )
    id_column: Optional[str] = Field(default="ID", description="Column name for original ID")

    # Additional fields to preserve
    preserve_fields: List[str] = Field(
        default_factory=lambda: ["structure_1", "structure_2", "relation", "score"],
        description="Additional fields to preserve from input",
    )


class ProcessingConfig(BaseModel):
    """Configuration for processing CSV files."""

    model_config = ConfigDict(extra="forbid")

    # Output Configuration
    suffix: str = Field(default="-oscapify", description="Suffix for output files")
    output_dir: Optional[str] = Field(default=None, description="Output directory path")
    batch_name: str = Field(default="oscapify_template", description="Batch name for processing")

    # Processing Options
    validate_headers: bool = Field(default=True, description="Validate input headers")
    cache_doi_lookups: bool = Field(default=True, description="Cache DOI lookups")
    debug_mode: bool = Field(default=False, description="Enable debug logging")

    # Header mapping configuration
    header_mapping: HeaderMapping = Field(default_factory=HeaderMapping)


class InputRecord(BaseModel):
    """Model for input CSV records."""

    model_config = ConfigDict(extra="allow")

    pmid: Optional[str] = None
    pmcid: Optional[str] = None
    sentence: str
    pubmed_url: Optional[str] = None

    @field_validator("pmid", "pmcid")
    @classmethod
    def clean_ids(cls, v: Optional[str]) -> Optional[str]:
        if v:
            v = str(v).strip()
            if v.lower() in ["nan", "none", ""]:
                return None
        return v

    def extract_pmcid_from_url(self) -> Optional[str]:
        """Extract PMCID from pubmed_url if available."""
        if self.pubmed_url and "PMC" in self.pubmed_url:
            import re

            match = re.search(r"PMC\d+", self.pubmed_url)
            if match:
                return match.group()
        return None


class OutputRecord(BaseModel):
    """Model for output CSV records."""

    model_config = ConfigDict(extra="forbid")

    id: str
    pmid: Optional[str] = ""
    pmcid: Optional[str] = ""
    doi: Optional[str] = ""
    sentence: str
    batch_name: str
    sentence_id: str
    out_of_scope: str = "yes"

    # Additional preserved fields
    additional_fields: Dict[str, Any] = Field(default_factory=dict)


class DOIResponse(BaseModel):
    """Model for NCBI DOI API response."""

    doi: Optional[str] = None
    pmid: Optional[str] = None
    pmcid: Optional[str] = None
    errmsg: Optional[str] = None

    @classmethod
    def from_api_response(cls, response: Dict[str, Any]) -> "DOIResponse":
        """Parse NCBI API response."""
        if "records" in response and response["records"]:
            record = response["records"][0]
            # Convert numeric IDs to strings if needed
            pmid = record.get("pmid")
            if pmid is not None:
                pmid = str(pmid)
            pmcid = record.get("pmcid")
            if pmcid is not None:
                pmcid = str(pmcid)
            return cls(
                doi=record.get("doi"),
                pmid=pmid,
                pmcid=pmcid,
                errmsg=record.get("errmsg"),
            )
        return cls(errmsg=response.get("errmsg", "No records found"))


class ProcessingStats(BaseModel):
    """Statistics for processing results."""

    total_files: int = 0
    processed_files: int = 0
    failed_files: int = 0
    total_records: int = 0
    successful_doi_lookups: int = 0
    failed_doi_lookups: int = 0
    processing_time: float = 0.0
    errors: List[Dict[str, str]] = Field(default_factory=list)
