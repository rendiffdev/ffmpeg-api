#!/bin/bash
#
# Install Backup Service for Rendiff FFmpeg API
# Creates systemd service and timer for automated backups
#

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
SERVICE_NAME="rendiff-backup"
BACKUP_SCRIPT="$SCRIPT_DIR/backup-database.sh"
SERVICE_USER="${BACKUP_USER:-$(whoami)}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $*"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $*"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $*" >&2
}

# Check if running as root or with sudo
check_permissions() {
    if [[ $EUID -ne 0 ]]; then
        log_error "This script must be run as root or with sudo"
        log_info "Usage: sudo $0"
        exit 1
    fi
}

# Validate backup script exists and is executable
validate_backup_script() {
    if [[ ! -f "$BACKUP_SCRIPT" ]]; then
        log_error "Backup script not found: $BACKUP_SCRIPT"
        exit 1
    fi
    
    if [[ ! -x "$BACKUP_SCRIPT" ]]; then
        log_warn "Making backup script executable"
        chmod +x "$BACKUP_SCRIPT"
    fi
    
    log_info "Backup script validated: $BACKUP_SCRIPT"
}

# Create systemd service file
create_service_file() {
    local service_file="/etc/systemd/system/${SERVICE_NAME}.service"
    
    log_info "Creating systemd service file: $service_file"
    
    cat > "$service_file" << EOF
[Unit]
Description=Rendiff FFmpeg API Database Backup
Documentation=file://$PROJECT_ROOT/docs/disaster-recovery.md
Wants=network-online.target
After=network-online.target

[Service]
Type=oneshot
User=$SERVICE_USER
Group=$SERVICE_USER
WorkingDirectory=$PROJECT_ROOT
Environment=PATH=/usr/local/bin:/usr/bin:/bin
Environment=DEBUG=false
EnvironmentFile=-$PROJECT_ROOT/.env

# Security settings
NoNewPrivileges=yes
PrivateTmp=yes
ProtectSystem=strict
ProtectHome=yes
ReadWritePaths=$PROJECT_ROOT/backups $PROJECT_ROOT/data
ProtectKernelTunables=yes
ProtectKernelModules=yes
ProtectControlGroups=yes

# Resource limits
CPUQuota=50%
MemoryLimit=1G
IOSchedulingClass=3
IOSchedulingPriority=7

# Execution
ExecStart=$BACKUP_SCRIPT
ExecStartPre=/bin/mkdir -p $PROJECT_ROOT/backups
ExecStartPre=/bin/touch $PROJECT_ROOT/backups/backup.log

# Timeout settings
TimeoutStartSec=1800
TimeoutStopSec=60

# Restart policy
Restart=no

# Logging
StandardOutput=append:$PROJECT_ROOT/backups/backup.log
StandardError=append:$PROJECT_ROOT/backups/backup.log
SyslogIdentifier=$SERVICE_NAME

[Install]
WantedBy=multi-user.target
EOF

    log_info "Service file created successfully"
}

# Create systemd timer file
create_timer_file() {
    local timer_file="/etc/systemd/system/${SERVICE_NAME}.timer"
    
    log_info "Creating systemd timer file: $timer_file"
    
    cat > "$timer_file" << EOF
[Unit]
Description=Run Rendiff FFmpeg API Database Backup
Documentation=file://$PROJECT_ROOT/docs/disaster-recovery.md
Requires=${SERVICE_NAME}.service

[Timer]
# Run daily at 2:00 AM
OnCalendar=*-*-* 02:00:00

# Run 10 minutes after boot if missed
Persistent=yes
AccuracySec=10min

# Randomize by up to 15 minutes to avoid system load spikes
RandomizedDelaySec=15min

# Don't run if system is on battery (laptops)
ConditionACPower=true

[Install]
WantedBy=timers.target
EOF

    log_info "Timer file created successfully"
}

# Create backup service environment file
create_environment_file() {
    local env_file="/etc/default/$SERVICE_NAME"
    
    log_info "Creating environment file: $env_file"
    
    cat > "$env_file" << EOF
# Environment configuration for Rendiff FFmpeg API Backup Service
# This file is sourced by the systemd service

# Backup configuration
BACKUP_RETENTION_DAYS=30
BACKUP_COMPRESSION=true
BACKUP_VERIFICATION=true

# Notification settings
BACKUP_NOTIFY_EMAIL=""
BACKUP_NOTIFY_WEBHOOK=""

# Performance settings
BACKUP_IO_PRIORITY=3
BACKUP_NICE_LEVEL=10

# Debug settings
DEBUG=false

# Custom backup script options
BACKUP_EXTRA_OPTIONS=""
EOF

    log_info "Environment file created successfully"
    log_warn "Edit $env_file to customize backup settings"
}

# Create log rotation configuration
create_logrotate_config() {
    local logrotate_file="/etc/logrotate.d/$SERVICE_NAME"
    
    log_info "Creating logrotate configuration: $logrotate_file"
    
    cat > "$logrotate_file" << EOF
$PROJECT_ROOT/backups/backup.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 644 $SERVICE_USER $SERVICE_USER
    postrotate
        systemctl reload-or-restart rsyslog > /dev/null 2>&1 || true
    endscript
}

$PROJECT_ROOT/backups/restore.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 644 $SERVICE_USER $SERVICE_USER
}
EOF

    log_info "Logrotate configuration created successfully"
}

