#!/bin/bash

# SSL Configuration Test Suite
# Comprehensive testing for all SSL configurations and deployment types

set -e

# Script configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
TEST_LOG="$PROJECT_ROOT/logs/ssl-test.log"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Test configuration
TEST_DOMAIN="${TEST_DOMAIN:-localhost}"
TEST_PORT="${TEST_PORT:-443}"
TIMEOUT="${TIMEOUT:-10}"

# Logging function
log() {
    echo -e "$(date '+%Y-%m-%d %H:%M:%S') $1" | tee -a "$TEST_LOG"
}

print_header() {
    echo -e "${BLUE}╔══════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║                   SSL Configuration Test Suite                  ║${NC}"
    echo -e "${BLUE}║                      Comprehensive Testing                      ║${NC}"
    echo -e "${BLUE}╚══════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

print_success() { echo -e "${GREEN}✓ $1${NC}"; }
print_warning() { echo -e "${YELLOW}⚠ $1${NC}"; }
print_error() { echo -e "${RED}✗ $1${NC}"; }
print_info() { echo -e "${CYAN}ℹ $1${NC}"; }

# Create test directories
setup_test_environment() {
    mkdir -p "$(dirname "$TEST_LOG")"
    mkdir -p "$PROJECT_ROOT/test-results/ssl"
    
    print_info "Test environment setup complete"
    log "SSL Configuration Test Suite started"
}

# Test 1: Verify Traefik is running
test_traefik_running() {
    print_info "Test 1: Checking if Traefik is running..."
    
    if docker ps | grep -q "rendiff.*traefik"; then
        print_success "Traefik container is running"
        
        # Get container details
        local container_id=$(docker ps | grep "rendiff.*traefik" | awk '{print $1}')
        local container_name=$(docker ps | grep "rendiff.*traefik" | awk '{print $NF}')
        
        log "Traefik container: $container_name ($container_id)"
        return 0
    else
        print_error "Traefik container is not running"
        log "ERROR: Traefik container not found"
        return 1
    fi
}

# Test 2: Verify SSL certificates exist
test_certificates_exist() {
    print_info "Test 2: Checking SSL certificates..."
    
    local cert_file="$PROJECT_ROOT/traefik/certs/cert.crt"
    local key_file="$PROJECT_ROOT/traefik/certs/cert.key"
    
    local tests_passed=0
    local total_tests=2
    
    if [ -f "$cert_file" ]; then
        print_success "Certificate file exists: $cert_file"
        log "Certificate file found: $cert_file"
        ((tests_passed++))
    else
        print_error "Certificate file missing: $cert_file"
        log "ERROR: Certificate file not found: $cert_file"
    fi
    
    if [ -f "$key_file" ]; then
        print_success "Private key file exists: $key_file"
        log "Private key file found: $key_file"
        ((tests_passed++))
    else
        print_error "Private key file missing: $key_file"
        log "ERROR: Private key file not found: $key_file"
    fi
    
    if [ $tests_passed -eq $total_tests ]; then
        return 0
    else
        return 1
    fi
}

# Test 3: Validate certificate properties
test_certificate_validity() {
    print_info "Test 3: Validating certificate properties..."
    
    local cert_file="$PROJECT_ROOT/traefik/certs/cert.crt"
    
    if [ ! -f "$cert_file" ]; then
        print_error "Certificate file not found, skipping validation"
        return 1
    fi
    
    local tests_passed=0
    local total_tests=4
    
    # Test certificate format
    if openssl x509 -in "$cert_file" -noout >/dev/null 2>&1; then
        print_success "Certificate has valid format"
        log "Certificate format validation passed"
        ((tests_passed++))
    else
        print_error "Certificate format is invalid"
        log "ERROR: Certificate format validation failed"
    fi
    
    # Test certificate expiration
    if openssl x509 -in "$cert_file" -noout -checkend 86400 >/dev/null 2>&1; then
        print_success "Certificate is not expired"
        log "Certificate expiration check passed"
        ((tests_passed++))
    else
        print_error "Certificate is expired or expires soon"
        log "ERROR: Certificate expiration check failed"
    fi
    
    # Test key size
    local key_size=$(openssl x509 -in "$cert_file" -noout -pubkey | openssl pkey -pubin -text -noout | grep -o "Private-Key: ([0-9]* bit)" | grep -o "[0-9]*")
    if [ "$key_size" -ge 2048 ]; then
        print_success "Certificate key size is adequate ($key_size bits)"
        log "Certificate key size check passed: $key_size bits"
        ((tests_passed++))
    else
        print_error "Certificate key size is too small ($key_size bits)"
        log "ERROR: Certificate key size too small: $key_size bits"
    fi
    
    # Test Subject Alternative Names
    local san=$(openssl x509 -in "$cert_file" -noout -ext subjectAltName 2>/dev/null)
    if echo "$san" | grep -q "localhost"; then
        print_success "Certificate includes localhost in SAN"
        log "Subject Alternative Names check passed"
        ((tests_passed++))
    else
        print_warning "Certificate may not include required domains in SAN"
        log "WARNING: Subject Alternative Names check failed"
    fi
    
    if [ $tests_passed -eq $total_tests ]; then
        return 0
    else
        return 1
    fi
}

# Test 4: Test HTTP to HTTPS redirect
test_http_redirect() {
    print_info "Test 4: Testing HTTP to HTTPS redirect..."
    
    # Test HTTP redirect using curl
    local redirect_response=$(curl -s -o /dev/null -w "%{http_code}:%{redirect_url}" "http://$TEST_DOMAIN" --connect-timeout $TIMEOUT 2>/dev/null || echo "000:")
    local http_code=$(echo "$redirect_response" | cut -d: -f1)
    local redirect_url=$(echo "$redirect_response" | cut -d: -f2-)
    
    if [ "$http_code" = "301" ] || [ "$http_code" = "302" ] || [ "$http_code" = "307" ] || [ "$http_code" = "308" ]; then
        if echo "$redirect_url" | grep -q "https://"; then
            print_success "HTTP redirects to HTTPS (HTTP $http_code)"
            log "HTTP to HTTPS redirect test passed: $http_code -> $redirect_url"
            return 0
        else
            print_error "HTTP redirects but not to HTTPS (HTTP $http_code)"
            log "ERROR: HTTP redirect test failed: $http_code -> $redirect_url"
            return 1
        fi
    else
        print_error "HTTP does not redirect to HTTPS (HTTP $http_code)"
        log "ERROR: HTTP redirect test failed: HTTP $http_code"
        return 1
    fi
}

# Test 5: Test HTTPS connection
test_https_connection() {
    print_info "Test 5: Testing HTTPS connection..."
    
    local tests_passed=0
    local total_tests=3
    
    # Test basic HTTPS connectivity
    if echo | openssl s_client -connect "$TEST_DOMAIN:$TEST_PORT" -servername "$TEST_DOMAIN" >/dev/null 2>&1; then
        print_success "HTTPS connection successful"
        log "HTTPS connection test passed"
        ((tests_passed++))
    else
        print_error "HTTPS connection failed"
        log "ERROR: HTTPS connection test failed"
    fi
    
    # Test TLS version
    local tls_version=$(echo | openssl s_client -connect "$TEST_DOMAIN:$TEST_PORT" -servername "$TEST_DOMAIN" 2>/dev/null | grep "Protocol" | head -1 | awk '{print $3}')
    if [[ "$tls_version" =~ ^TLSv1\.[23]$ ]]; then
        print_success "TLS version is secure ($tls_version)"
        log "TLS version test passed: $tls_version"
        ((tests_passed++))
    else
        print_error "TLS version may be insecure ($tls_version)"
        log "ERROR: TLS version test failed: $tls_version"
    fi
    
    # Test cipher strength
    local cipher=$(echo | openssl s_client -connect "$TEST_DOMAIN:$TEST_PORT" -servername "$TEST_DOMAIN" 2>/dev/null | grep "Cipher" | head -1 | awk '{print $3}')
    if echo "$cipher" | grep -E "(AES|CHACHA)" >/dev/null; then
        print_success "Cipher is strong ($cipher)"
        log "Cipher strength test passed: $cipher"
        ((tests_passed++))
    else
        print_warning "Cipher may be weak ($cipher)"
        log "WARNING: Cipher strength test failed: $cipher"
    fi
    
    if [ $tests_passed -eq $total_tests ]; then
        return 0
    else
        return 1
    fi
}

# Test 6: Test API endpoints over HTTPS
test_api_endpoints() {
    print_info "Test 6: Testing API endpoints over HTTPS..."
    
    local tests_passed=0
    local total_tests=2
    
    # Test health endpoint
    local health_response=$(curl -s -k "https://$TEST_DOMAIN/api/v1/health" --connect-timeout $TIMEOUT 2>/dev/null || echo "")
    if echo "$health_response" | grep -q "status"; then
        print_success "Health endpoint accessible over HTTPS"
        log "Health endpoint test passed"
        ((tests_passed++))
    else
        print_error "Health endpoint not accessible over HTTPS"
        log "ERROR: Health endpoint test failed"
    fi
    
    # Test API documentation
    local docs_response=$(curl -s -k -o /dev/null -w "%{http_code}" "https://$TEST_DOMAIN/docs" --connect-timeout $TIMEOUT 2>/dev/null || echo "000")
    if [ "$docs_response" = "200" ]; then
        print_success "API documentation accessible over HTTPS"
        log "API documentation test passed"
        ((tests_passed++))
    else
        print_error "API documentation not accessible over HTTPS (HTTP $docs_response)"
        log "ERROR: API documentation test failed: HTTP $docs_response"
    fi
    
    if [ $tests_passed -eq $total_tests ]; then
        return 0
    else
        return 1
    fi
}

# Test 7: Test SSL security headers
test_security_headers() {
    print_info "Test 7: Testing SSL security headers..."
    
    local headers=$(curl -s -k -I "https://$TEST_DOMAIN" --connect-timeout $TIMEOUT 2>/dev/null || echo "")
    
    local tests_passed=0
    local total_tests=4
    
    # Test HSTS header
    if echo "$headers" | grep -i "strict-transport-security" >/dev/null; then
        print_success "HSTS header present"
        log "HSTS header test passed"
        ((tests_passed++))
    else
        print_warning "HSTS header missing"
        log "WARNING: HSTS header test failed"
    fi
    
    # Test X-Frame-Options
    if echo "$headers" | grep -i "x-frame-options" >/dev/null; then
        print_success "X-Frame-Options header present"
        log "X-Frame-Options header test passed"
        ((tests_passed++))
    else
        print_warning "X-Frame-Options header missing"
        log "WARNING: X-Frame-Options header test failed"
    fi
    
    # Test X-Content-Type-Options
    if echo "$headers" | grep -i "x-content-type-options" >/dev/null; then
        print_success "X-Content-Type-Options header present"
        log "X-Content-Type-Options header test passed"
        ((tests_passed++))
    else
        print_warning "X-Content-Type-Options header missing"
        log "WARNING: X-Content-Type-Options header test failed"
    fi
    
    # Test X-XSS-Protection
    if echo "$headers" | grep -i "x-xss-protection" >/dev/null; then
        print_success "X-XSS-Protection header present"
        log "X-XSS-Protection header test passed"
        ((tests_passed++))
    else
        print_warning "X-XSS-Protection header missing"
        log "WARNING: X-XSS-Protection header test failed"
    fi
    
    if [ $tests_passed -ge 2 ]; then
        return 0
    else
        return 1
    fi
}

# Test 8: Test SSL management scripts
test_ssl_scripts() {
    print_info "Test 8: Testing SSL management scripts..."
    
    local tests_passed=0
    local total_tests=3
    
    # Test enhanced SSL manager
    if [ -x "$PROJECT_ROOT/scripts/enhanced-ssl-manager.sh" ]; then
        print_success "Enhanced SSL manager script is executable"
        log "Enhanced SSL manager script test passed"
        ((tests_passed++))
    else
        print_error "Enhanced SSL manager script is not executable"
        log "ERROR: Enhanced SSL manager script test failed"
    fi
    
    # Test legacy SSL manager
    if [ -x "$PROJECT_ROOT/scripts/manage-ssl.sh" ]; then
        print_success "Legacy SSL manager script is executable"
        log "Legacy SSL manager script test passed"
        ((tests_passed++))
    else
        print_error "Legacy SSL manager script is not executable"
        log "ERROR: Legacy SSL manager script test failed"
    fi
    
    # Test SSL monitor script
    if [ -x "$PROJECT_ROOT/monitoring/ssl-monitor.sh" ]; then
        print_success "SSL monitor script is executable"
        log "SSL monitor script test passed"
        ((tests_passed++))
    else
        print_error "SSL monitor script is not executable"
        log "ERROR: SSL monitor script test failed"
    fi
    
    if [ $tests_passed -eq $total_tests ]; then
        return 0
    else
        return 1
    fi
}

# Generate comprehensive test report
generate_test_report() {
    local report_file="$PROJECT_ROOT/test-results/ssl/ssl-test-report-$(date +%Y%m%d-%H%M%S).txt"
    
    cat > "$report_file" << EOF
SSL Configuration Test Report
Generated: $(date)
Domain: $TEST_DOMAIN
Port: $TEST_PORT

=== Test Summary ===
Total Tests Run: $total_tests_run
Tests Passed: $total_tests_passed
Tests Failed: $total_tests_failed
Success Rate: $(( total_tests_passed * 100 / total_tests_run ))%

=== Detailed Results ===
EOF
    
    # Append detailed log
    echo "" >> "$report_file"
    echo "=== Detailed Test Log ===" >> "$report_file"
    cat "$TEST_LOG" >> "$report_file"
    
    print_info "Test report generated: $report_file"
}

# Main test execution
run_all_tests() {
    print_header
    setup_test_environment
    
    echo ""
    print_info "Running SSL Configuration Test Suite for $TEST_DOMAIN:$TEST_PORT"
    echo ""
    
    # Initialize counters
    total_tests_run=0
    total_tests_passed=0
    total_tests_failed=0
    
    # Run all tests
    local tests=(
        "test_traefik_running"
        "test_certificates_exist"
        "test_certificate_validity"
        "test_http_redirect"
        "test_https_connection"
        "test_api_endpoints"
        "test_security_headers"
        "test_ssl_scripts"
    )
    
    for test in "${tests[@]}"; do
        ((total_tests_run++))
        if $test; then
            ((total_tests_passed++))
        else
            ((total_tests_failed++))
        fi
        echo ""
    done
    
    # Generate summary
    echo ""
    print_info "=== Test Summary ==="
    echo -e "${CYAN}Total Tests Run:${NC} $total_tests_run"
    echo -e "${GREEN}Tests Passed:${NC} $total_tests_passed"
    echo -e "${RED}Tests Failed:${NC} $total_tests_failed"
    echo -e "${PURPLE}Success Rate:${NC} $(( total_tests_passed * 100 / total_tests_run ))%"
    
    # Generate report
    generate_test_report
    
    # Return appropriate exit code
    if [ $total_tests_failed -eq 0 ]; then
        print_success "All SSL configuration tests passed!"
        log "SSL configuration test suite completed successfully"
        return 0
    else
        print_error "Some SSL configuration tests failed"
        log "SSL configuration test suite completed with failures"
        return 1
    fi
}

# Show usage information
show_usage() {
    cat << EOF
Usage: $0 [OPTIONS]

SSL Configuration Test Suite

OPTIONS:
  --domain DOMAIN     Test domain (default: localhost)
  --port PORT         Test port (default: 443)
  --timeout SECONDS   Connection timeout (default: 10)
  --help, -h          Show this help message

EXAMPLES:
  $0                              # Test localhost:443
  $0 --domain api.example.com     # Test custom domain
  $0 --port 8443                  # Test custom port
  $0 --domain api.example.com --port 443 --timeout 15

EOF
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --domain)
            TEST_DOMAIN="$2"
            shift 2
            ;;
        --port)
            TEST_PORT="$2"
            shift 2
            ;;
        --timeout)
            TIMEOUT="$2"
            shift 2
            ;;
        --help|-h)
            show_usage
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

# Run the test suite
run_all_tests