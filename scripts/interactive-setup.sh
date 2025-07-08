#!/bin/bash

# Interactive Setup Script for FFmpeg API
# This script collects user preferences and generates secure configurations

set -e

# Color codes for better UX
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration file paths
ENV_FILE=".env"
BACKUP_ENV=".env.backup.$(date +%Y%m%d_%H%M%S)"

# Utility functions
print_header() {
    echo -e "${BLUE}=================================${NC}"
    echo -e "${BLUE}  FFmpeg API - Interactive Setup${NC}"
    echo -e "${BLUE}=================================${NC}"
    echo ""
}

print_section() {
    echo -e "${CYAN}--- $1 ---${NC}"
    echo ""
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

# Function to prompt for user input with validation
prompt_input() {
    local prompt="$1"
    local default="$2"
    local validation="$3"
    local secret="$4"
    local value=""
    
    while true; do
        if [ -n "$default" ]; then
            echo -ne "${prompt} [${default}]: "
        else
            echo -ne "${prompt}: "
        fi
        
        if [ "$secret" = "true" ]; then
            read -s value
            echo
        else
            read value
        fi
        
        # Use default if empty
        if [ -z "$value" ] && [ -n "$default" ]; then
            value="$default"
        fi
        
        # Validate input if validation function provided
        if [ -n "$validation" ]; then
            if $validation "$value"; then
                echo "$value"
                return 0
            else
                print_error "Invalid input. Please try again."
                continue
            fi
        else
            echo "$value"
            return 0
        fi
    done
}

# Function to generate secure password
generate_password() {
    local length=${1:-32}
    openssl rand -base64 $length | tr -d "=+/" | cut -c1-$length
}

# Function to generate API key
generate_api_key() {
    local length=${1:-32}
    openssl rand -hex $length | cut -c1-$length
}

# Validation functions
validate_port() {
    local port="$1"
    if [[ "$port" =~ ^[0-9]+$ ]] && [ "$port" -ge 1024 ] && [ "$port" -le 65535 ]; then
        return 0
    else
        print_error "Port must be a number between 1024 and 65535"
        return 1
    fi
}

validate_email() {
    local email="$1"
    if [[ "$email" =~ ^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$ ]]; then
        return 0
    else
        print_error "Please enter a valid email address"
        return 1
    fi
}

validate_url() {
    local url="$1"
    if [[ "$url" =~ ^https?://[a-zA-Z0-9.-]+([:]?[0-9]+)?(/.*)?$ ]]; then
        return 0
    else
        print_error "Please enter a valid URL (http:// or https://)"
        return 1
    fi
}

validate_non_empty() {
    local value="$1"
    if [ -n "$value" ]; then
        return 0
    else
        print_error "This field cannot be empty"
        return 1
    fi
}

# Function to backup existing .env file
backup_env() {
    if [ -f "$ENV_FILE" ]; then
        cp "$ENV_FILE" "$BACKUP_ENV"
        print_warning "Existing .env file backed up to $BACKUP_ENV"
    fi
}

# Function to write configuration to .env file
write_env_config() {
    cat > "$ENV_FILE" << EOF
# FFmpeg API Configuration
# Generated on $(date)
# Backup: $BACKUP_ENV

# === BASIC CONFIGURATION ===
API_HOST=$API_HOST
API_PORT=$API_PORT
API_WORKERS=$API_WORKERS
EXTERNAL_URL=$EXTERNAL_URL

# === DATABASE CONFIGURATION ===
DATABASE_TYPE=$DATABASE_TYPE
EOF

    if [ "$DATABASE_TYPE" = "postgresql" ]; then
        cat >> "$ENV_FILE" << EOF
POSTGRES_HOST=$POSTGRES_HOST
POSTGRES_PORT=$POSTGRES_PORT
POSTGRES_DB=$POSTGRES_DB
POSTGRES_USER=$POSTGRES_USER
POSTGRES_PASSWORD=$POSTGRES_PASSWORD
DATABASE_URL=postgresql://$POSTGRES_USER:$POSTGRES_PASSWORD@$POSTGRES_HOST:$POSTGRES_PORT/$POSTGRES_DB
EOF
    else
        cat >> "$ENV_FILE" << EOF
DATABASE_URL=sqlite+aiosqlite:///data/rendiff.db
EOF
    fi

    cat >> "$ENV_FILE" << EOF

# === REDIS CONFIGURATION ===
REDIS_HOST=$REDIS_HOST
REDIS_PORT=$REDIS_PORT
REDIS_URL=redis://$REDIS_HOST:$REDIS_PORT/0

# === SECURITY CONFIGURATION ===
ADMIN_API_KEYS=$ADMIN_API_KEYS
GRAFANA_PASSWORD=$GRAFANA_PASSWORD
ENABLE_API_KEYS=$ENABLE_API_KEYS

# === RENDIFF API KEYS ===
RENDIFF_API_KEYS=$RENDIFF_API_KEYS

# === STORAGE CONFIGURATION ===
STORAGE_PATH=$STORAGE_PATH
STORAGE_DEFAULT_BACKEND=$STORAGE_DEFAULT_BACKEND
EOF

    if [ "$SETUP_S3" = "true" ]; then
        cat >> "$ENV_FILE" << EOF

# === AWS S3 CONFIGURATION ===
AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY
AWS_S3_BUCKET=$AWS_S3_BUCKET
AWS_S3_REGION=$AWS_S3_REGION
AWS_S3_ENDPOINT=$AWS_S3_ENDPOINT
EOF
    fi

    if [ "$SETUP_AZURE" = "true" ]; then
        cat >> "$ENV_FILE" << EOF

# === AZURE STORAGE CONFIGURATION ===
AZURE_STORAGE_ACCOUNT=$AZURE_STORAGE_ACCOUNT
AZURE_STORAGE_KEY=$AZURE_STORAGE_KEY
AZURE_CONTAINER=$AZURE_CONTAINER
EOF
    fi

    if [ "$SETUP_GCP" = "true" ]; then
        cat >> "$ENV_FILE" << EOF

# === GCP STORAGE CONFIGURATION ===
GCP_PROJECT_ID=$GCP_PROJECT_ID
GCS_BUCKET=$GCS_BUCKET
GOOGLE_APPLICATION_CREDENTIALS=/config/gcp-key.json
EOF
    fi

    cat >> "$ENV_FILE" << EOF

# === MONITORING CONFIGURATION ===
ENABLE_MONITORING=$ENABLE_MONITORING
PROMETHEUS_PORT=$PROMETHEUS_PORT
GRAFANA_PORT=$GRAFANA_PORT

# === RESOURCE LIMITS ===
MAX_UPLOAD_SIZE=$MAX_UPLOAD_SIZE
MAX_CONCURRENT_JOBS_PER_KEY=$MAX_CONCURRENT_JOBS_PER_KEY
MAX_JOB_DURATION=$MAX_JOB_DURATION

# === WORKER CONFIGURATION ===
CPU_WORKERS=$CPU_WORKERS
GPU_WORKERS=$GPU_WORKERS
WORKER_CONCURRENCY=$WORKER_CONCURRENCY

# === SSL/TLS CONFIGURATION ===
SSL_ENABLED=$SSL_ENABLED
SSL_TYPE=$SSL_TYPE
DOMAIN_NAME=$DOMAIN_NAME
CERTBOT_EMAIL=$CERTBOT_EMAIL
LETSENCRYPT_STAGING=$LETSENCRYPT_STAGING

# === ADDITIONAL SETTINGS ===
LOG_LEVEL=$LOG_LEVEL
CORS_ORIGINS=$CORS_ORIGINS
EOF
}

# Function to set up new API keys
setup_new_api_keys() {
    echo ""
    echo "Setting up new Rendiff API keys..."
    echo ""
    
    # Ask about existing keys deletion
    if [ -f ".env" ] && grep -q "RENDIFF_API_KEYS" .env 2>/dev/null; then
        print_warning "Existing Rendiff API keys found in current configuration."
        echo ""
        echo "Security Options:"
        echo "1) Delete existing keys and generate new ones (Recommended for security)"
        echo "2) Keep existing keys and add new ones"
        echo "3) Cancel and keep current keys"
        echo ""
        
        while true; do
            security_choice=$(prompt_input "Security option" "1")
            case $security_choice in
                1)
                    print_warning "Existing API keys will be invalidated and replaced"
                    REPLACE_EXISTING_KEYS=true
                    break
                    ;;
                2)
                    print_info "New keys will be added to existing ones"
                    REPLACE_EXISTING_KEYS=false
                    break
                    ;;
                3)
                    echo "Keeping existing API keys..."
                    RENDIFF_API_KEYS=$(grep "RENDIFF_API_KEYS=" .env 2>/dev/null | cut -d= -f2 || echo "")
                    return 0
                    ;;
                *)
                    print_error "Please choose 1, 2, or 3"
                    ;;
            esac
        done
    else
        REPLACE_EXISTING_KEYS=true
    fi
    
    # Ask how many API keys to generate
    echo ""
    NUM_API_KEYS=$(prompt_input "Number of Rendiff API keys to generate" "3")
    
    # Validate number
    if ! [[ "$NUM_API_KEYS" =~ ^[0-9]+$ ]] || [ "$NUM_API_KEYS" -lt 1 ] || [ "$NUM_API_KEYS" -gt 20 ]; then
        print_error "Please enter a number between 1 and 20"
        NUM_API_KEYS=3
    fi
    
    # Ask for key descriptions/labels
    echo ""
    echo "You can assign labels to your API keys for easier management:"
    echo "(Press Enter to use default labels)"
    echo ""
    
    local api_keys=()
    local api_key_labels=()
    
    for i in $(seq 1 $NUM_API_KEYS); do
        local default_label="api_key_$i"
        local label=$(prompt_input "Label for API key $i" "$default_label")
        local key=$(generate_api_key 32)
        
        api_keys+=("$key")
        api_key_labels+=("$label")
        
        print_success "Generated API key $i: $label"
    done
    
    # Combine existing keys if not replacing
    if [ "$REPLACE_EXISTING_KEYS" = "false" ] && [ -f ".env" ]; then
        local existing_keys=$(grep "RENDIFF_API_KEYS=" .env 2>/dev/null | cut -d= -f2 | tr ',' '\n' | grep -v '^$' || echo "")
        if [ -n "$existing_keys" ]; then
            while IFS= read -r existing_key; do
                api_keys+=("$existing_key")
            done <<< "$existing_keys"
        fi
    fi
    
    # Create comma-separated list
    RENDIFF_API_KEYS=$(IFS=','; echo "${api_keys[*]}")
    
    # Save key labels for documentation
    RENDIFF_API_KEY_LABELS=$(IFS=','; echo "${api_key_labels[*]}")
    
    echo ""
    print_success "Rendiff API keys configured successfully"
    echo ""
}