# Create monitoring script
create_monitoring_script() {
    local monitor_script="$SCRIPT_DIR/monitor-backup.sh"
    
    log_info "Creating backup monitoring script: $monitor_script"
    
    cat > "$monitor_script" << 'EOF'
#!/bin/bash
#
# Backup Monitoring Script for Rendiff FFmpeg API
#

set -euo pipefail

SERVICE_NAME="rendiff-backup"
PROJECT_ROOT="$(dirname "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)")"
BACKUP_DIR="$PROJECT_ROOT/backups"
LOG_FILE="$BACKUP_DIR/backup.log"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

check_service_status() {
    echo "=== Service Status ==="
    systemctl is-enabled $SERVICE_NAME.timer || echo "Timer not enabled"
    systemctl is-active $SERVICE_NAME.timer || echo "Timer not active"
    echo ""
    
    echo "=== Last Backup Job ==="
    systemctl status $SERVICE_NAME.service --no-pager -l || true
    echo ""
}

check_recent_backups() {
    echo "=== Recent Backups ==="
    if [[ -d "$BACKUP_DIR" ]]; then
        find "$BACKUP_DIR" -name "rendiff-*" -type f -mtime -7 -exec ls -lh {} \; | sort -k6,7
    else
        echo "No backup directory found"
    fi
    echo ""
}

check_backup_log() {
    echo "=== Recent Log Entries ==="
    if [[ -f "$LOG_FILE" ]]; then
        tail -20 "$LOG_FILE"
    else
        echo "No log file found"
    fi
    echo ""
}

check_disk_space() {
    echo "=== Disk Space ==="
    df -h "$BACKUP_DIR" 2>/dev/null || df -h /
    echo ""
}

main() {
    echo "Rendiff FFmpeg API Backup Monitor"
    echo "================================="
    
    check_service_status
    check_recent_backups
    check_backup_log
    check_disk_space
    
    echo "=== Summary ==="
    local recent_backups=$(find "$BACKUP_DIR" -name "rendiff-*" -type f -mtime -1 2>/dev/null | wc -l)
    if [[ "$recent_backups" -gt 0 ]]; then
        echo -e "${GREEN}✓${NC} Found $recent_backups recent backup(s)"
    else
        echo -e "${RED}✗${NC} No recent backups found"
    fi
    
    if systemctl is-active --quiet $SERVICE_NAME.timer; then
        echo -e "${GREEN}✓${NC} Backup timer is active"
    else
        echo -e "${RED}✗${NC} Backup timer is not active"
    fi
}

if [[ "${1:-}" == "--help" ]]; then
    echo "Usage: $0"
    echo "Monitor backup service status and recent backups"
    exit 0
fi

main
EOF

    chmod +x "$monitor_script"
    log_info "Monitoring script created: $monitor_script"
}

# Install and enable the service
install_service() {
    log_info "Reloading systemd daemon"
    systemctl daemon-reload
    
    log_info "Enabling backup timer"
    systemctl enable "${SERVICE_NAME}.timer"
    
    log_info "Starting backup timer"
    systemctl start "${SERVICE_NAME}.timer"
    
    # Test the service
    log_info "Testing backup service"
    if systemctl is-active --quiet "${SERVICE_NAME}.timer"; then
        log_info "✓ Backup timer is active"
    else
        log_error "✗ Backup timer failed to start"
        exit 1
    fi
}

# Display installation summary
show_summary() {
    echo ""
    echo "==============================================="
    echo "Backup Service Installation Complete"
    echo "==============================================="
    echo ""
    echo "Service: $SERVICE_NAME"
    echo "Schedule: Daily at 2:00 AM"
    echo "User: $SERVICE_USER"
    echo "Backup Directory: $PROJECT_ROOT/backups"
    echo ""
    echo "Useful Commands:"
    echo "  systemctl status $SERVICE_NAME.timer    # Check timer status"
    echo "  systemctl status $SERVICE_NAME.service  # Check last backup job"
    echo "  journalctl -u $SERVICE_NAME.service     # View backup logs"
    echo "  sudo systemctl start $SERVICE_NAME      # Run backup now"
    echo "  $SCRIPT_DIR/monitor-backup.sh           # Monitor backup status"
    echo ""
    echo "Configuration Files:"
    echo "  /etc/systemd/system/$SERVICE_NAME.service"
    echo "  /etc/systemd/system/$SERVICE_NAME.timer"
    echo "  /etc/default/$SERVICE_NAME"
    echo "  /etc/logrotate.d/$SERVICE_NAME"
    echo ""
    echo "Next Steps:"
    echo "1. Edit /etc/default/$SERVICE_NAME to customize settings"
    echo "2. Run 'sudo systemctl start $SERVICE_NAME' to test backup"
    echo "3. Check '$PROJECT_ROOT/backups/' for backup files"
    echo "4. Set up monitoring and alerting for backup failures"
    echo ""
}

# Main installation process
main() {
    echo "Installing Rendiff FFmpeg API Backup Service"
    echo "============================================"
    
    check_permissions
    validate_backup_script
    
    create_service_file
    create_timer_file
    create_environment_file
    create_logrotate_config
    create_monitoring_script
    
    install_service
    
    show_summary
}

# Handle command line arguments
case "${1:-}" in
    --help|-h)
        echo "Backup Service Installer for Rendiff FFmpeg API"
        echo ""
        echo "Usage: sudo $0"
        echo ""
        echo "This script installs systemd service and timer for automated backups."
        echo ""
        echo "Options:"
        echo "  --help     Show this help message"
        echo ""
        echo "Environment Variables:"
        echo "  BACKUP_USER    User to run backup service (default: current user)"
        echo ""
        echo "Example:"
        echo "  sudo BACKUP_USER=rendiff $0"
        exit 0
        ;;
    *)
        main
        ;;
esac
EOF