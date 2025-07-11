#!/bin/bash
#
# Backup Verification Script for Rendiff FFmpeg API
# Verifies backup integrity and metadata
#

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BACKUP_DIR="${PROJECT_ROOT}/backups"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $*"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $*"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $*" >&2
}

log_debug() {
    if [[ "${DEBUG:-false}" == "true" ]]; then
        echo -e "${BLUE}[DEBUG]${NC} $*"
    fi
}

# Verify SQLite backup
verify_sqlite_backup() {
    local backup_file="$1"
    local test_file="$backup_file"
    local temp_file=""
    
    log_info "Verifying SQLite backup: $(basename "$backup_file")"
    
    # If compressed, decompress temporarily
    if [[ "$backup_file" =~ \.gz$ ]]; then
        temp_file="${backup_file%.gz}.tmp"
        gunzip -c "$backup_file" > "$temp_file"
        test_file="$temp_file"
        log_debug "Decompressed to temporary file: $temp_file"
    fi
    
    # Check if file exists and is not empty
    if [[ ! -f "$test_file" ]]; then
        log_error "Backup file not found: $test_file"
        return 1
    fi
    
    local file_size=$(stat -f%z "$test_file" 2>/dev/null || stat -c%s "$test_file" 2>/dev/null || echo "0")
    if [[ "$file_size" -eq 0 ]]; then
        log_error "Backup file is empty"
        [[ -n "$temp_file" ]] && rm -f "$temp_file"
        return 1
    fi
    
    log_debug "File size: $file_size bytes"
    
    # Check if it's a valid SQLite file
    if ! file "$test_file" | grep -q "SQLite"; then
        log_error "File is not a valid SQLite database"
        [[ -n "$temp_file" ]] && rm -f "$temp_file"
        return 1
    fi
    
    # Run SQLite integrity check
    if ! sqlite3 "$test_file" "PRAGMA integrity_check;" 2>/dev/null | grep -q "ok"; then
        log_error "SQLite integrity check failed"
        [[ -n "$temp_file" ]] && rm -f "$temp_file"
        return 1
    fi
    
    # Check if it has expected tables
    local table_count=$(sqlite3 "$test_file" "SELECT COUNT(*) FROM sqlite_master WHERE type='table';" 2>/dev/null || echo "0")
    if [[ "$table_count" -eq 0 ]]; then
        log_warn "No tables found in database"
    else
        log_debug "Found $table_count tables"
        
        # Check for expected tables
        local expected_tables=("jobs" "api_keys" "alembic_version")
        for table in "${expected_tables[@]}"; do
            if sqlite3 "$test_file" "SELECT name FROM sqlite_master WHERE type='table' AND name='$table';" 2>/dev/null | grep -q "$table"; then
                log_debug "✓ Table '$table' exists"
            else
                log_debug "⚠ Table '$table' not found"
            fi
        done
    fi
    
    # Clean up temporary file
    [[ -n "$temp_file" ]] && rm -f "$temp_file"
    
    log_info "✓ SQLite backup verification passed"
    return 0
}

# Verify PostgreSQL backup
verify_postgresql_backup() {
    local backup_file="$1"
    
    log_info "Verifying PostgreSQL backup: $(basename "$backup_file")"
    
    # Check if file exists and is not empty
    if [[ ! -f "$backup_file" ]]; then
        log_error "Backup file not found: $backup_file"
        return 1
    fi
    
    local file_size=$(stat -f%z "$backup_file" 2>/dev/null || stat -c%s "$backup_file" 2>/dev/null || echo "0")
    if [[ "$file_size" -eq 0 ]]; then
        log_error "Backup file is empty"
        return 1
    fi
    
    log_debug "File size: $file_size bytes"
    
    # Check if pg_restore is available
    if ! command -v pg_restore >/dev/null 2>&1; then
        log_warn "pg_restore not found. Cannot verify PostgreSQL backup structure."
        log_info "✓ Basic file checks passed (install PostgreSQL client tools for full verification)"
        return 0
    fi
    
    # Use pg_restore to list backup contents
    if ! pg_restore --list "$backup_file" >/dev/null 2>&1; then
        log_error "pg_restore cannot read backup file"
        return 1
    fi
    
    # Count objects in backup
    local object_count=$(pg_restore --list "$backup_file" 2>/dev/null | wc -l)
    log_debug "Found $object_count database objects"
    
    if [[ "$object_count" -eq 0 ]]; then
        log_warn "No database objects found in backup"
    fi
    
    log_info "✓ PostgreSQL backup verification passed"
    return 0
}