# Function to import existing API keys
import_existing_api_keys() {
    echo ""
    echo "Import existing Rendiff API keys..."
    echo ""
    echo "You can import API keys in the following ways:"
    echo "1) Enter keys manually (one by one)"
    echo "2) Paste comma-separated keys"
    echo "3) Import from file"
    echo ""
    
    while true; do
        import_choice=$(prompt_input "Import method" "1")
        case $import_choice in
            1)
                import_keys_manually
                break
                ;;
            2)
                import_keys_comma_separated
                break
                ;;
            3)
                import_keys_from_file
                break
                ;;
            *)
                print_error "Please choose 1, 2, or 3"
                ;;
        esac
    done
}

# Function to import keys manually
import_keys_manually() {
    echo ""
    echo "Enter your existing API keys one by one (press Enter with empty key to finish):"
    echo ""
    
    local api_keys=()
    local counter=1
    
    while true; do
        local key=$(prompt_input "API key $counter (or press Enter to finish)" "")
        
        if [ -z "$key" ]; then
            break
        fi
        
        # Validate key format (basic validation)
        if [ ${#key} -lt 16 ]; then
            print_error "API key too short (minimum 16 characters). Please try again."
            continue
        fi
        
        api_keys+=("$key")
        print_success "API key $counter added"
        ((counter++))
        
        if [ $counter -gt 20 ]; then
            print_warning "Maximum 20 keys reached"
            break
        fi
    done
    
    if [ ${#api_keys[@]} -eq 0 ]; then
        print_error "No API keys entered"
        RENDIFF_API_KEYS=""
        return 1
    fi
    
    RENDIFF_API_KEYS=$(IFS=','; echo "${api_keys[*]}")
    print_success "${#api_keys[@]} API keys imported successfully"
}

# Function to import comma-separated keys
import_keys_comma_separated() {
    echo ""
    echo "Paste your comma-separated API keys:"
    echo "(Format: key1,key2,key3)"
    echo ""
    
    local keys_input=$(prompt_input "API keys" "" "validate_non_empty")
    
    # Split by comma and validate
    IFS=',' read -ra api_keys <<< "$keys_input"
    local valid_keys=()
    
    for key in "${api_keys[@]}"; do
        # Trim whitespace
        key=$(echo "$key" | xargs)
        
        if [ ${#key} -lt 16 ]; then
            print_warning "Skipping invalid key (too short): ${key:0:8}..."
            continue
        fi
        
        valid_keys+=("$key")
    done
    
    if [ ${#valid_keys[@]} -eq 0 ]; then
        print_error "No valid API keys found"
        RENDIFF_API_KEYS=""
        return 1
    fi
    
    RENDIFF_API_KEYS=$(IFS=','; echo "${valid_keys[*]}")
    print_success "${#valid_keys[@]} API keys imported successfully"
}

# Function to import keys from file
import_keys_from_file() {
    echo ""
    local file_path=$(prompt_input "Path to API keys file" "")
    
    if [ ! -f "$file_path" ]; then
        print_error "File not found: $file_path"
        RENDIFF_API_KEYS=""
        return 1
    fi
    
    # Read keys from file (one per line or comma-separated)
    local file_content=$(cat "$file_path" 2>/dev/null)
    local api_keys=()
    
    # Try comma-separated first
    if [[ "$file_content" == *","* ]]; then
        IFS=',' read -ra keys_array <<< "$file_content"
    else
        # Try line-separated
        IFS=$'\n' read -ra keys_array <<< "$file_content"
    fi
    
    # Validate each key
    for key in "${keys_array[@]}"; do
        key=$(echo "$key" | xargs)  # Trim whitespace
        
        if [ ${#key} -lt 16 ]; then
            continue
        fi
        
        api_keys+=("$key")
    done
    
    if [ ${#api_keys[@]} -eq 0 ]; then
        print_error "No valid API keys found in file"
        RENDIFF_API_KEYS=""
        return 1
    fi
    
    RENDIFF_API_KEYS=$(IFS=','; echo "${api_keys[*]}")
    print_success "${#api_keys[@]} API keys imported from file"
}

# Main setup function
main_setup() {
    print_header
    
    echo "This interactive setup will guide you through configuring your FFmpeg API deployment."
    echo "All sensitive data will be securely generated or collected."
    echo ""
    
    # Backup existing configuration
    backup_env
    
    # === BASIC CONFIGURATION ===
    print_section "Basic Configuration"
    
    API_HOST=$(prompt_input "API Host" "0.0.0.0")
    API_PORT=$(prompt_input "API Port" "8000" "validate_port")
    API_WORKERS=$(prompt_input "Number of API Workers" "4")
    EXTERNAL_URL=$(prompt_input "External URL" "http://localhost:$API_PORT" "validate_url")
    
    # === DATABASE CONFIGURATION ===
    print_section "Database Configuration"
    
    echo "Choose your database backend:"
    echo "1) PostgreSQL (Recommended for production)"
    echo "2) SQLite (Good for development/testing)"
    echo ""
    
    while true; do
        choice=$(prompt_input "Database choice" "1")
        case $choice in
            1)
                DATABASE_TYPE="postgresql"
                break
                ;;
            2)
                DATABASE_TYPE="sqlite"
                break
                ;;
            *)
                print_error "Please choose 1 or 2"
                ;;
        esac
    done
    
    if [ "$DATABASE_TYPE" = "postgresql" ]; then
        POSTGRES_HOST=$(prompt_input "PostgreSQL Host" "postgres")
        POSTGRES_PORT=$(prompt_input "PostgreSQL Port" "5432" "validate_port")
        POSTGRES_DB=$(prompt_input "Database Name" "ffmpeg_api" "validate_non_empty")
        POSTGRES_USER=$(prompt_input "Database User" "ffmpeg_user" "validate_non_empty")
        
        echo ""
        echo "Choose password option:"
        echo "1) Generate secure password automatically (Recommended)"
        echo "2) Enter custom password"
        echo ""
        
        while true; do
            pass_choice=$(prompt_input "Password choice" "1")
            case $pass_choice in
                1)
                    POSTGRES_PASSWORD=$(generate_password 32)
                    print_success "Secure password generated"
                    break
                    ;;
                2)
                    POSTGRES_PASSWORD=$(prompt_input "Database Password" "" "validate_non_empty" "true")
                    break
                    ;;
                *)
                    print_error "Please choose 1 or 2"
                    ;;
            esac
        done
    fi
    
    # === REDIS CONFIGURATION ===
    print_section "Redis Configuration"
    
    REDIS_HOST=$(prompt_input "Redis Host" "redis")
    REDIS_PORT=$(prompt_input "Redis Port" "6379" "validate_port")
    
    # === SECURITY CONFIGURATION ===
    print_section "Security Configuration"
    
    echo "Generating admin API keys..."
    ADMIN_KEY_1=$(generate_api_key 32)
    ADMIN_KEY_2=$(generate_api_key 32)
    ADMIN_API_KEYS="$ADMIN_KEY_1,$ADMIN_KEY_2"
    print_success "Admin API keys generated"
    
    echo "Generating Grafana admin password..."
    GRAFANA_PASSWORD=$(generate_password 24)
    print_success "Grafana password generated"
    
    ENABLE_API_KEYS=$(prompt_input "Enable API key authentication" "true")
    
    # === RENDIFF API KEY CONFIGURATION ===
    print_section "Rendiff API Key Management"
    
    # Check if existing API keys should be managed
    echo "Rendiff API keys are used for client authentication to access the API."
    echo ""
    echo "API Key Management Options:"
    echo "1) Generate new Rendiff API keys (Recommended for new setup)"
    echo "2) Import existing Rendiff API keys"
    echo "3) Skip API key generation (configure later)"
    echo ""
    
    while true; do
        api_key_choice=$(prompt_input "API key option" "1")
        case $api_key_choice in
            1)
                setup_new_api_keys
                break
                ;;
            2)
                import_existing_api_keys
                break
                ;;
            3)
                RENDIFF_API_KEYS=""
                print_warning "API key generation skipped. You can generate keys later using: ./scripts/manage-api-keys.sh"
                break
                ;;
            *)
                print_error "Please choose 1, 2, or 3"
                ;;
        esac
    done
    
    # === SSL/TLS CONFIGURATION ===
    print_section "SSL/TLS Configuration"
    
    echo "Configure HTTPS/SSL for your API endpoint:"
    echo "1) HTTP only (Development/Internal use)"
    echo "2) Self-signed certificate (Development/Testing)"
    echo "3) Let's Encrypt certificate (Production with domain)"
    echo ""
    
    while true; do
        ssl_choice=$(prompt_input "SSL configuration" "1")
        case $ssl_choice in
            1)
                SSL_ENABLED="false"
                SSL_TYPE="none"
                break
                ;;
            2)
                SSL_ENABLED="true"
                SSL_TYPE="self-signed"
                break
                ;;
            3)
                SSL_ENABLED="true"
                SSL_TYPE="letsencrypt"
                break
                ;;
            *)
                print_error "Please choose 1, 2, or 3"
                ;;
        esac
    done
    
    if [ "$SSL_ENABLED" = "true" ]; then
        DOMAIN_NAME=$(prompt_input "Domain name (FQDN)" "" "validate_non_empty")
        
        if [ "$SSL_TYPE" = "letsencrypt" ]; then
            CERTBOT_EMAIL=$(prompt_input "Email for Let's Encrypt registration" "" "validate_email")
            
            echo ""
            echo "Let's Encrypt Options:"
            echo "1) Production certificates"
            echo "2) Staging certificates (for testing)"
            echo ""
            
            while true; do
                staging_choice=$(prompt_input "Certificate environment" "1")
                case $staging_choice in
                    1)
                        LETSENCRYPT_STAGING="false"
                        break
                        ;;
                    2)
                        LETSENCRYPT_STAGING="true"
                        print_warning "Using staging certificates - these will show as invalid in browsers"
                        break
                        ;;
                    *)
                        print_error "Please choose 1 or 2"
                        ;;
                esac
            done
        fi
        
        # Update external URL to use HTTPS if SSL is enabled
        if [[ "$EXTERNAL_URL" == http://* ]]; then
            EXTERNAL_URL="https://${DOMAIN_NAME}:443"
        fi
    fi
    
    # === STORAGE CONFIGURATION ===
    print_section "Storage Configuration"
    
    STORAGE_PATH=$(prompt_input "Local storage path" "./storage")
    
    echo ""
    echo "Choose default storage backend:"
    echo "1) Local filesystem"
    echo "2) AWS S3"
    echo "3) Azure Blob Storage"
    echo "4) Google Cloud Storage"
    echo ""
    
    while true; do
        storage_choice=$(prompt_input "Storage choice" "1")
        case $storage_choice in
            1)
                STORAGE_DEFAULT_BACKEND="local"
                SETUP_S3="false"
                SETUP_AZURE="false"
                SETUP_GCP="false"
                break
                ;;
            2)
                STORAGE_DEFAULT_BACKEND="s3"
                SETUP_S3="true"
                SETUP_AZURE="false"
                SETUP_GCP="false"
                break
                ;;
            3)
                STORAGE_DEFAULT_BACKEND="azure"
                SETUP_S3="false"
                SETUP_AZURE="true"
                SETUP_GCP="false"
                break
                ;;
            4)
                STORAGE_DEFAULT_BACKEND="gcs"
                SETUP_S3="false"
                SETUP_AZURE="false"
                SETUP_GCP="true"
                break
                ;;
            *)
                print_error "Please choose 1, 2, 3, or 4"
                ;;
        esac
    done
    
    # === CLOUD STORAGE SETUP ===
    if [ "$SETUP_S3" = "true" ]; then
        print_section "AWS S3 Configuration"
        AWS_ACCESS_KEY_ID=$(prompt_input "AWS Access Key ID" "" "validate_non_empty")
        AWS_SECRET_ACCESS_KEY=$(prompt_input "AWS Secret Access Key" "" "validate_non_empty" "true")
        AWS_S3_BUCKET=$(prompt_input "S3 Bucket Name" "" "validate_non_empty")
        AWS_S3_REGION=$(prompt_input "AWS Region" "us-east-1")
        AWS_S3_ENDPOINT=$(prompt_input "S3 Endpoint" "https://s3.amazonaws.com" "validate_url")
    fi
    
    if [ "$SETUP_AZURE" = "true" ]; then
        print_section "Azure Storage Configuration"
        AZURE_STORAGE_ACCOUNT=$(prompt_input "Storage Account Name" "" "validate_non_empty")
        AZURE_STORAGE_KEY=$(prompt_input "Storage Account Key" "" "validate_non_empty" "true")
        AZURE_CONTAINER=$(prompt_input "Container Name" "" "validate_non_empty")
    fi
    
    if [ "$SETUP_GCP" = "true" ]; then
        print_section "Google Cloud Storage Configuration"
        GCP_PROJECT_ID=$(prompt_input "GCP Project ID" "" "validate_non_empty")
        GCS_BUCKET=$(prompt_input "GCS Bucket Name" "" "validate_non_empty")
        
        echo ""
        print_warning "Please ensure your GCP service account key is placed at: ./config/gcp-key.json"
        echo "Press Enter to continue..."
        read
    fi
    
    # === MONITORING CONFIGURATION ===
    print_section "Monitoring Configuration"
    
    ENABLE_MONITORING=$(prompt_input "Enable monitoring (Prometheus/Grafana)" "true")
    
    if [ "$ENABLE_MONITORING" = "true" ]; then
        PROMETHEUS_PORT=$(prompt_input "Prometheus Port" "9090" "validate_port")
        GRAFANA_PORT=$(prompt_input "Grafana Port" "3000" "validate_port")
    else
        PROMETHEUS_PORT="9090"
        GRAFANA_PORT="3000"
    fi
    
    # === RESOURCE LIMITS ===
    print_section "Resource Limits"
    
    echo "Configure resource limits (press Enter for defaults):"
    MAX_UPLOAD_SIZE=$(prompt_input "Max upload size in bytes" "10737418240")
    MAX_CONCURRENT_JOBS_PER_KEY=$(prompt_input "Max concurrent jobs per API key" "10")
    MAX_JOB_DURATION=$(prompt_input "Max job duration in seconds" "3600")
    
    # === WORKER CONFIGURATION ===
    print_section "Worker Configuration"
    
    CPU_WORKERS=$(prompt_input "Number of CPU workers" "2")
    GPU_WORKERS=$(prompt_input "Number of GPU workers" "0")
    WORKER_CONCURRENCY=$(prompt_input "Worker concurrency" "4")
    
    # === ADDITIONAL SETTINGS ===
    print_section "Additional Settings"
    
    LOG_LEVEL=$(prompt_input "Log level" "info")
    CORS_ORIGINS=$(prompt_input "CORS origins (comma-separated)" "*")
    
    # === WRITE CONFIGURATION ===
    print_section "Writing Configuration"
    
    write_env_config
    
    # === SUMMARY ===
    print_section "Setup Complete!"
    
    print_success "Configuration written to $ENV_FILE"
    if [ -f "$BACKUP_ENV" ]; then
        print_success "Previous configuration backed up to $BACKUP_ENV"
    fi
    
    echo ""
    echo "=== IMPORTANT CREDENTIALS ==="
    echo ""
    
    if [ "$DATABASE_TYPE" = "postgresql" ]; then
        echo "Database: $POSTGRES_DB"
        echo "Database User: $POSTGRES_USER"
        echo "Database Password: $POSTGRES_PASSWORD"
        echo ""
    fi
    
    echo "Admin API Keys:"
    echo "  Key 1: $ADMIN_KEY_1"
    echo "  Key 2: $ADMIN_KEY_2"
    echo ""
    echo "Grafana Admin Password: $GRAFANA_PASSWORD"
    echo ""
    
    if [ -n "$RENDIFF_API_KEYS" ]; then
        echo "Rendiff API Keys:"
        IFS=',' read -ra keys_array <<< "$RENDIFF_API_KEYS"
        for i in "${!keys_array[@]}"; do
            echo "  Key $((i+1)): ${keys_array[i]}"
        done
        echo ""
    fi
    
    print_warning "Please save these credentials securely!"
    echo ""
    
    if [ "$SSL_ENABLED" = "true" ]; then
        echo "SSL Configuration: $SSL_TYPE for $DOMAIN_NAME"
        if [ "$SSL_TYPE" = "letsencrypt" ]; then
            echo "Let's Encrypt Email: $CERTBOT_EMAIL"
            if [ "$LETSENCRYPT_STAGING" = "true" ]; then
                echo "Environment: Staging (test certificates)"
            else
                echo "Environment: Production"
            fi
        fi
        echo ""
    fi
    
    echo "Next steps:"
    echo "1. Review the generated .env file"
    
    if [ "$SSL_ENABLED" = "true" ]; then
        echo "2. Generate SSL certificates:"
        if [ "$SSL_TYPE" = "self-signed" ]; then
            echo "   ./scripts/manage-ssl.sh generate-self-signed $DOMAIN_NAME"
        elif [ "$SSL_TYPE" = "letsencrypt" ]; then
            if [ "$LETSENCRYPT_STAGING" = "true" ]; then
                echo "   ./scripts/manage-ssl.sh generate-letsencrypt $DOMAIN_NAME $CERTBOT_EMAIL --staging"
            else
                echo "   ./scripts/manage-ssl.sh generate-letsencrypt $DOMAIN_NAME $CERTBOT_EMAIL"
            fi
        fi
        echo "3. Start the services with HTTPS: docker-compose -f docker-compose.yml -f docker-compose.https.yml up -d"
    else
        echo "2. Start the services with: docker-compose up -d"
    fi
    
    if [ "$ENABLE_MONITORING" = "true" ]; then
        if [ "$SSL_ENABLED" = "true" ]; then
            echo "4. Access Grafana at: http://localhost:$GRAFANA_PORT (admin/$GRAFANA_PASSWORD)"
        else
            echo "3. Access Grafana at: http://localhost:$GRAFANA_PORT (admin/$GRAFANA_PASSWORD)"
        fi
    fi
    
    if [ "$SSL_ENABLED" = "true" ]; then
        echo "$(if [ "$ENABLE_MONITORING" = "true" ]; then echo "5"; else echo "4"; fi). Access the API at: $EXTERNAL_URL"
    else
        echo "$(if [ "$ENABLE_MONITORING" = "true" ]; then echo "4"; else echo "3"; fi). Access the API at: $EXTERNAL_URL"
    fi
    echo ""
    
    print_success "Setup completed successfully!"
}

# Run main setup
main_setup