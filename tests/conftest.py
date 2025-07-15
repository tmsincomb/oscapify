"""Pytest configuration and fixtures."""

import shutil
import tempfile
from pathlib import Path

import pandas as pd
import pytest

# Path to test data directories
TEST_DATA_DIR = Path(__file__).parent / "data"
TEST_INPUT_DIR = TEST_DATA_DIR / "input"
TEST_OUTPUT_DIR = TEST_DATA_DIR / "output"


@pytest.fixture()
def temp_dir():
    """Create a temporary directory for tests."""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)


@pytest.fixture()
def sample_csv_data():
    """Sample CSV data for testing."""
    return pd.DataFrame(
        {
            "ID": [1, 2, 3, 4, 5],
            "pmid": ["12345678", "87654321", None, "11111111", "22222222"],
            "pmcid": ["PMC1234567", None, "PMC7654321", None, "PMC3333333"],
            "sentence": [
                "The brain connects to the spinal cord.",
                "Neurons communicate through synapses.",
                "The hippocampus is involved in memory.",
                "Dopamine is a neurotransmitter.",
                "The cortex has multiple layers.",
            ],
            "structure_1": ["brain", "neurons", "hippocampus", "dopamine", "cortex"],
            "structure_2": ["spinal cord", "synapses", "memory", "receptors", "layers"],
            "relation": ["connects", "communicate", "involved", "binds", "has"],
            "score": [0.95, 0.87, 0.92, 0.88, 0.90],
            "pubmed_url": [
                "https://pubmed.ncbi.nlm.nih.gov/12345678/",
                "https://pubmed.ncbi.nlm.nih.gov/87654321/",
                "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC7654321/",
                "https://pubmed.ncbi.nlm.nih.gov/11111111/",
                "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC3333333/",
            ],
        }
    )


@pytest.fixture()
def sample_csv_with_header_issues():
    """Sample CSV with header problems for testing."""
    return pd.DataFrame(
        {
            "PMID": ["12345678", "87654321"],  # Different case
            "  sentence  ": ["Test sentence 1", "Test sentence 2"],  # Whitespace
            "Structure_1": ["brain", "neuron"],  # Different format
            "structure_2": ["cord", "synapse"],
            "": ["empty", "header"],  # Empty header
        }
    )


@pytest.fixture()
def mock_doi_response():
    """Mock DOI API response."""
    return {
        "records": [{"pmid": "12345678", "pmcid": "PMC1234567", "doi": "10.1234/test.doi.12345"}]
    }


@pytest.fixture()
def test_input_csv_files():
    """Get list of test input CSV files."""
    return list(TEST_INPUT_DIR.glob("*.csv"))


@pytest.fixture()
def test_output_dir():
    """Get test output directory, ensuring it exists."""
    TEST_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    return TEST_OUTPUT_DIR


@pytest.fixture()
def sample_input_csv_path():
    """Get path to a sample input CSV file."""
    csv_files = list(TEST_INPUT_DIR.glob("*.csv"))
    if not csv_files:
        raise FileNotFoundError(f"No CSV files found in {TEST_INPUT_DIR}")
    return csv_files[0]


@pytest.fixture()
def real_csv_data():
    """Load real CSV data from test input directory."""
    csv_file = list(TEST_INPUT_DIR.glob("*.csv"))[0]
    return pd.read_csv(csv_file)
