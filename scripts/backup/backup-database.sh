#!/bin/bash
#
# Database Backup Script for Rendiff FFmpeg API
# Supports both PostgreSQL and SQLite databases
#

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
CONFIG_FILE="${PROJECT_ROOT}/.env"
BACKUP_DIR="${PROJECT_ROOT}/backups"
LOG_FILE="${BACKUP_DIR}/backup.log"

# Default configuration
DEFAULT_RETENTION_DAYS=30
DEFAULT_COMPRESSION=true
DEFAULT_VERIFICATION=true

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
        # Source the .env file but only export specific variables
        while IFS='=' read -r key value; do
            # Skip comments and empty lines
            [[ $key =~ ^[[:space:]]*# ]] && continue
            [[ -z "$key" ]] && continue
            
            # Remove quotes and spaces
            key=$(echo "$key" | tr -d ' ')
            value=$(echo "$value" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//' | sed 's/^"\(.*\)"$/\1/' | sed "s/^'\(.*\)'$/\1/")
            
            case "$key" in
                DATABASE_URL|POSTGRES_*|BACKUP_*|DEBUG)
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
        # Extract file path from sqlite URL
        DB_FILE=$(echo "$db_url" | sed 's|sqlite[^:]*:///\?||' | sed 's|\?.*||')
        log_info "Detected SQLite database: $DB_FILE"
    elif [[ "$db_url" =~ ^postgres ]]; then
        DB_TYPE="postgresql"
        # Parse PostgreSQL URL: postgres://user:pass@host:port/dbname
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

# Create backup directory structure
setup_backup_directory() {
    local timestamp=$(date '+%Y-%m-%d')
    BACKUP_DATE_DIR="$BACKUP_DIR/$timestamp"
    
    mkdir -p "$BACKUP_DATE_DIR"
    mkdir -p "$BACKUP_DIR/logs"
    
    # Ensure log file exists
    touch "$LOG_FILE"
    
    log_info "Backup directory: $BACKUP_DATE_DIR"
}

# Backup SQLite database
backup_sqlite() {
    local db_file="$1"
    local backup_file="$BACKUP_DATE_DIR/rendiff-$(date '+%Y%m%d-%H%M%S').db"
    
    log_info "Starting SQLite backup..."
    
    # Check if source database exists
    if [[ ! -f "$db_file" ]]; then
        log_error "SQLite database file not found: $db_file"
        return 1
    fi
    
    # Create backup using sqlite3 .backup command for consistency
    if command -v sqlite3 >/dev/null 2>&1; then
        log_info "Using sqlite3 .backup command"
        sqlite3 "$db_file" ".backup '$backup_file'"
    else
        log_warn "sqlite3 not found, using file copy"
        cp "$db_file" "$backup_file"
    fi
    
    # Verify backup file was created
    if [[ ! -f "$backup_file" ]]; then
        log_error "Backup file was not created: $backup_file"
        return 1
    fi
    
    # Check backup file size
    local original_size=$(stat -f%z "$db_file" 2>/dev/null || stat -c%s "$db_file" 2>/dev/null || echo "0")
    local backup_size=$(stat -f%z "$backup_file" 2>/dev/null || stat -c%s "$backup_file" 2>/dev/null || echo "0")
    
    log_info "Original size: $original_size bytes, Backup size: $backup_size bytes"
    
    if [[ "$backup_size" -lt "$((original_size / 2))" ]]; then
        log_error "Backup file seems too small, possible corruption"
        return 1
    fi
    
    # Compress if enabled
    if [[ "${BACKUP_COMPRESSION:-$DEFAULT_COMPRESSION}" == "true" ]]; then
        log_info "Compressing backup..."
        gzip "$backup_file"
        backup_file="${backup_file}.gz"
    fi
    
    echo "$backup_file"
}

# Backup PostgreSQL database
backup_postgresql() {
    local backup_file="$BACKUP_DATE_DIR/rendiff-$(date '+%Y%m%d-%H%M%S').sql"
    
    log_info "Starting PostgreSQL backup..."
    
    # Check if pg_dump is available
    if ! command -v pg_dump >/dev/null 2>&1; then
        log_error "pg_dump not found. Please install PostgreSQL client tools."
        return 1
    fi
    
    # Set PostgreSQL environment variables
    export PGPASSWORD="$POSTGRES_PASSWORD"
    export PGHOST="$POSTGRES_HOST"
    export PGPORT="$POSTGRES_PORT"
    export PGUSER="$POSTGRES_USER"
    export PGDATABASE="$POSTGRES_DB"
    
    # Create backup
    log_info "Running pg_dump..."
    if pg_dump \
        --verbose \
        --no-owner \
        --no-privileges \
        --format=custom \
        --compress=9 \
        --file="$backup_file" \
        "$POSTGRES_DB"; then
        log_info "PostgreSQL backup completed successfully"
    else
        log_error "pg_dump failed"
        return 1
    fi
    
    # Verify backup file was created
    if [[ ! -f "$backup_file" ]]; then
        log_error "Backup file was not created: $backup_file"
        return 1
    fi
    
    # Check backup file size
    local backup_size=$(stat -f%z "$backup_file" 2>/dev/null || stat -c%s "$backup_file" 2>/dev/null || echo "0")
    log_info "Backup size: $backup_size bytes"
    
    if [[ "$backup_size" -lt 1024 ]]; then
        log_error "Backup file seems too small, possible corruption"
        return 1
    fi
    
    echo "$backup_file"
}

# Verify backup integrity
verify_backup() {
    local backup_file="$1"
    
    if [[ "${BACKUP_VERIFICATION:-$DEFAULT_VERIFICATION}" != "true" ]]; then
        log_info "Backup verification disabled"
        return 0
    fi
    
    log_info "Verifying backup integrity: $backup_file"
    
    if [[ "$DB_TYPE" == "sqlite" ]]; then
        local test_file="$backup_file"
        
        # If compressed, decompress temporarily
        if [[ "$backup_file" =~ \.gz$ ]]; then
            test_file="${backup_file%.gz}"
            gunzip -c "$backup_file" > "$test_file"
        fi
        
        # Verify SQLite database integrity
        if sqlite3 "$test_file" "PRAGMA integrity_check;" | grep -q "ok"; then
            log_info "SQLite backup verification passed"
            
            # Clean up temporary file if it was decompressed
            if [[ "$backup_file" =~ \.gz$ ]]; then
                rm -f "$test_file"
            fi
            return 0
        else
            log_error "SQLite backup verification failed"
            return 1
        fi
        
    elif [[ "$DB_TYPE" == "postgresql" ]]; then
        # For PostgreSQL, we can check if pg_restore can read the file
        if pg_restore --list "$backup_file" >/dev/null 2>&1; then
            log_info "PostgreSQL backup verification passed"
            return 0
        else
            log_error "PostgreSQL backup verification failed"
            return 1
        fi
    fi
}

# Clean old backups
cleanup_old_backups() {
    local retention_days="${BACKUP_RETENTION_DAYS:-$DEFAULT_RETENTION_DAYS}"
    
    log_info "Cleaning up backups older than $retention_days days..."
    
    # Find and remove directories older than retention period
    find "$BACKUP_DIR" -maxdepth 1 -type d -name "[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]" \
        -mtime +"$retention_days" -exec rm -rf {} + 2>/dev/null || true
    
    # Also clean up individual backup files (legacy cleanup)
    find "$BACKUP_DIR" -maxdepth 1 -type f -name "rendiff-*.db*" \
        -mtime +"$retention_days" -delete 2>/dev/null || true
    find "$BACKUP_DIR" -maxdepth 1 -type f -name "rendiff-*.sql*" \
        -mtime +"$retention_days" -delete 2>/dev/null || true
    
    log_info "Cleanup completed"
}

# Create backup metadata
create_backup_metadata() {
    local backup_file="$1"
    local metadata_file="$BACKUP_DATE_DIR/backup-metadata.json"
    
    local backup_size=$(stat -f%z "$backup_file" 2>/dev/null || stat -c%s "$backup_file" 2>/dev/null || echo "0")
    local checksum=$(shasum -a 256 "$backup_file" | cut -d' ' -f1)
    
    cat > "$metadata_file" << EOF
{
    "timestamp": "$(date -u '+%Y-%m-%dT%H:%M:%SZ')",
    "database_type": "$DB_TYPE",
    "backup_file": "$(basename "$backup_file")",
    "backup_size": $backup_size,
    "checksum": "$checksum",
    "version": "1.0",
    "retention_days": ${BACKUP_RETENTION_DAYS:-$DEFAULT_RETENTION_DAYS},
    "compressed": $([ "$backup_file" =~ \.gz$ ] && echo "true" || echo "false"),
    "verified": true
}
EOF
    
    log_info "Backup metadata created: $metadata_file"
}

# Main backup function
main() {
    local start_time=$(date '+%Y-%m-%d %H:%M:%S')
    
    log_info "=== Starting Database Backup ==="
    log_info "Start time: $start_time"
    
    # Load configuration
    load_config
    
    # Parse database configuration
    if ! parse_database_url; then
        log_error "Failed to parse database configuration"
        exit 1
    fi
    
    # Setup backup directory
    setup_backup_directory
    
    # Perform backup based on database type
    local backup_file=""
    if [[ "$DB_TYPE" == "sqlite" ]]; then
        backup_file=$(backup_sqlite "$DB_FILE")
    elif [[ "$DB_TYPE" == "postgresql" ]]; then
        backup_file=$(backup_postgresql)
    else
        log_error "Unsupported database type: $DB_TYPE"
        exit 1
    fi
    
    if [[ -z "$backup_file" ]]; then
        log_error "Backup failed"
        exit 1
    fi
    
    # Verify backup
    if ! verify_backup "$backup_file"; then
        log_error "Backup verification failed"
        exit 1
    fi
    
    # Create metadata
    create_backup_metadata "$backup_file"
    
    # Clean up old backups
    cleanup_old_backups
    
    local end_time=$(date '+%Y-%m-%d %H:%M:%S')
    log_info "Backup completed successfully: $backup_file"
    log_info "Start time: $start_time"
    log_info "End time: $end_time"
    log_info "=== Database Backup Complete ==="
    
    # Output backup file path for automation
    echo "$backup_file"
}

# Handle command line arguments
case "${1:-}" in
    --help|-h)
        echo "Database Backup Script for Rendiff FFmpeg API"
        echo ""
        echo "Usage: $0 [OPTIONS]"
        echo ""
        echo "Environment Variables:"
        echo "  DATABASE_URL                Database connection URL"
        echo "  BACKUP_RETENTION_DAYS      Days to keep backups (default: 30)"
        echo "  BACKUP_COMPRESSION         Enable compression (default: true)"
        echo "  BACKUP_VERIFICATION        Enable verification (default: true)"
        echo "  DEBUG                      Enable debug logging (default: false)"
        echo ""
        echo "Examples:"
        echo "  $0                         # Run backup with default settings"
        echo "  DEBUG=true $0              # Run with debug logging"
        echo "  BACKUP_RETENTION_DAYS=7 $0 # Keep backups for 7 days"
        exit 0
        ;;
    --test)
        echo "Testing backup configuration..."
        load_config
        parse_database_url
        echo "Database type: $DB_TYPE"
        if [[ "$DB_TYPE" == "sqlite" ]]; then
            echo "SQLite file: $DB_FILE"
        elif [[ "$DB_TYPE" == "postgresql" ]]; then
            echo "PostgreSQL: $POSTGRES_HOST:$POSTGRES_PORT/$POSTGRES_DB"
        fi
        exit 0
        ;;
    "")
        # Run main backup
        main
        ;;
    *)
        echo "Unknown option: $1"
        echo "Use --help for usage information"
        exit 1
        ;;
esac