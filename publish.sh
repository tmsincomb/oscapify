#!/bin/bash

# Oscapify PyPI Publishing Script
# This script automates the process of publishing oscapify to PyPI

set -e # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to get current version from pyproject.toml
get_current_version() {
    grep '^version = ' pyproject.toml | sed 's/version = "\(.*\)"/\1/'
}

# Function to update version in pyproject.toml
update_version() {
    local new_version=$1
    sed -i.bak "s/^version = \".*\"/version = \"${new_version}\"/" pyproject.toml
    rm -f pyproject.toml.bak
}

# Function to check if git working directory is clean
check_git_clean() {
    if [[ -n $(git status --porcelain) ]]; then
        print_error "Git working directory is not clean. Please commit or stash changes."
        exit 1
    fi
}

# Function to run tests
run_tests() {
    print_info "Running tests..."
    if pytest; then
        print_success "All tests passed!"
    else
        print_error "Tests failed. Fix issues before publishing."
        exit 1
    fi
}

# Function to run quality checks
run_quality_checks() {
    print_info "Running quality checks..."

    # # Run ruff
    # if ruff check .; then
    #     print_success "Ruff check passed!"
    # else
    #     print_error "Ruff check failed. Fix linting issues before publishing."
    #     exit 1
    # fi

    # # Run mypy
    # if mypy oscapify/; then
    #     print_success "Type checking passed!"
    # else
    #     print_error "Type checking failed. Fix type issues before publishing."
    #     exit 1
    # fi

    # Run black check
    if black --check .; then
        print_success "Code formatting check passed!"
    else
        print_error "Code formatting check failed. Run 'black .' to fix."
        exit 1
    fi
}

# Main script
print_info "Oscapify PyPI Publishing Script"
echo "================================"

# Check required commands
for cmd in python pip git twine; do
    if ! command_exists $cmd; then
        print_error "$cmd is not installed. Please install it first."
        exit 1
    fi
done

# Check if we're in the right directory
if [[ ! -f "pyproject.toml" ]] || [[ ! -d "oscapify" ]]; then
    print_error "This script must be run from the oscapify project root directory."
    exit 1
fi

# Check git status
check_git_clean

# Get current version
CURRENT_VERSION=$(get_current_version)
print_info "Current version: $CURRENT_VERSION"

# Ask for new version
echo
read -p "Enter new version (or press Enter to keep $CURRENT_VERSION): " NEW_VERSION
if [[ -z "$NEW_VERSION" ]]; then
    NEW_VERSION=$CURRENT_VERSION
    print_info "Keeping current version: $NEW_VERSION"
else
    # Validate version format (basic semantic versioning)
    if [[ ! "$NEW_VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+(-[a-zA-Z0-9]+)?$ ]]; then
        print_error "Invalid version format. Please use semantic versioning (e.g., 1.0.0, 1.0.0-beta1)"
        exit 1
    fi

    # Update version
    update_version "$NEW_VERSION"
    print_success "Updated version to: $NEW_VERSION"
fi

# Run tests and quality checks
echo
read -p "Run tests and quality checks? (Y/n): " RUN_CHECKS
if [[ "$RUN_CHECKS" != "n" ]] && [[ "$RUN_CHECKS" != "N" ]]; then
    run_tests
    run_quality_checks
else
    print_warning "Skipping tests and quality checks (not recommended)"
fi

# Clean previous builds
print_info "Cleaning previous builds..."
rm -rf dist/ build/ *.egg-info/
print_success "Cleaned build directories"

# Build the package
print_info "Building package..."
python -m build
print_success "Package built successfully"

# Check the package
print_info "Checking package with twine..."
if twine check dist/*; then
    print_success "Package check passed!"
else
    print_error "Package check failed."
    exit 1
fi

# Ask about Test PyPI
echo
read -p "Upload to Test PyPI first? (recommended) (Y/n): " USE_TEST_PYPI
if [[ "$USE_TEST_PYPI" != "n" ]] && [[ "$USE_TEST_PYPI" != "N" ]]; then
    print_info "Uploading to Test PyPI..."
    print_warning "You will be prompted for credentials. Use __token__ as username and your Test PyPI token as password."

    if twine upload --repository testpypi dist/*; then
        print_success "Upload to Test PyPI successful!"
        echo
        print_info "Test installation command:"
        echo "pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ oscapify"
        echo
        read -p "Did you test the installation? Continue to PyPI? (y/N): " CONTINUE_TO_PYPI
        if [[ "$CONTINUE_TO_PYPI" != "y" ]] && [[ "$CONTINUE_TO_PYPI" != "Y" ]]; then
            print_info "Stopping here. Run the script again to upload to PyPI."
            exit 0
        fi
    else
        print_error "Upload to Test PyPI failed."
        exit 1
    fi
fi

# Final confirmation
echo
print_warning "About to upload to PyPI (production)"
print_info "Version: $NEW_VERSION"
read -p "Are you sure you want to continue? (y/N): " FINAL_CONFIRM

if [[ "$FINAL_CONFIRM" != "y" ]] && [[ "$FINAL_CONFIRM" != "Y" ]]; then
    print_info "Upload cancelled."
    exit 0
fi

# Upload to PyPI
print_info "Uploading to PyPI..."
print_warning "You will be prompted for credentials. Use __token__ as username and your PyPI token as password."

if twine upload dist/*; then
    print_success "Package uploaded successfully to PyPI!"

    # Git operations
    echo
    read -p "Create git tag for v$NEW_VERSION? (Y/n): " CREATE_TAG
    if [[ "$CREATE_TAG" != "n" ]] && [[ "$CREATE_TAG" != "N" ]]; then
        # Commit version change if different
        if [[ "$CURRENT_VERSION" != "$NEW_VERSION" ]]; then
            git add pyproject.toml
            git commit -m "Bump version to $NEW_VERSION"
            print_success "Committed version change"
        fi

        # Create tag
        git tag -a "v$NEW_VERSION" -m "Release version $NEW_VERSION"
        print_success "Created git tag: v$NEW_VERSION"

        echo
        read -p "Push tag to origin? (Y/n): " PUSH_TAG
        if [[ "$PUSH_TAG" != "n" ]] && [[ "$PUSH_TAG" != "N" ]]; then
            git push origin "v$NEW_VERSION"
            print_success "Pushed tag to origin"

            # Push commits if any
            if [[ "$CURRENT_VERSION" != "$NEW_VERSION" ]]; then
                git push origin
                print_success "Pushed commits to origin"
            fi
        fi
    fi

    echo
    print_success "🎉 Release complete!"
    print_info "Package available at: https://pypi.org/project/oscapify/$NEW_VERSION/"
    print_info "Install with: pip install oscapify==$NEW_VERSION"
else
    print_error "Upload to PyPI failed."
    exit 1
fi
