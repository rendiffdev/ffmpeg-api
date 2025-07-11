#!/bin/bash

# Rendiff API Key Management Script
# This script provides comprehensive API key management functionality

set -e

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
ENV_FILE=".env"
BACKUP_DIR=".env_backups"
API_KEYS_FILE="api_keys.json"

# Utility functions
print_header() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}     Rendiff API Key Management${NC}"
    echo -e "${BLUE}========================================${NC}"
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

print_info() {
    echo -e "${CYAN}ℹ $1${NC}"
}

# Function to generate secure API key
generate_api_key() {
    local length=${1:-32}
    openssl rand -hex $length | cut -c1-$length
}

# Function to backup .env file
backup_env() {
    if [ -f "$ENV_FILE" ]; then
        mkdir -p "$BACKUP_DIR"
        local backup_file="$BACKUP_DIR/env_$(date +%Y%m%d_%H%M%S).backup"
        cp "$ENV_FILE" "$backup_file"
        print_info "Environment backed up to: $backup_file"
        echo "$backup_file"
    fi
}

# Function to load current API keys
load_current_keys() {
    if [ -f "$ENV_FILE" ]; then
        local keys=$(grep "^RENDIFF_API_KEYS=" "$ENV_FILE" 2>/dev/null | cut -d= -f2 | tr -d '"' || echo "")
        echo "$keys"
    else
        echo ""
    fi
}

# Function to save API keys to .env
save_api_keys() {
    local keys="$1"
    local backup_file=$(backup_env)
    
    if [ -f "$ENV_FILE" ]; then
        # Update existing .env file
        if grep -q "^RENDIFF_API_KEYS=" "$ENV_FILE"; then
            # Replace existing line
            if [[ "$OSTYPE" == "darwin"* ]]; then
                # macOS
                sed -i '' "s/^RENDIFF_API_KEYS=.*/RENDIFF_API_KEYS=$keys/" "$ENV_FILE"
            else
                # Linux
                sed -i "s/^RENDIFF_API_KEYS=.*/RENDIFF_API_KEYS=$keys/" "$ENV_FILE"
            fi
        else
            # Add new line
            echo "RENDIFF_API_KEYS=$keys" >> "$ENV_FILE"
        fi
    else
        # Create new .env file
        echo "RENDIFF_API_KEYS=$keys" > "$ENV_FILE"
    fi
    
    print_success "API keys saved to $ENV_FILE"
    if [ -n "$backup_file" ]; then
        print_info "Previous configuration backed up"
    fi
}

# Function to list current API keys
list_api_keys() {
    echo -e "${CYAN}Current Rendiff API Keys:${NC}"
    echo ""
    
    local keys=$(load_current_keys)
    
    if [ -z "$keys" ]; then
        print_warning "No API keys found in configuration"
        echo ""
        echo "To generate new keys, run: $0 generate"
        echo ""
        return 1
    fi
    
    IFS=',' read -ra keys_array <<< "$keys"
    
    echo "Total keys: ${#keys_array[@]}"
    echo ""
    
    for i in "${!keys_array[@]}"; do
        local key="${keys_array[i]}"
        local masked_key="${key:0:8}...${key: -8}"
        echo "  $((i+1)). $masked_key (Length: ${#key})"
    done
    
    echo ""
    echo "Full keys are stored in: $ENV_FILE"
    echo ""
}