# Verify backup metadata
verify_backup_metadata() {
    local backup_file="$1"
    local backup_dir=$(dirname "$backup_file")
    local metadata_file="$backup_dir/backup-metadata.json"
    
    if [[ ! -f "$metadata_file" ]]; then
        log_warn "No metadata file found: $metadata_file"
        return 0
    fi
    
    log_info "Verifying backup metadata..."
    
    # Check if metadata is valid JSON
    if ! jq . "$metadata_file" >/dev/null 2>&1; then
        log_error "Invalid JSON in metadata file"
        return 1
    fi
    
    # Extract metadata
    local backup_filename=$(jq -r '.backup_file' "$metadata_file" 2>/dev/null || echo "")
    local expected_size=$(jq -r '.backup_size' "$metadata_file" 2>/dev/null || echo "0")
    local expected_checksum=$(jq -r '.checksum' "$metadata_file" 2>/dev/null || echo "")
    local database_type=$(jq -r '.database_type' "$metadata_file" 2>/dev/null || echo "")
    
    log_debug "Metadata - File: $backup_filename, Size: $expected_size, Type: $database_type"
    
    # Verify filename matches
    if [[ "$(basename "$backup_file")" != "$backup_filename" ]]; then
        log_warn "Backup filename doesn't match metadata"
    fi
    
    # Verify file size
    local actual_size=$(stat -f%z "$backup_file" 2>/dev/null || stat -c%s "$backup_file" 2>/dev/null || echo "0")
    if [[ "$actual_size" != "$expected_size" ]]; then
        log_error "File size mismatch: expected $expected_size, got $actual_size"
        return 1
    fi
    
    # Verify checksum
    if [[ -n "$expected_checksum" ]]; then
        local actual_checksum=$(shasum -a 256 "$backup_file" | cut -d' ' -f1)
        if [[ "$actual_checksum" != "$expected_checksum" ]]; then
            log_error "Checksum mismatch: expected $expected_checksum, got $actual_checksum"
            return 1
        fi
        log_debug "✓ Checksum verified"
    fi
    
    log_info "✓ Metadata verification passed"
    return 0
}

# Verify single backup file
verify_backup_file() {
    local backup_file="$1"
    local success=true
    
    echo ""
    echo "=================================="
    echo "Verifying: $(basename "$backup_file")"
    echo "=================================="
    
    # Basic file checks
    if [[ ! -f "$backup_file" ]]; then
        log_error "File not found: $backup_file"
        return 1
    fi
    
    local file_size=$(stat -f%z "$backup_file" 2>/dev/null || stat -c%s "$backup_file" 2>/dev/null || echo "0")
    local size_mb=$((file_size / 1024 / 1024))
    log_info "File size: ${size_mb}MB ($file_size bytes)"
    
    # Determine backup type from filename or content
    local db_type=""
    if [[ "$backup_file" =~ \.db(\.gz)?$ ]]; then
        db_type="sqlite"
    elif [[ "$backup_file" =~ \.sql(\.gz)?$ ]]; then
        db_type="postgresql"
    else
        # Try to determine from file content
        if file "$backup_file" | grep -q "SQLite"; then
            db_type="sqlite"
        else
            db_type="postgresql"
        fi
    fi
    
    log_info "Detected database type: $db_type"
    
    # Verify backup integrity
    if [[ "$db_type" == "sqlite" ]]; then
        if ! verify_sqlite_backup "$backup_file"; then
            success=false
        fi
    elif [[ "$db_type" == "postgresql" ]]; then
        if ! verify_postgresql_backup "$backup_file"; then
            success=false
        fi
    else
        log_error "Unknown database type"
        success=false
    fi
    
    # Verify metadata if available
    if ! verify_backup_metadata "$backup_file"; then
        success=false
    fi
    
    if [[ "$success" == "true" ]]; then
        log_info "🎉 Backup verification PASSED"
        return 0
    else
        log_error "❌ Backup verification FAILED"
        return 1
    fi
}

