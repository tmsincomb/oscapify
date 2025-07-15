# Oscapify

[![PyPI version](https://badge.fury.io/py/oscapify.svg)](https://badge.fury.io/py/oscapify)
[![Python versions](https://img.shields.io/pypi/pyversions/oscapify.svg)](https://pypi.org/project/oscapify/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A robust tool for converting scientific literature CSV files to OSCAP-compatible format. Oscapify processes neuroscience connectivity data from PubMed/PMC sources, validates headers, retrieves DOIs, and handles errors gracefully.

## Features

- **Intelligent Header Validation**: Automatically detects and corrects common header issues
- **Flexible Header Mapping**: Support for custom column names and formats
- **DOI Retrieval**: Fetches DOIs from NCBI API with built-in caching
- **Error Recovery**: Continues processing even when individual records fail
- **Detailed Debugging**: Comprehensive logging and header analysis tools
- **Batch Processing**: Process multiple files or entire directories
- **Performance**: Persistent caching and efficient batch operations

## Installation

```bash
pip install oscapify
```

### Development Installation

```bash
git clone https://github.com/yourusername/oscapify.git
cd oscapify
pip install -e ".[dev]"
```

## Quick Start

### Basic Usage

```bash
# Process a single file
oscapify process input.csv

# Process multiple files
oscapify process file1.csv file2.csv

# Process all CSV files in a directory
oscapify process /path/to/csv/directory/

# Specify output directory
oscapify process input.csv --output ./results
```

### Header Validation and Debugging

```bash
# Validate CSV headers and see debugging info
oscapify validate input.csv

# Get header mapping suggestions
oscapify validate input.csv --suggest-mappings
```

### Custom Header Mapping

If your CSV files use different column names:

```bash
oscapify process input.csv \
  --header-pmid "PubMedID" \
  --header-sentence "text" \
  --preserve-fields "custom_field1" "custom_field2"
```

## Expected Input Format

Oscapify expects CSV files with the following columns (case-insensitive):

- `pmid` - PubMed ID
- `sentence` - Text content
- `pmcid` (optional) - PubMed Central ID
- `pubmed_url` (optional) - URL to PubMed/PMC article

Additional columns are preserved in the output.

### Example Input CSV

```csv
ID,pmid,pmcid,sentence,structure_1,structure_2,relation,score,pubmed_url
1,12345678,PMC1234567,"The brain connects to the spinal cord.",brain,spinal cord,connects,0.95,https://pubmed.ncbi.nlm.nih.gov/12345678/
```

## Output Format

Oscapify outputs CSV files with OSCAP-compatible formatting:

- `id` - Unique identifier (format: `nlp-{index}-{date}`)
- `pmid` - PubMed ID
- `pmcid` - PubMed Central ID
- `doi` - Digital Object Identifier (retrieved from NCBI)
- `sentence` - Original text
- `batch_name` - Processing batch identifier
- `sentence_id` - Sentence identifier
- `out_of_scope` - "yes" if DOI couldn't be retrieved, "no" otherwise

## Advanced Features

### Cache Management

```bash
# View cache statistics
oscapify cache-stats

# Clear the DOI cache
oscapify clear-cache
```

### Error Handling Options

```bash
# Stop on first error (strict mode)
oscapify process input.csv --strict

# Disable caching for testing
oscapify process input.csv --no-cache

# Skip header validation
oscapify process input.csv --no-validation
```

### Debug Mode

```bash
# Enable detailed debug logging
oscapify process input.csv --debug
```

## Python API

```python
from oscapify import OscapifyProcessor
from oscapify.models import ProcessingConfig

# Create configuration
config = ProcessingConfig(
    output_dir="./output",
    batch_name="my_batch"
)

# Process files
processor = OscapifyProcessor(config)
stats = processor.process_files(["input1.csv", "input2.csv"])

# Check results
print(f"Processed {stats.processed_files} files")
print(f"Total records: {stats.total_records}")
print(f"DOI lookups: {stats.successful_doi_lookups} successful, {stats.failed_doi_lookups} failed")
```

## Configuration

### Environment Variables

- `OSCAPIFY_API_KEY` - NCBI API key for higher rate limits

### Custom Header Mapping via API

```python
from oscapify.models import HeaderMapping, ProcessingConfig

# Define custom mapping
header_mapping = HeaderMapping(
    pmid="PubMedID",
    sentence="abstract_text",
    pmcid="PMC_ID",
    preserve_fields=["experiment_type", "confidence_score"]
)

config = ProcessingConfig(
    header_mapping=header_mapping
)
```

## Troubleshooting

### Common Issues

1. **Missing Headers Error**
   ```bash
   # Check what headers are in your file
   oscapify validate problematic.csv

   # Use suggested mappings
   oscapify validate problematic.csv --suggest-mappings
   ```

2. **DOI Retrieval Failures**
   - Check your internet connection
   - Consider using an NCBI API key for better rate limits

3. **Encoding Errors**
   - Oscapify automatically tries multiple encodings
   - If issues persist, convert your CSV to UTF-8

### Getting Help

```bash
# View all commands and options
oscapify --help

# View help for specific command
oscapify process --help
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Citation

If you use Oscapify in your research, please cite:

```bibtex
@software{oscapify,
  author = {Troy Sincomb},
  title = {Oscapify: A tool for converting scientific literature CSV files to OSCAP format},
  year = {2025},
  url = {https://github.com/yourusername/oscapify}
}
```

## Acknowledgments

- Uses the NCBI E-utilities API for DOI retrieval
- Built with Click for CLI interface
- Pandas for data processing
- Pydantic for data validation