# Function to generate new API keys
generate_new_keys() {
    echo -e "${CYAN}Generate New API Keys${NC}"
    echo ""
    
    # Check for existing keys
    local existing_keys=$(load_current_keys)
    if [ -n "$existing_keys" ]; then
        print_warning "Existing API keys found!"
        echo ""
        echo "Options:"
        echo "1) Replace all existing keys (DANGER: Will invalidate current keys)"
        echo "2) Add new keys to existing ones"
        echo "3) Cancel"
        echo ""
        
        while true; do
            echo -ne "Choose option [3]: "
            read -r choice
            case ${choice:-3} in
                1)
                    print_warning "All existing keys will be replaced!"
                    echo -ne "Are you sure? [y/N]: "
                    read -r confirm
                    if [[ $confirm =~ ^[Yy] ]]; then
                        REPLACE_EXISTING=true
                        break
                    else
                        echo "Operation cancelled."
                        return 0
                    fi
                    ;;
                2)
                    REPLACE_EXISTING=false
                    break
                    ;;
                3)
                    echo "Operation cancelled."
                    return 0
                    ;;
                *)
                    print_error "Please choose 1, 2, or 3."
                    ;;
            esac
        done
    else
        REPLACE_EXISTING=true
    fi
    
    # Ask for number of keys
    echo ""
    echo -ne "Number of API keys to generate [3]: "
    read -r num_keys
    num_keys=${num_keys:-3}
    
    # Validate number
    if ! [[ "$num_keys" =~ ^[0-9]+$ ]] || [ "$num_keys" -lt 1 ] || [ "$num_keys" -gt 20 ]; then
        print_error "Please enter a number between 1 and 20"
        return 1
    fi
    
    # Generate keys
    echo ""
    echo "Generating $num_keys API keys..."
    echo ""
    
    local new_keys=()
    for i in $(seq 1 $num_keys); do
        local key=$(generate_api_key 32)
        new_keys+=("$key")
        print_success "Generated key $i: ${key:0:8}...${key: -8}"
    done
    
    # Combine with existing keys if not replacing
    local final_keys=()
    if [ "$REPLACE_EXISTING" = "false" ] && [ -n "$existing_keys" ]; then
        IFS=',' read -ra existing_array <<< "$existing_keys"
        final_keys=("${existing_array[@]}")
    fi
    
    final_keys+=("${new_keys[@]}")
    
    # Save keys
    local keys_string=$(IFS=','; echo "${final_keys[*]}")
    save_api_keys "$keys_string"
    
    echo ""
    print_success "API key generation complete!"
    echo ""
    echo "Total keys: ${#final_keys[@]}"
    echo ""
    
    # Show new keys (full keys for first-time setup)
    if [ "$REPLACE_EXISTING" = "true" ] || [ -z "$existing_keys" ]; then
        echo "IMPORTANT: Save these keys securely!"
        echo ""
        for i in "${!new_keys[@]}"; do
            echo "  Key $((i+1)): ${new_keys[i]}"
        done
        echo ""
    fi
}

