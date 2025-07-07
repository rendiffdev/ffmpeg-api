#!/bin/bash
# Production Configuration Validation Script

set -e

echo "🔍 Validating Production Configuration..."
echo "========================================"

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Validation counters
ERRORS=0
WARNINGS=0

# Function to check if a file exists
check_file() {
    if [ -f "$1" ]; then
        echo -e "${GREEN}✓${NC} $2"
        return 0
    else
        echo -e "${RED}✗${NC} $2"
        ((ERRORS++))
        return 1
    fi
}

# Function to check environment variable
check_env() {
    if [ -z "${!1}" ]; then
        echo -e "${RED}✗${NC} $1 is not set"
        ((ERRORS++))
        return 1
    else
        if [ "$2" = "secure" ]; then
            echo -e "${GREEN}✓${NC} $1 is set (hidden)"
        else
            echo -e "${GREEN}✓${NC} $1 is set: ${!1}"
        fi
        return 0
    fi
}

# Function to check for default values
check_not_default() {
    if [ "${!1}" = "$2" ]; then
        echo -e "${RED}✗${NC} $1 is using default value: $2"
        ((ERRORS++))
        return 1
    else
        echo -e "${GREEN}✓${NC} $1 is not using default value"
        return 0
    fi
}

# Function to validate password strength
check_password_strength() {
    local pass="${!1}"
    if [ -z "$pass" ]; then
        echo -e "${RED}✗${NC} $1 is not set"
        ((ERRORS++))
        return 1
    fi
    
    if [ ${#pass} -lt 16 ]; then
        echo -e "${RED}✗${NC} $1 is too short (minimum 16 characters)"
        ((ERRORS++))
        return 1
    fi
    
    echo -e "${GREEN}✓${NC} $1 meets minimum length requirement"
    return 0
}

echo ""
echo "1. Checking Required Files"
echo "--------------------------"
check_file ".env" "Environment configuration file exists"
check_file "docker-compose.yml" "Docker Compose file exists"
check_file "config/storage.yml" "Storage configuration exists"

echo ""
echo "2. Loading Environment Variables"
echo "--------------------------------"
if [ -f .env ]; then
    set -a
    source .env
    set +a
    echo -e "${GREEN}✓${NC} Environment variables loaded"
else
    echo -e "${RED}✗${NC} Cannot load .env file"
    exit 1
fi

echo ""
echo "3. Checking Database Configuration"
echo "----------------------------------"
check_env "POSTGRES_PASSWORD" "secure"
check_password_strength "POSTGRES_PASSWORD"
check_not_default "POSTGRES_PASSWORD" "changeme"
check_not_default "POSTGRES_PASSWORD" "your_secure_password_here"

echo ""
echo "4. Checking Security Configuration"
echo "----------------------------------"
check_env "ADMIN_API_KEYS" "secure"
check_not_default "ADMIN_API_KEYS" "your_admin_key_1,your_admin_key_2"

if [ -n "$ADMIN_API_KEYS" ]; then
    IFS=',' read -ra KEYS <<< "$ADMIN_API_KEYS"
    if [ ${#KEYS[@]} -lt 1 ]; then
        echo -e "${RED}✗${NC} No admin API keys configured"
        ((ERRORS++))
    else
        echo -e "${GREEN}✓${NC} ${#KEYS[@]} admin API keys configured"
        for key in "${KEYS[@]}"; do
            if [ ${#key} -lt 32 ]; then
                echo -e "${YELLOW}⚠${NC}  Warning: API key is shorter than recommended 32 characters"
                ((WARNINGS++))
            fi
        done
    fi
fi

echo ""
echo "5. Checking Monitoring Configuration"
echo "------------------------------------"
check_env "GRAFANA_PASSWORD" "secure"
check_not_default "GRAFANA_PASSWORD" "admin"
check_not_default "GRAFANA_PASSWORD" "changeme"
check_not_default "GRAFANA_PASSWORD" "your_grafana_password_here"

echo ""
echo "6. Checking API Configuration"
echo "-----------------------------"
if [ "$ENABLE_API_KEYS" != "true" ]; then
    echo -e "${RED}✗${NC} API key authentication is disabled"
    ((ERRORS++))
else
    echo -e "${GREEN}✓${NC} API key authentication is enabled"
fi

if [ "$DEBUG" = "true" ]; then
    echo -e "${YELLOW}⚠${NC}  Warning: DEBUG mode is enabled"
    ((WARNINGS++))
else
    echo -e "${GREEN}✓${NC} DEBUG mode is disabled"
fi

echo ""
echo "7. Checking Storage Configuration"
echo "---------------------------------"
if [ -f "config/storage.yml" ]; then
    if grep -q "your-bucket-name" config/storage.yml 2>/dev/null; then
        echo -e "${YELLOW}⚠${NC}  Warning: Storage configuration contains placeholder values"
        ((WARNINGS++))
    else
        echo -e "${GREEN}✓${NC} Storage configuration appears to be customized"
    fi
fi

echo ""
echo "8. Checking Docker Configuration"
echo "--------------------------------"
if docker compose config > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} Docker Compose configuration is valid"
else
    echo -e "${RED}✗${NC} Docker Compose configuration has errors"
    ((ERRORS++))
fi

echo ""
echo "9. Checking Network Security"
echo "----------------------------"
if [ "$ENABLE_IP_WHITELIST" = "true" ]; then
    echo -e "${GREEN}✓${NC} IP whitelisting is enabled"
    if [ -n "$IP_WHITELIST" ]; then
        echo -e "${GREEN}✓${NC} IP whitelist configured: $IP_WHITELIST"
    else
        echo -e "${RED}✗${NC} IP whitelist is empty"
        ((ERRORS++))
    fi
else
    echo -e "${YELLOW}⚠${NC}  Warning: IP whitelisting is disabled"
    ((WARNINGS++))
fi

echo ""
echo "10. Checking CORS Configuration"
echo "-------------------------------"
if [ "$CORS_ORIGINS" = "*" ]; then
    echo -e "${YELLOW}⚠${NC}  Warning: CORS allows all origins (*)"
    ((WARNINGS++))
else
    echo -e "${GREEN}✓${NC} CORS origins are restricted"
fi

echo ""
echo "========================================"
echo "Validation Summary"
echo "========================================"
echo -e "Errors:   ${RED}$ERRORS${NC}"
echo -e "Warnings: ${YELLOW}$WARNINGS${NC}"
echo ""

if [ $ERRORS -gt 0 ]; then
    echo -e "${RED}❌ Production validation FAILED${NC}"
    echo "Please fix the errors above before deploying to production."
    exit 1
elif [ $WARNINGS -gt 0 ]; then
    echo -e "${YELLOW}⚠️  Production validation passed with warnings${NC}"
    echo "Consider addressing the warnings for better security."
    exit 0
else
    echo -e "${GREEN}✅ Production validation PASSED${NC}"
    echo "Your configuration appears to be production-ready!"
    exit 0
fi