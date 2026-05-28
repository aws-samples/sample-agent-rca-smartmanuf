#!/bin/bash
#
# Setup script for domain-specific configuration.
#
# This script copies domain-specific templates to the agent directory,
# allowing customers to use pre-configured schemas for their industry.
#
# Usage:
#   ./scripts/setup_domain.sh <domain>
#   ./scripts/setup_domain.sh --list
#
# Examples:
#   ./scripts/setup_domain.sh manufacturing   # Pharma/manufacturing (5M, QQOCQPC)
#   ./scripts/setup_domain.sh generic         # Generic template (customizable)
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
TEMPLATES_DIR="$PROJECT_ROOT/templates"
TARGET_DIR="$PROJECT_ROOT/agent/state"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_header() {
    echo ""
    echo -e "${BLUE}================================================================${NC}"
    echo -e "${BLUE}  RCA Agent - Domain Setup${NC}"
    echo -e "${BLUE}================================================================${NC}"
    echo ""
}

list_domains() {
    echo -e "${YELLOW}Available domains:${NC}"
    echo ""
    for dir in "$TEMPLATES_DIR"/*/; do
        domain=$(basename "$dir")
        if [[ -f "$dir/investigation_state.py" ]]; then
            # Extract domain description from the file
            desc=$(head -20 "$dir/investigation_state.py" | grep -E "^(Domain:|Typed dataclasses)" | head -1 | sed 's/^[# ]*//')
            echo -e "  ${GREEN}$domain${NC}"
            if [[ -n "$desc" ]]; then
                echo "      $desc"
            fi
        fi
    done
    echo ""
    echo "Usage: $0 <domain>"
    echo ""
}

setup_domain() {
    local domain="$1"
    local template_dir="$TEMPLATES_DIR/$domain"

    if [[ ! -d "$template_dir" ]]; then
        echo -e "${RED}Error: Domain '$domain' not found.${NC}"
        echo ""
        list_domains
        exit 1
    fi

    if [[ ! -f "$template_dir/investigation_state.py" ]]; then
        echo -e "${RED}Error: Template file not found for domain '$domain'.${NC}"
        exit 1
    fi

    print_header

    echo -e "Domain: ${GREEN}$domain${NC}"
    echo ""

    # Backup existing file if it exists
    if [[ -f "$TARGET_DIR/investigation_state.py" ]]; then
        backup_file="$TARGET_DIR/investigation_state.py.backup.$(date +%Y%m%d_%H%M%S)"
        echo -e "${YELLOW}Backing up existing file to:${NC}"
        echo "  $backup_file"
        cp "$TARGET_DIR/investigation_state.py" "$backup_file"
        echo ""
    fi

    # Copy template
    echo "Installing domain template..."
    cp "$template_dir/investigation_state.py" "$TARGET_DIR/investigation_state.py"
    echo -e "${GREEN}✓ Copied investigation_state.py${NC}"

    # Copy any additional template files (if they exist)
    for file in "$template_dir"/*.py; do
        if [[ -f "$file" && "$(basename "$file")" != "investigation_state.py" ]]; then
            filename=$(basename "$file")
            cp "$file" "$TARGET_DIR/$filename"
            echo -e "${GREEN}✓ Copied $filename${NC}"
        fi
    done

    echo ""
    echo -e "${GREEN}================================================================${NC}"
    echo -e "${GREEN}  Setup complete!${NC}"
    echo -e "${GREEN}================================================================${NC}"
    echo ""
    echo "Next steps:"
    echo "  1. Review agent/state/investigation_state.py"
    echo "  2. Customize fields if needed for your specific use case"
    echo "  3. Rebuild and deploy: ./scripts/build_and_push.sh"
    echo ""
}

# Main
case "${1:-}" in
    --list|-l)
        print_header
        list_domains
        ;;
    --help|-h)
        print_header
        echo "Setup domain-specific configuration for the RCA agent."
        echo ""
        echo "Usage:"
        echo "  $0 <domain>     Install domain template"
        echo "  $0 --list       List available domains"
        echo "  $0 --help       Show this help"
        echo ""
        list_domains
        ;;
    "")
        print_header
        echo -e "${YELLOW}No domain specified.${NC}"
        echo ""
        list_domains
        exit 1
        ;;
    *)
        setup_domain "$1"
        ;;
esac