# Function to delete specific API keys
delete_api_keys() {
    echo -e "${CYAN}Delete API Keys${NC}"
    echo ""
    
    local keys=$(load_current_keys)
    
    if [ -z "$keys" ]; then
        print_error "No API keys found to delete"
        return 1
    fi
    
    IFS=',' read -ra keys_array <<< "$keys"
    
    echo "Current API keys:"
    echo ""
    
    for i in "${!keys_array[@]}"; do
        local key="${keys_array[i]}"
        local masked_key="${key:0:8}...${key: -8}"
        echo "  $((i+1)). $masked_key"
    done
    
    echo ""
    echo "Enter the numbers of keys to delete (comma-separated, e.g., 1,3,5):"
    echo "Or enter 'all' to delete all keys:"
    echo ""
    
    echo -ne "Keys to delete: "
    read -r delete_input
    
    if [ "$delete_input" = "all" ]; then
        print_warning "This will delete ALL API keys!"
        echo -ne "Are you sure? [y/N]: "
        read -r confirm
        if [[ $confirm =~ ^[Yy] ]]; then
            save_api_keys ""
            print_success "All API keys deleted"
        else
            echo "Operation cancelled."
        fi
        return 0
    fi
    
    # Parse comma-separated numbers
    IFS=',' read -ra delete_indices <<< "$delete_input"
    local keys_to_keep=()
    
    for i in "${!keys_array[@]}"; do
        local should_delete=false
        for delete_idx in "${delete_indices[@]}"; do
            delete_idx=$(echo "$delete_idx" | xargs)  # Trim whitespace
            if [ "$((i+1))" = "$delete_idx" ]; then
                should_delete=true
                break
            fi
        done
        
        if [ "$should_delete" = "false" ]; then
            keys_to_keep+=("${keys_array[i]}")
        fi
    done
    
    if [ ${#keys_to_keep[@]} -eq ${#keys_array[@]} ]; then
        print_warning "No valid keys selected for deletion"
        return 1
    fi
    
    # Confirm deletion
    local deleted_count=$((${#keys_array[@]} - ${#keys_to_keep[@]}))
    print_warning "This will delete $deleted_count API key(s)"
    echo -ne "Continue? [y/N]: "
    read -r confirm
    
    if [[ $confirm =~ ^[Yy] ]]; then
        local remaining_keys=$(IFS=','; echo "${keys_to_keep[*]}")
        save_api_keys "$remaining_keys"
        print_success "$deleted_count API key(s) deleted"
        print_info "Remaining keys: ${#keys_to_keep[@]}"
    else
        echo "Operation cancelled."
    fi
}

# Function to rotate (regenerate) all API keys
rotate_api_keys() {
    echo -e "${CYAN}Rotate All API Keys${NC}"
    echo ""
    
    local keys=$(load_current_keys)
    
    if [ -z "$keys" ]; then
        print_error "No API keys found to rotate"
        echo ""
        echo "Run: $0 generate"
        return 1
    fi
    
    IFS=',' read -ra keys_array <<< "$keys"
    local num_keys=${#keys_array[@]}
    
    print_warning "This will replace ALL $num_keys existing API keys with new ones!"
    print_warning "Current API keys will be INVALIDATED!"
    echo ""
    echo -ne "Continue with rotation? [y/N]: "
    read -r confirm
    
    if [[ ! $confirm =~ ^[Yy] ]]; then
        echo "Operation cancelled."
        return 0
    fi
    
    echo ""
    echo "Generating $num_keys new API keys..."
    echo ""
    
    local new_keys=()
    for i in $(seq 1 $num_keys); do
        local key=$(generate_api_key 32)
        new_keys+=("$key")
        print_success "Generated new key $i"
    done
    
    local keys_string=$(IFS=','; echo "${new_keys[*]}")
    save_api_keys "$keys_string"
    
    echo ""
    print_success "API key rotation complete!"
    echo ""
    print_warning "IMPORTANT: Update all clients with the new API keys!"
    echo ""
    
    echo "New API keys:"
    for i in "${!new_keys[@]}"; do
        echo "  Key $((i+1)): ${new_keys[i]}"
    done
    echo ""
}

# Function to test API keys
test_api_keys() {
    echo -e "${CYAN}Test API Keys${NC}"
    echo ""
    
    local keys=$(load_current_keys)
    
    if [ -z "$keys" ]; then
        print_error "No API keys found to test"
        return 1
    fi
    
    # Check if API is running
    local api_url="http://localhost:8000"
    if [ -f "$ENV_FILE" ]; then
        local external_url=$(grep "^EXTERNAL_URL=" "$ENV_FILE" 2>/dev/null | cut -d= -f2 | tr -d '"' || echo "")
        if [ -n "$external_url" ]; then
            api_url="$external_url"
        fi
    fi
    
    echo "Testing API keys against: $api_url"
    echo ""
    
    IFS=',' read -ra keys_array <<< "$keys"
    
    for i in "${!keys_array[@]}"; do
        local key="${keys_array[i]}"
        local masked_key="${key:0:8}...${key: -8}"
        
        echo -ne "Testing key $((i+1)) ($masked_key): "
        
        # Test the key with a health check
        local response=$(curl -s -w "%{http_code}" -H "X-API-Key: $key" "$api_url/health" -o /dev/null 2>/dev/null || echo "000")
        
        case $response in
            200)
                echo -e "${GREEN}✓ Valid${NC}"
                ;;
            401)
                echo -e "${RED}✗ Unauthorized${NC}"
                ;;
            403)
                echo -e "${RED}✗ Forbidden${NC}"
                ;;
            000)
                echo -e "${YELLOW}? API not reachable${NC}"
                ;;
            *)
                echo -e "${YELLOW}? HTTP $response${NC}"
                ;;
        esac
    done
    
    echo ""
    if [[ "$response" == "000" ]]; then
        print_info "Note: API server may not be running. Start with: docker-compose up -d"
    fi
}

# Function to export API keys
export_api_keys() {
    echo -e "${CYAN}Export API Keys${NC}"
    echo ""
    
    local keys=$(load_current_keys)
    
    if [ -z "$keys" ]; then
        print_error "No API keys found to export"
        return 1
    fi
    
    echo "Export options:"
    echo "1) Save to file (secure)"
    echo "2) Display in terminal (less secure)"
    echo "3) Copy to clipboard (if available)"
    echo ""
    
    while true; do
        echo -ne "Choose export method [1]: "
        read -r choice
        case ${choice:-1} in
            1)
                export_to_file "$keys"
                break
                ;;
            2)
                export_to_terminal "$keys"
                break
                ;;
            3)
                export_to_clipboard "$keys"
                break
                ;;
            *)
                print_error "Please choose 1, 2, or 3."
                ;;
        esac
    done
}

