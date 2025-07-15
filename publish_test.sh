#!/bin/bash

# Mock test version of publish.sh
# This simulates the publishing process without actually uploading

set -e  # Exit on error

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

print_warning "THIS IS A TEST RUN - No actual uploads will occur"
echo

# Copy the real script and modify it
cp publish.sh publish_test_temp.sh

# Replace actual twine upload commands with mock ones
sed -i.bak 's/twine upload --repository testpypi/echo "[MOCK] Would run: twine upload --repository testpypi/' publish_test_temp.sh
sed -i.bak 's/twine upload dist/echo "[MOCK] Would run: twine upload dist/' publish_test_temp.sh

# Also mock git operations to be safe
sed -i.bak 's/git add pyproject.toml/echo "[MOCK] Would run: git add pyproject.toml"/' publish_test_temp.sh
sed -i.bak 's/git commit -m/echo "[MOCK] Would run: git commit -m/' publish_test_temp.sh
sed -i.bak 's/git tag -a/echo "[MOCK] Would run: git tag -a/' publish_test_temp.sh
sed -i.bak 's/git push origin/echo "[MOCK] Would run: git push origin/' publish_test_temp.sh

# Run the modified script
print_info "Running mock test..."
echo
bash publish_test_temp.sh

# Cleanup
rm -f publish_test_temp.sh publish_test_temp.sh.bak

echo
print_success "Mock test completed! Review the output above to see what would happen."
