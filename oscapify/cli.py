"""Command-line interface for Oscapify."""

import logging
import sys
from pathlib import Path
from typing import List, Optional

import click

from . import __version__
from .core import OscapifyProcessor
from .models import HeaderMapping, ProcessingConfig
from .validators import HeaderValidator

logger = logging.getLogger(__name__)


@click.group(invoke_without_command=True)
@click.pass_context
@click.version_option(version=__version__, prog_name="oscapify")
def cli(ctx):
    """Oscapify - Convert scientific literature CSV files to OSCAP-compatible format."""
    if ctx.invoked_subcommand is None:
        # If no subcommand, run the default process command
        ctx.invoke(process)


@cli.command()
@click.argument("inputs", nargs=-1, type=click.Path(exists=True), required=True)
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    help="Output directory (default: oscapify_output_YYYYMMDD_HHMMSS)",
)
@click.option("--api-key", "-k", help="NCBI API key for higher rate limits")
@click.option(
    "--suffix", "-s", default="-oscapify", help="Suffix for output files (default: -oscapify)"
)
@click.option(
    "--batch-name",
    "-b",
    default="oscapify_batch",
    help="Batch name for processing (default: oscapify_batch)",
)
@click.option("--no-cache", is_flag=True, help="Disable DOI lookup caching")
@click.option("--no-validation", is_flag=True, help="Skip header validation")
@click.option("--strict", is_flag=True, help="Fail on any error instead of skipping")
@click.option("--debug", is_flag=True, help="Enable debug logging")
@click.option("--header-pmid", default="pmid", help="Column name for PubMed ID (default: pmid)")
@click.option(
    "--header-sentence",
    default="sentence",
    help="Column name for sentence text (default: sentence)",
)
@click.option("--preserve-fields", multiple=True, help="Additional fields to preserve from input")
def process(
    inputs: List[str],
    output: Optional[str],
    api_key: Optional[str],
    suffix: str,
    batch_name: str,
    no_cache: bool,
    no_validation: bool,
    strict: bool,
    debug: bool,
    header_pmid: str,
    header_sentence: str,
    preserve_fields: tuple,
):
    """Process CSV files to OSCAP format."""
    # Setup logging
    log_level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=log_level, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Create header mapping
    header_mapping_args = {
        "pmid": header_pmid,
        "sentence": header_sentence,
    }
    if preserve_fields:
        header_mapping_args["preserve_fields"] = list(preserve_fields)

    header_mapping = HeaderMapping(**header_mapping_args)

    # Create processing config
    config = ProcessingConfig(
        api_key=api_key,
        suffix=suffix,
        output_dir=output,
        batch_name=batch_name,
        validate_headers=not no_validation,
        skip_doi_errors=not strict,
        cache_doi_lookups=not no_cache,
        debug_mode=debug,
        header_mapping=header_mapping,
    )

    # Process files
    try:
        processor = OscapifyProcessor(config)
        stats = processor.process_files(list(inputs))

        # Exit with error code if any files failed
        if stats.failed_files > 0:
            sys.exit(1)

    except Exception as e:
        logger.error(f"Processing failed: {e}")
        if debug:
            logger.exception("Full traceback:")
        sys.exit(1)


@cli.command()
@click.argument("csv_file", type=click.Path(exists=True))
@click.option(
    "--suggest-mappings", is_flag=True, help="Suggest header mappings based on common patterns"
)
def validate(csv_file: str, suggest_mappings: bool):
    """Validate CSV file headers and show debugging information."""
    import pandas as pd

    # Setup logging
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    try:
        # Read CSV
        df = pd.read_csv(csv_file)

        # Create validator with default mapping
        validator = HeaderValidator(HeaderMapping())

        # Get debug info
        debug_info = validator.debug_headers(df)

        # Display results
        click.echo(f"\nValidating: {csv_file}")
        click.echo("=" * 60)

        click.echo(f"\nFound {debug_info['header_stats']['total_columns']} columns:")
        for i, header in enumerate(debug_info["found_headers"], 1):
            click.echo(f"  {i}. {header}")

        # Check for issues
        if debug_info["header_stats"]["has_duplicates"]:
            click.echo("\n⚠️  Duplicate headers found:")
            for dup in set(debug_info["header_stats"]["duplicate_headers"]):
                click.echo(f"  - {dup}")

        if debug_info["header_stats"]["empty_headers"]:
            click.echo("\n⚠️  Empty headers found")

        if debug_info["header_stats"]["whitespace_issues"]:
            click.echo("\n⚠️  Headers with whitespace issues:")
            for header in debug_info["header_stats"]["whitespace_issues"]:
                click.echo(f"  - '{header}'")

        # Validate required headers
        is_valid, corrections = validator.validate_headers(df)

        if is_valid:
            click.echo("\n✅ All required headers found")
        else:
            click.echo("\n❌ Missing required headers")
            if corrections:
                click.echo("\nSuggested corrections:")
                for old, new in corrections.items():
                    click.echo(f"  - Rename '{old}' to '{new}'")

        # Show pattern detection
        if debug_info["detected_patterns"]:
            click.echo("\nDetected header patterns:")
            for pattern, headers in debug_info["detected_patterns"].items():
                click.echo(f"  {pattern}: {', '.join(headers)}")

        # Show suggestions if requested
        if suggest_mappings:
            suggestions = validator.suggest_mapping(debug_info["found_headers"])
            if suggestions:
                click.echo("\nSuggested mappings:")
                for found, expected in suggestions.items():
                    click.echo(f"  --header-{expected.lower().replace('_', '-')} '{found}'")

        # Show sample data
        click.echo("\nSample data (first 3 non-null values per column):")
        for col, info in list(debug_info["sample_data"].items())[:5]:
            click.echo(f"\n  {col} ({info['dtype']}):")
            click.echo(f"    Nulls: {info['null_count']}, Unique: {info['unique_count']}")
            if info["samples"]:
                for sample in info["samples"][:3]:
                    click.echo(f"    - {sample}")

    except Exception as e:
        click.echo(f"\n❌ Error: {e}", err=True)
        sys.exit(1)


@cli.command()
def cache_stats():
    """Show cache statistics."""
    from .cache import CacheManager

    cache = CacheManager()
    stats = cache.get_stats()

    click.echo("\nCache Statistics:")
    click.echo("=" * 40)
    for key, value in stats.items():
        click.echo(f"{key:.<20} {value}")


@cli.command()
@click.confirmation_option(prompt="Are you sure you want to clear the cache?")
def clear_cache():
    """Clear the DOI lookup cache."""
    from .cache import CacheManager

    cache = CacheManager()
    cache.clear()
    click.echo("✅ Cache cleared")


def main():
    """Main entry point."""
    cli()


if __name__ == "__main__":
    main()