# Function to export keys to file
export_to_file() {
    local keys="$1"
    local timestamp=$(date +%Y%m%d_%H%M%S)
    local export_file="rendiff_api_keys_$timestamp.txt"
    
    echo -ne "Export filename [$export_file]: "
    read -r filename
    filename=${filename:-$export_file}
    
    {
        echo "# Rendiff API Keys"
        echo "# Generated: $(date)"
        echo "# Total keys: $(echo "$keys" | tr ',' '\n' | wc -l)"
        echo ""
        echo "# Comma-separated format:"
        echo "$keys"
        echo ""
        echo "# Individual keys:"
        IFS=',' read -ra keys_array <<< "$keys"
        for i in "${!keys_array[@]}"; do
            echo "Key_$((i+1)): ${keys_array[i]}"
        done
    } > "$filename"
    
    chmod 600 "$filename"  # Secure file permissions
    print_success "API keys exported to: $filename"
    print_warning "Keep this file secure and delete after use!"
}

# Function to export keys to terminal
export_to_terminal() {
    local keys="$1"
    
    print_warning "WARNING: Keys will be displayed in terminal!"
    echo -ne "Continue? [y/N]: "
    read -r confirm
    
    if [[ ! $confirm =~ ^[Yy] ]]; then
        echo "Export cancelled."
        return 0
    fi
    
    echo ""
    echo "=== RENDIFF API KEYS ==="
    echo ""
    echo "Comma-separated:"
    echo "$keys"
    echo ""
    echo "Individual keys:"
    IFS=',' read -ra keys_array <<< "$keys"
    for i in "${!keys_array[@]}"; do
        echo "Key $((i+1)): ${keys_array[i]}"
    done
    echo ""
    echo "========================"
    echo ""
}

# Function to export keys to clipboard
export_to_clipboard() {
    local keys="$1"
    
    # Check for clipboard utilities
    local clipboard_cmd=""
    if command -v pbcopy &> /dev/null; then
        clipboard_cmd="pbcopy"
    elif command -v xclip &> /dev/null; then
        clipboard_cmd="xclip -selection clipboard"
    elif command -v xsel &> /dev/null; then
        clipboard_cmd="xsel --clipboard --input"
    else
        print_error "No clipboard utility found (pbcopy, xclip, or xsel)"
        return 1
    fi
    
    echo "$keys" | $clipboard_cmd
    print_success "API keys copied to clipboard"
    print_warning "Clear clipboard after use for security!"
}

# Function to show usage
show_usage() {
    echo "Usage: $0 [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  list        List current API keys (masked)"
    echo "  generate    Generate new API keys"
    echo "  delete      Delete specific API keys"
    echo "  rotate      Rotate (replace) all API keys"
    echo "  test        Test API keys against running API"
    echo "  export      Export API keys to file/clipboard"
    echo "  help        Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 list                    # Show current keys"
    echo "  $0 generate                # Generate new keys"
    echo "  $0 delete                  # Delete specific keys"
    echo "  $0 rotate                  # Replace all keys"
    echo "  $0 test                    # Test keys against API"
    echo ""
}

# Main function
main() {
    local command="${1:-help}"
    
    case $command in
        list|ls)
            print_header
            list_api_keys
            ;;
        generate|gen|new)
            print_header
            generate_new_keys
            ;;
        delete|del|remove|rm)
            print_header
            delete_api_keys
            ;;
        rotate|regenerate|regen)
            print_header
            rotate_api_keys
            ;;
        test|validate|check)
            print_header
            test_api_keys
            ;;
        export|save)
            print_header
            export_api_keys
            ;;
        help|--help|-h)
            print_header
            show_usage
            ;;
        *)
            print_header
            print_error "Unknown command: $command"
            echo ""
            show_usage
            exit 1
            ;;
    esac
}

# Run main function
main "$@"