#!/bin/bash

# Configuration Validation Script
# Validates all configurations, scripts, and environment files

set -e

# Script configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

print_header() {
    echo -e "${BLUE}╔══════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║                Configuration Validation Suite                    ║${NC}"
    echo -e "${BLUE}║                     Production Readiness Check                  ║${NC}"
    echo -e "${BLUE}╚══════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

print_success() { echo -e "${GREEN}✓ $1${NC}"; }
print_warning() { echo -e "${YELLOW}⚠ $1${NC}"; }
print_error() { echo -e "${RED}✗ $1${NC}"; }
print_info() { echo -e "${CYAN}ℹ $1${NC}"; }

# Validation counters
total_checks=0
passed_checks=0
failed_checks=0
warning_checks=0

# Run a validation check
run_check() {
    local check_name="$1"
    local check_command="$2"
    
    ((total_checks++))
    print_info "Checking: $check_name"
    
    if eval "$check_command" >/dev/null 2>&1; then
        print_success "$check_name"
        ((passed_checks++))
        return 0
    else
        print_error "$check_name"
        ((failed_checks++))
        return 1
    fi
}

# Run a validation check with warning
run_check_warning() {
    local check_name="$1"
    local check_command="$2"
    
    ((total_checks++))
    print_info "Checking: $check_name"
    
    if eval "$check_command" >/dev/null 2>&1; then
        print_success "$check_name"
        ((passed_checks++))
        return 0
    else
        print_warning "$check_name"
        ((warning_checks++))
        return 1
    fi
}

# Check Docker Compose file validity
validate_docker_compose() {
    print_info "Validating Docker Compose configurations..."
    
    # Check main compose file
    run_check "Main compose.yml syntax" \
        "docker-compose -f '$PROJECT_ROOT/compose.yml' config >/dev/null"
    
    # Check production compose file
    run_check "Production compose.prod.yml syntax" \
        "docker-compose -f '$PROJECT_ROOT/compose.prod.yml' config >/dev/null"
    
    # Check GenAI compose file with base
    run_check "GenAI docker-compose.genai.yml as override" \
        "docker-compose -f '$PROJECT_ROOT/compose.yml' -f '$PROJECT_ROOT/docker-compose.genai.yml' config >/dev/null"
    
    # Note: Main and production configs are designed to be used separately
    # They have conflicting service definitions by design
}

# Check script permissions and syntax
validate_scripts() {
    print_info "Validating scripts..."
    
    # Check script permissions
    run_check "setup.sh executable" \
        "test -x '$PROJECT_ROOT/setup.sh'"
    
    run_check "enhanced-ssl-manager.sh executable" \
        "test -x '$PROJECT_ROOT/scripts/enhanced-ssl-manager.sh'"
    
    run_check "test-ssl-configurations.sh executable" \
        "test -x '$PROJECT_ROOT/scripts/test-ssl-configurations.sh'"
    
    run_check "ssl-monitor.sh executable" \
        "test -x '$PROJECT_ROOT/monitoring/ssl-monitor.sh'"
    
    # Check shell script syntax
    local scripts=(
        "$PROJECT_ROOT/setup.sh"
        "$PROJECT_ROOT/scripts/enhanced-ssl-manager.sh"
        "$PROJECT_ROOT/scripts/test-ssl-configurations.sh"
        "$PROJECT_ROOT/monitoring/ssl-monitor.sh"
    )
    
    for script in "${scripts[@]}"; do
        if [ -f "$script" ]; then
            run_check "$(basename "$script") syntax" \
                "bash -n '$script'"
        fi
    done
}

# Check file structure and organization
validate_file_structure() {
    print_info "Validating file structure..."
    
    # Check required directories
    run_check "traefik directory exists" \
        "test -d '$PROJECT_ROOT/traefik'"
    
    run_check "scripts directory exists" \
        "test -d '$PROJECT_ROOT/scripts'"
    
    run_check "docs directory exists" \
        "test -d '$PROJECT_ROOT/docs'"
    
    run_check "config directory exists" \
        "test -d '$PROJECT_ROOT/config'"
    
    # Check required files
    run_check "README.md exists" \
        "test -f '$PROJECT_ROOT/README.md'"
    
    run_check ".env.example exists" \
        "test -f '$PROJECT_ROOT/.env.example'"
    
    run_check ".gitignore exists" \
        "test -f '$PROJECT_ROOT/.gitignore'"
    
    # Check Traefik configuration files
    run_check "traefik.yml exists" \
        "test -f '$PROJECT_ROOT/traefik/traefik.yml'"
    
    run_check "traefik dynamic.yml exists" \
        "test -f '$PROJECT_ROOT/traefik/dynamic.yml'"
}

# Check for security issues
validate_security() {
    print_info "Validating security configurations..."
    
    # Check for committed secrets
    run_check "No .env files committed" \
        "! find '$PROJECT_ROOT' -name '.env' -not -path '*/node_modules/*' | grep -q ."
    
    # Check CORS configuration
    run_check_warning "CORS not set to wildcard" \
        "! grep -r 'CORS.*\\*' '$PROJECT_ROOT' --exclude-dir=.git"
    
    # Check for hardcoded passwords
    run_check "No hardcoded passwords" \
        "! grep -ri 'password.*=' '$PROJECT_ROOT' --include='*.yml' --include='*.yaml' | grep -v 'your_.*_password' | grep -v 'example' | grep -v '\${' | grep -q ."
    
    # Check SSL certificate files are ignored
    run_check "SSL certificates in .gitignore" \
        "grep -q '\\*.crt' '$PROJECT_ROOT/.gitignore' && grep -q '\\*.key' '$PROJECT_ROOT/.gitignore'"
    
    # Check file permissions
    run_check "No world-writable files" \
        "! find '$PROJECT_ROOT' -type f -perm -002 | grep -q ."
}

# Check environment configuration
validate_environment() {
    print_info "Validating environment configuration..."
    
    # Check .env.example format
    run_check ".env.example has required variables" \
        "grep -q 'POSTGRES_PASSWORD' '$PROJECT_ROOT/.env.example' && grep -q 'DOMAIN_NAME' '$PROJECT_ROOT/.env.example'"
    
    # Check for port consistency
    run_check "Consistent API port in .env.example" \
        "grep -q 'API_PORT=8000' '$PROJECT_ROOT/.env.example'"
    
    # Check external URL format
    run_check "HTTPS external URL in .env.example" \
        "grep -q 'EXTERNAL_URL=https://' '$PROJECT_ROOT/.env.example'"
}

# Check documentation consistency
validate_documentation() {
    print_info "Validating documentation..."
    
    # Check for broken internal links
    run_check_warning "Documentation files exist" \
        "test -f '$PROJECT_ROOT/docs/SETUP.md' && test -f '$PROJECT_ROOT/docs/API.md'"
    
    # Check port consistency in documentation
    run_check_warning "Consistent ports in README" \
        "! grep -q '8080' '$PROJECT_ROOT/README.md'"
    
    # Check HTTPS references in production docs
    run_check_warning "HTTPS references in documentation" \
        "grep -q 'https://localhost' '$PROJECT_ROOT/docs/SETUP.md'"
}

# Check Traefik configuration
validate_traefik() {
    print_info "Validating Traefik configuration..."
    
    # Check static configuration
    run_check "Traefik static config valid YAML" \
        "python3 -c 'import yaml; yaml.safe_load(open(\"$PROJECT_ROOT/traefik/traefik.yml\"))'"
    
    # Check dynamic configuration
    run_check "Traefik dynamic config valid YAML" \
        "python3 -c 'import yaml; yaml.safe_load(open(\"$PROJECT_ROOT/traefik/dynamic.yml\"))'"
    
    # Check certificate paths
    run_check "Certificate paths in dynamic config" \
        "grep -q '/etc/traefik/certs' '$PROJECT_ROOT/traefik/dynamic.yml'"
}

# Main validation function
main() {
    print_header
    
    # Run all validation categories
    validate_file_structure
    echo ""
    
    validate_docker_compose
    echo ""
    
    validate_scripts
    echo ""
    
    validate_security
    echo ""
    
    validate_environment
    echo ""
    
    validate_documentation
    echo ""
    
    validate_traefik
    echo ""
    
    # Print summary
    print_info "=== Validation Summary ==="
    echo -e "${CYAN}Total Checks:${NC} $total_checks"
    echo -e "${GREEN}Passed:${NC} $passed_checks"
    echo -e "${RED}Failed:${NC} $failed_checks"
    echo -e "${YELLOW}Warnings:${NC} $warning_checks"
    
    local success_rate=$(( (passed_checks * 100) / total_checks ))
    echo -e "${CYAN}Success Rate:${NC} $success_rate%"
    
    echo ""
    if [ $failed_checks -eq 0 ]; then
        print_success "All critical validations passed! Repository is production-ready."
        if [ $warning_checks -gt 0 ]; then
            print_warning "$warning_checks warnings found - review recommended but not blocking."
        fi
        return 0
    else
        print_error "$failed_checks critical issues found - must be fixed before production deployment."
        return 1
    fi
}

# Run main function
main "$@"