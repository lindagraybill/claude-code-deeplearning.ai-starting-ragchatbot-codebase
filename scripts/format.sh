#!/bin/bash
# Auto-format code script
# Run from the project root directory

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo "Auto-formatting code..."
echo "======================="

# Check if we're in the right directory
if [ ! -f "pyproject.toml" ]; then
    echo -e "${RED}Error: Run this script from the project root directory${NC}"
    exit 1
fi

# Run isort first (sorts imports)
echo -e "\n${YELLOW}Running isort...${NC}"
uv run isort backend/
echo -e "${GREEN}Imports sorted${NC}"

# Run black (formats code)
echo -e "\n${YELLOW}Running black...${NC}"
uv run black backend/
echo -e "${GREEN}Code formatted${NC}"

echo ""
echo "======================="
echo -e "${GREEN}Formatting complete!${NC}"