# Verify all backups in a directory
verify_all_backups() {
    local search_dir="${1:-$BACKUP_DIR}"
    local total=0
    local passed=0
    local failed=0
    
    log_info "Verifying all backups in: $search_dir"
    
    if [[ ! -d "$search_dir" ]]; then
        log_error "Directory not found: $search_dir"
        return 1
    fi
    
    # Find all backup files
    while IFS= read -r -d '' backup_file; do
        ((total++))
        
        if verify_backup_file "$backup_file"; then
            ((passed++))
        else
            ((failed++))
        fi
        
    done < <(find "$search_dir" -name "rendiff-*" -type f \( -name "*.db" -o -name "*.db.gz" -o -name "*.sql" -o -name "*.sql.gz" \) -print0)
    
    echo ""
    echo "==============================="
    echo "VERIFICATION SUMMARY"
    echo "==============================="
    echo "Total backups: $total"
    echo "Passed: $passed"
    echo "Failed: $failed"
    
    if [[ "$failed" -eq 0 ]]; then
        log_info "🎉 All backup verifications PASSED"
        return 0
    else
        log_error "❌ $failed backup verification(s) FAILED"
        return 1
    fi
}

# Main function
main() {
    local target="${1:-}"
    
    echo "Rendiff FFmpeg API - Backup Verification Tool"
    echo "=============================================="
    
    if [[ -z "$target" ]]; then
        # No target specified, verify all backups
        verify_all_backups
    elif [[ -f "$target" ]]; then
        # Single file specified
        verify_backup_file "$target"
    elif [[ -d "$target" ]]; then
        # Directory specified
        verify_all_backups "$target"
    else
        # Try to find the file in backup directories
        local found_file=""
        
        # Search in date directories
        for date_dir in "$BACKUP_DIR"/[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]; do
            if [[ -d "$date_dir" && -f "$date_dir/$target" ]]; then
                found_file="$date_dir/$target"
                break
            fi
        done
        
        # Search in root backup directory
        if [[ -z "$found_file" && -f "$BACKUP_DIR/$target" ]]; then
            found_file="$BACKUP_DIR/$target"
        fi
        
        if [[ -n "$found_file" ]]; then
            verify_backup_file "$found_file"
        else
            log_error "Target not found: $target"
            return 1
        fi
    fi
}

# Handle command line arguments
case "${1:-}" in
    --help|-h)
        echo "Backup Verification Script for Rendiff FFmpeg API"
        echo ""
        echo "Usage: $0 [TARGET]"
        echo ""
        echo "Arguments:"
        echo "  TARGET     Backup file, directory, or filename to verify"
        echo "             If not provided, verifies all backups"
        echo ""
        echo "Options:"
        echo "  --help     Show this help message"
        echo ""
        echo "Environment Variables:"
        echo "  DEBUG      Enable debug logging (default: false)"
        echo ""
        echo "Examples:"
        echo "  $0                             # Verify all backups"
        echo "  $0 rendiff-20240710-120000.db # Verify specific backup file"
        echo "  $0 /path/to/backup/dir        # Verify all backups in directory"
        echo "  DEBUG=true $0                 # Verify with debug output"
        exit 0
        ;;
    *)
        main "$@"
        ;;
esac