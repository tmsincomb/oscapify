#!/bin/bash

# Script to build and publish oscapify to PyPI using Poetry
# Usage: ./publish_to_pypi.sh [version] [--test]

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if Poetry is installed
if ! command -v poetry &> /dev/null; then
    echo -e "${RED}Error: Poetry is not installed${NC}"
    echo "Install Poetry with: curl -sSL https://install.python-poetry.org | python3 -"
    exit 1
fi

# Function to update version
update_version() {
    local new_version=$1
    echo -e "${YELLOW}Updating version to $new_version...${NC}"
    poetry version $new_version
}

# Parse arguments
VERSION=""
TEST_MODE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --test)
            TEST_MODE=true
            shift
            ;;
        *)
            VERSION=$1
            shift
            ;;
    esac
done

# Update version if provided
if [ ! -z "$VERSION" ]; then
    update_version $VERSION
fi

# Get current version
CURRENT_VERSION=$(poetry version -s)
echo -e "${GREEN}Current version: $CURRENT_VERSION${NC}"

# Clean previous builds
echo -e "${YELLOW}Cleaning previous builds...${NC}"
rm -rf dist/ build/ *.egg-info

# Run tests
echo -e "${YELLOW}Running tests...${NC}"
poetry run pytest

# Format code
echo -e "${YELLOW}Formatting code with black...${NC}"
poetry run black oscapify tests

# Build the package
echo -e "${YELLOW}Building package...${NC}"
poetry build

# Check the package
echo -e "${YELLOW}Checking package with Poetry...${NC}"
poetry check

# List the built files
echo -e "${GREEN}Built files:${NC}"
ls -la dist/

# Publish
if [ "$TEST_MODE" = true ]; then
    echo -e "${YELLOW}Publishing to Test PyPI...${NC}"
    echo -e "${YELLOW}Note: You need to configure Poetry with Test PyPI repository first${NC}"
    echo "Run: poetry config repositories.test-pypi https://test.pypi.org/legacy/"
    echo "Then: poetry config pypi-token.test-pypi your-test-pypi-token"

    read -p "Have you configured Test PyPI? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        poetry publish -r test-pypi
        echo -e "${GREEN}Package published to Test PyPI!${NC}"
        echo -e "Install with: pip install -i https://test.pypi.org/simple/ oscapify==$CURRENT_VERSION"
    fi
else
    echo -e "${YELLOW}Publishing to PyPI...${NC}"
    read -p "Are you sure you want to publish to PyPI? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        poetry publish
        echo -e "${GREEN}Package published to PyPI!${NC}"
        echo -e "Install with: pip install oscapify==$CURRENT_VERSION"

        # Create git tag
        echo -e "${YELLOW}Creating git tag v$CURRENT_VERSION...${NC}"
        git tag -a "v$CURRENT_VERSION" -m "Release version $CURRENT_VERSION"

        # Push tag
        read -p "Push tag to origin? (y/n): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            git push origin "v$CURRENT_VERSION"
            echo -e "${GREEN}Tag pushed!${NC}"
        fi
    fi
fi

echo -e "${GREEN}Done!${NC}"
