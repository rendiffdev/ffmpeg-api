#!/bin/bash
#
# Database Restore Script for Rendiff FFmpeg API
# Supports both PostgreSQL and SQLite databases
#

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
CONFIG_FILE="${PROJECT_ROOT}/.env"
BACKUP_DIR="${PROJECT_ROOT}/backups"
LOG_FILE="${BACKUP_DIR}/restore.log"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging function
log() {
    local level="$1"
    shift
    local message="$*"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    
    echo -e "[$timestamp] [$level] $message" | tee -a "$LOG_FILE"
}

log_info() {
    log "INFO" "$@"
    echo -e "${GREEN}[INFO]${NC} $*"
}

log_warn() {
    log "WARN" "$@"
    echo -e "${YELLOW}[WARN]${NC} $*"
}

log_error() {
    log "ERROR" "$@"
    echo -e "${RED}[ERROR]${NC} $*" >&2
}

log_debug() {
    if [[ "${DEBUG:-false}" == "true" ]]; then
        log "DEBUG" "$@"
        echo -e "${BLUE}[DEBUG]${NC} $*"
    fi
}

# Load configuration
load_config() {
    if [[ -f "$CONFIG_FILE" ]]; then
        log_info "Loading configuration from $CONFIG_FILE"
        while IFS='=' read -r key value; do
            [[ $key =~ ^[[:space:]]*# ]] && continue
            [[ -z "$key" ]] && continue
            
            key=$(echo "$key" | tr -d ' ')
            value=$(echo "$value" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//' | sed 's/^"\(.*\)"$/\1/' | sed "s/^'\(.*\)'$/\1/")
            
            case "$key" in
                DATABASE_URL|POSTGRES_*|DEBUG)
                    export "$key"="$value"
                    log_debug "Loaded config: $key=$value"
                    ;;
            esac
        done < "$CONFIG_FILE"
    else
        log_warn "Configuration file not found: $CONFIG_FILE"
    fi
}

# Parse database URL
parse_database_url() {
    local db_url="${DATABASE_URL:-}"
    
    if [[ -z "$db_url" ]]; then
        log_error "DATABASE_URL not set"
        return 1
    fi
    
    if [[ "$db_url" =~ ^sqlite ]]; then
        DB_TYPE="sqlite"
        DB_FILE=$(echo "$db_url" | sed 's|sqlite[^:]*:///\?||' | sed 's|\?.*||')
        log_info "Detected SQLite database: $DB_FILE"
    elif [[ "$db_url" =~ ^postgres ]]; then
        DB_TYPE="postgresql"
        if [[ "$db_url" =~ postgres://([^:]+):([^@]+)@([^:]+):([0-9]+)/(.+) ]]; then
            POSTGRES_USER="${BASH_REMATCH[1]}"
            POSTGRES_PASSWORD="${BASH_REMATCH[2]}"
            POSTGRES_HOST="${BASH_REMATCH[3]}"
            POSTGRES_PORT="${BASH_REMATCH[4]}"
            POSTGRES_DB="${BASH_REMATCH[5]}"
        else
            log_error "Invalid PostgreSQL URL format"
            return 1
        fi
        log_info "Detected PostgreSQL database: $POSTGRES_HOST:$POSTGRES_PORT/$POSTGRES_DB"
    else
        log_error "Unsupported database type in URL: $db_url"
        return 1
    fi
}

# List available backups
list_backups() {
    log_info "Available backups in $BACKUP_DIR:"
    
    if [[ ! -d "$BACKUP_DIR" ]]; then
        log_error "Backup directory not found: $BACKUP_DIR"
        return 1
    fi
    
    local found=false
    
    # Look for backup files in date directories
    for date_dir in "$BACKUP_DIR"/[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]; do
        if [[ -d "$date_dir" ]]; then
            echo ""
            echo "Date: $(basename "$date_dir")"
            echo "----------------------------------------"
            
            for backup_file in "$date_dir"/rendiff-*; do
                if [[ -f "$backup_file" ]]; then
                    local size=$(stat -f%z "$backup_file" 2>/dev/null || stat -c%s "$backup_file" 2>/dev/null || echo "0")
                    local size_mb=$((size / 1024 / 1024))
                    echo "  $(basename "$backup_file") (${size_mb}MB)"
                    found=true
                fi
            done
            
            # Show metadata if available
            if [[ -f "$date_dir/backup-metadata.json" ]]; then
                echo "  📋 metadata: backup-metadata.json"
            fi
        fi
    done
    
    # Also check for legacy backup files in root directory
    for backup_file in "$BACKUP_DIR"/rendiff-*; do
        if [[ -f "$backup_file" ]]; then
            if [[ "$found" == "false" ]]; then
                echo ""
                echo "Legacy backups:"
                echo "----------------------------------------"
            fi
            local size=$(stat -f%z "$backup_file" 2>/dev/null || stat -c%s "$backup_file" 2>/dev/null || echo "0")
            local size_mb=$((size / 1024 / 1024))
            echo "  $(basename "$backup_file") (${size_mb}MB)"
            found=true
        fi
    done
    
    if [[ "$found" == "false" ]]; then
        log_warn "No backup files found"
        return 1
    fi
    
    return 0
}

# Find backup file
find_backup_file() {
    local backup_identifier="$1"
    
    # If it's a full path and exists, use it
    if [[ -f "$backup_identifier" ]]; then
        echo "$backup_identifier"
        return 0
    fi
    
    # If it's just a filename, search for it
    local found_file=""
    
    # Search in date directories first
    for date_dir in "$BACKUP_DIR"/[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]; do
        if [[ -d "$date_dir" ]]; then
            if [[ -f "$date_dir/$backup_identifier" ]]; then
                found_file="$date_dir/$backup_identifier"
                break
            fi
        fi
    done
    
    # Search in root backup directory if not found
    if [[ -z "$found_file" && -f "$BACKUP_DIR/$backup_identifier" ]]; then
        found_file="$BACKUP_DIR/$backup_identifier"
    fi
    
    # Try pattern matching
    if [[ -z "$found_file" ]]; then
        for date_dir in "$BACKUP_DIR"/[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9] "$BACKUP_DIR"; do
            if [[ -d "$date_dir" ]]; then
                for backup_file in "$date_dir"/*"$backup_identifier"*; do
                    if [[ -f "$backup_file" ]]; then
                        found_file="$backup_file"
                        break 2
                    fi
                done
            fi
        done
    fi
    
    if [[ -z "$found_file" ]]; then
        log_error "Backup file not found: $backup_identifier"
        return 1
    fi
    
    echo "$found_file"
}

# Create database backup before restore
create_pre_restore_backup() {
    log_info "Creating pre-restore backup..."
    
    local backup_script="$SCRIPT_DIR/backup-database.sh"
    if [[ -x "$backup_script" ]]; then
        local backup_file
        if backup_file=$("$backup_script"); then
            log_info "Pre-restore backup created: $backup_file"
            echo "$backup_file"
        else
            log_error "Failed to create pre-restore backup"
            return 1
        fi
    else
        log_warn "Backup script not found or not executable: $backup_script"
        return 1
    fi
}

# Restore SQLite database
restore_sqlite() {
    local backup_file="$1"
    local restore_file="$2"
    
    log_info "Restoring SQLite database from: $backup_file"
    log_info "Restoring to: $restore_file"
    
    # Decompress if needed
    local source_file="$backup_file"
    if [[ "$backup_file" =~ \.gz$ ]]; then
        log_info "Decompressing backup file..."
        source_file="${backup_file%.gz}"
        gunzip -c "$backup_file" > "$source_file"
    fi
    
    # Verify source file
    if ! sqlite3 "$source_file" "PRAGMA integrity_check;" | grep -q "ok"; then
        log_error "Source backup file is corrupted"
        return 1
    fi
    
    # Create directory if needed
    local restore_dir=$(dirname "$restore_file")
    mkdir -p "$restore_dir"
    
    # Stop any running services that might be using the database
    log_warn "Make sure to stop the API service before running this restore!"
    read -p "Continue with restore? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_info "Restore cancelled by user"
        return 1
    fi
    
    # Copy the file
    cp "$source_file" "$restore_file"
    
    # Verify restored file
    if sqlite3 "$restore_file" "PRAGMA integrity_check;" | grep -q "ok"; then
        log_info "SQLite restore completed successfully"
        
        # Clean up temporary decompressed file
        if [[ "$backup_file" =~ \.gz$ ]]; then
            rm -f "$source_file"
        fi
        
        return 0
    else
        log_error "Restored database failed integrity check"
        return 1
    fi
}

# Restore PostgreSQL database
restore_postgresql() {
    local backup_file="$1"
    
    log_info "Restoring PostgreSQL database from: $backup_file"
    
    # Check if pg_restore is available
    if ! command -v pg_restore >/dev/null 2>&1; then
        log_error "pg_restore not found. Please install PostgreSQL client tools."
        return 1
    fi
    
    # Set PostgreSQL environment variables
    export PGPASSWORD="$POSTGRES_PASSWORD"
    export PGHOST="$POSTGRES_HOST"
    export PGPORT="$POSTGRES_PORT"
    export PGUSER="$POSTGRES_USER"
    export PGDATABASE="$POSTGRES_DB"
    
    # Confirm restore
    log_warn "This will COMPLETELY REPLACE the database: $POSTGRES_DB"
    log_warn "Make sure to stop the API service before running this restore!"
    read -p "Continue with restore? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_info "Restore cancelled by user"
        return 1
    fi
    
    # Drop and recreate database
    log_info "Dropping existing database..."
    if ! psql -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -d "postgres" \
        -c "DROP DATABASE IF EXISTS \"$POSTGRES_DB\";" \
        -c "CREATE DATABASE \"$POSTGRES_DB\";"; then
        log_error "Failed to recreate database"
        return 1
    fi
    
    # Restore database
    log_info "Restoring database content..."
    if pg_restore \
        --verbose \
        --clean \
        --no-owner \
        --no-privileges \
        --dbname="$POSTGRES_DB" \
        "$backup_file"; then
        log_info "PostgreSQL restore completed successfully"
        return 0
    else
        log_error "pg_restore failed"
        return 1
    fi
}

# Main restore function
main() {
    local backup_identifier="${1:-}"
    local start_time=$(date '+%Y-%m-%d %H:%M:%S')
    
    log_info "=== Starting Database Restore ==="
    log_info "Start time: $start_time"
    
    # Load configuration
    load_config
    
    # Parse database configuration
    if ! parse_database_url; then
        log_error "Failed to parse database configuration"
        exit 1
    fi
    
    # If no backup specified, list available backups
    if [[ -z "$backup_identifier" ]]; then
        list_backups
        echo ""
        read -p "Enter backup file name to restore: " backup_identifier
        if [[ -z "$backup_identifier" ]]; then
            log_error "No backup file specified"
            exit 1
        fi
    fi
    
    # Find the backup file
    local backup_file
    if ! backup_file=$(find_backup_file "$backup_identifier"); then
        exit 1
    fi
    
    log_info "Found backup file: $backup_file"
    
    # Create pre-restore backup
    if [[ "${CREATE_PRE_RESTORE_BACKUP:-true}" == "true" ]]; then
        create_pre_restore_backup || log_warn "Failed to create pre-restore backup"
    fi
    
    # Perform restore based on database type
    if [[ "$DB_TYPE" == "sqlite" ]]; then
        if ! restore_sqlite "$backup_file" "$DB_FILE"; then
            log_error "SQLite restore failed"
            exit 1
        fi
    elif [[ "$DB_TYPE" == "postgresql" ]]; then
        if ! restore_postgresql "$backup_file"; then
            log_error "PostgreSQL restore failed"
            exit 1
        fi
    else
        log_error "Unsupported database type: $DB_TYPE"
        exit 1
    fi
    
    local end_time=$(date '+%Y-%m-%d %H:%M:%S')
    log_info "Restore completed successfully"
    log_info "Start time: $start_time"
    log_info "End time: $end_time"
    log_info "=== Database Restore Complete ==="
    
    log_info "Remember to restart the API service!"
}

# Handle command line arguments
case "${1:-}" in
    --help|-h)
        echo "Database Restore Script for Rendiff FFmpeg API"
        echo ""
        echo "Usage: $0 [BACKUP_FILE]"
        echo ""
        echo "Arguments:"
        echo "  BACKUP_FILE    Backup file to restore (optional, will prompt if not provided)"
        echo ""
        echo "Options:"
        echo "  --list         List available backup files"
        echo "  --help         Show this help message"
        echo ""
        echo "Environment Variables:"
        echo "  DATABASE_URL                   Database connection URL"
        echo "  CREATE_PRE_RESTORE_BACKUP     Create backup before restore (default: true)"
        echo "  DEBUG                          Enable debug logging (default: false)"
        echo ""
        echo "Examples:"
        echo "  $0                             # Interactive mode - list and select backup"
        echo "  $0 rendiff-20240710-120000.db # Restore specific backup file"
        echo "  $0 --list                     # List available backups"
        exit 0
        ;;
    --list)
        load_config
        list_backups
        exit 0
        ;;
    *)
        # Run main restore
        main "$@"
        ;;
esac