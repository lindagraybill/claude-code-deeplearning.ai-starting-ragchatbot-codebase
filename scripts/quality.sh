#!/bin/bash
# Code quality check script
# Run from the project root directory

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "Running code quality checks..."
echo "=============================="

# Check if we're in the right directory
if [ ! -f "pyproject.toml" ]; then
    echo -e "${RED}Error: Run this script from the project root directory${NC}"
    exit 1
fi

# Function to run a check
run_check() {
    local name=$1
    local cmd=$2
    echo -e "\n${YELLOW}Running $name...${NC}"
    if eval "$cmd"; then
        echo -e "${GREEN}$name passed${NC}"
        return 0
    else
        echo -e "${RED}$name failed${NC}"
        return 1
    fi
}

# Track failures
FAILED=0

# Run black (formatter check)
run_check "black (format check)" "uv run black --check backend/" || FAILED=1

# Run isort (import sorting check)
run_check "isort (import order check)" "uv run isort --check-only backend/" || FAILED=1

# Run flake8 (linting)
run_check "flake8 (linting)" "uv run flake8 backend/" || FAILED=1

# Summary
echo ""
echo "=============================="
if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}All quality checks passed!${NC}"
    exit 0
else
    echo -e "${RED}Some quality checks failed${NC}"
    echo "Run './scripts/format.sh' to auto-fix formatting issues"
    exit 1
fi
