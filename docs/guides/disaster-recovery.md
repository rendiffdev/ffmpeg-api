# Disaster Recovery Guide - Rendiff FFmpeg API

This document provides comprehensive procedures for disaster recovery, backup management, and system restoration for the Rendiff FFmpeg API.

## Table of Contents

1. [Overview](#overview)
2. [Backup Strategy](#backup-strategy)
3. [Recovery Procedures](#recovery-procedures)
4. [Emergency Contacts](#emergency-contacts)
5. [Testing and Validation](#testing-and-validation)
6. [Common Scenarios](#common-scenarios)
7. [Troubleshooting](#troubleshooting)

## Overview

### Recovery Objectives

- **Recovery Time Objective (RTO)**: 1 hour
- **Recovery Point Objective (RPO)**: 24 hours
- **Maximum Tolerable Downtime**: 4 hours

### Backup Components

The backup system protects the following critical components:

- **Database**: PostgreSQL/SQLite containing jobs, API keys, and metadata
- **Storage**: User-uploaded files and processed outputs
- **Configuration**: Application settings and secrets
- **Logs**: Application and audit logs

## Backup Strategy

### Automated Backups

#### Daily Backups
- **Schedule**: 2:00 AM UTC daily
- **Retention**: 30 days
- **Location**: `./backups/YYYY-MM-DD/`
- **Verification**: Automatic integrity check after creation

#### Weekly Backups
- **Schedule**: Sunday 2:00 AM UTC
- **Retention**: 12 weeks
- **Additional**: Tagged as weekly in metadata

#### Monthly Backups
- **Schedule**: 1st of month, 2:00 AM UTC
- **Retention**: 12 months
- **Additional**: Tagged as monthly in metadata

### Backup Types

#### Database Backups
- **SQLite**: Complete database file with integrity verification
- **PostgreSQL**: Custom format with compression using `pg_dump`
- **Encryption**: AES-256 (production environments)
- **Compression**: Enabled to reduce storage requirements

#### Configuration Backups
- Environment variables and settings
- SSL certificates and keys
- Service configuration files

## Recovery Procedures

### Prerequisites

Before starting any recovery procedure:

1. **Stop all services** to prevent data corruption
2. **Identify the cause** of the failure
3. **Select appropriate backup** based on recovery requirements
4. **Notify stakeholders** of the recovery operation

### Complete System Recovery

#### Step 1: Prepare Recovery Environment

```bash
# Stop all services
docker-compose down

# Create recovery workspace
mkdir -p /tmp/recovery
cd /tmp/recovery

# Download recovery scripts
curl -O https://raw.githubusercontent.com/your-repo/recovery-scripts.tar.gz
tar -xzf recovery-scripts.tar.gz
```

#### Step 2: Database Recovery

```bash
# List available backups
./scripts/restore-database.sh --list

# Restore database (interactive mode)
./scripts/restore-database.sh

# Or restore specific backup
./scripts/restore-database.sh rendiff-20240710-120000.db
```

#### Step 3: Configuration Recovery

```bash
# Restore environment configuration
cp backups/config/.env.backup .env

# Restore SSL certificates
cp -r backups/ssl/ traefik/certs/

# Restore storage configuration
cp backups/config/storage.yml config/
```

#### Step 4: Storage Recovery

```bash
# Mount backup storage
mount /dev/backup-disk /mnt/backup

# Restore user data
rsync -av /mnt/backup/storage/ ./storage/

# Verify file integrity
find ./storage -type f -exec sha256sum {} \; > restored-checksums.txt
diff restored-checksums.txt backups/storage-checksums.txt
```

#### Step 5: Service Restart

```bash
# Start services
docker-compose up -d

# Verify health
curl http://localhost:8000/api/v1/health
curl http://localhost:8000/api/v1/health/detailed

# Check logs
docker-compose logs -f api
```

### Database-Only Recovery

For database corruption or data loss:

```bash
# 1. Stop API and worker services
docker-compose stop api worker

# 2. Backup current state (even if corrupted)
cp data/rendiff.db data/rendiff.db.corrupted.$(date +%Y%m%d-%H%M%S)

# 3. Restore from backup
./scripts/restore-database.sh

# 4. Restart services
docker-compose start api worker

# 5. Verify functionality
curl -H "X-API-Key: your-key" http://localhost:8000/api/v1/jobs
```

### Configuration Recovery

For configuration corruption or loss:

```bash
# 1. Stop all services
docker-compose down

# 2. Restore configuration files
cp backups/latest/.env .env
cp backups/latest/config/* config/

# 3. Restart services
docker-compose up -d

# 4. Verify configuration
./scripts/validate-configurations.sh
```

## Emergency Contacts

### Primary Contacts

| Role | Name | Email | Phone | Available |
|------|------|-------|-------|-----------|
| System Administrator | Admin | admin@company.com | +1-xxx-xxx-xxxx | 24/7 |
| DevOps Engineer | DevOps | devops@company.com | +1-xxx-xxx-xxxx | Business Hours |
| Database Administrator | DBA | dba@company.com | +1-xxx-xxx-xxxx | On-call |

### Escalation Matrix

1. **Level 1**: System Administrator (0-15 minutes)
2. **Level 2**: DevOps Engineer (15-30 minutes)
3. **Level 3**: Database Administrator (30-60 minutes)
4. **Level 4**: Management (60+ minutes)

### External Vendors

| Service | Contact | Support Level |
|---------|---------|---------------|
| Cloud Provider | AWS Support | Enterprise |
| Backup Service | BackupVendor | Premium |
| Monitoring | MonitoringCo | 24/7 |

## Testing and Validation

### Monthly Recovery Tests

#### Database Recovery Test

```bash
# 1. Create test environment
mkdir recovery-test-$(date +%Y%m%d)
cd recovery-test-$(date +%Y%m%d)

# 2. Copy production backup
cp ../backups/latest/rendiff-*.db ./test-backup.db

# 3. Create test database
sqlite3 test-restore.db < test-backup.db

# 4. Run validation queries
sqlite3 test-restore.db "SELECT COUNT(*) FROM jobs;"
sqlite3 test-restore.db "SELECT COUNT(*) FROM api_keys;"

# 5. Clean up
cd .. && rm -rf recovery-test-*
```

#### Full System Recovery Test

```bash
# 1. Clone production environment
git clone https://github.com/your-repo/ffmpeg-api.git test-recovery
cd test-recovery

# 2. Use test database
cp ../backups/latest/rendiff-*.db ./data/test.db
sed -i 's/rendiff.db/test.db/' .env

# 3. Start test environment
docker-compose -f docker-compose.test.yml up -d

# 4. Run health checks
curl http://test-api:8000/api/v1/health

# 5. Test basic functionality
curl -H "X-API-Key: test-key" -X POST \
  -H "Content-Type: application/json" \
  -d '{"input": "test.mp4", "output": "test-output.mp4"}' \
  http://test-api:8000/api/v1/convert

# 6. Clean up
docker-compose -f docker-compose.test.yml down
cd .. && rm -rf test-recovery
```

### Validation Checklist

After any recovery operation, verify:

- [ ] Database connectivity and integrity
- [ ] API endpoints responding correctly
- [ ] Authentication system functional
- [ ] Job processing working
- [ ] Storage backends accessible
- [ ] Monitoring and logging operational
- [ ] All configuration settings correct
- [ ] SSL certificates valid
- [ ] External integrations working

## Common Scenarios

### Scenario 1: Database Corruption

**Symptoms**: Application errors, data inconsistency, SQLite/PostgreSQL errors

**Recovery**:
1. Stop services immediately
2. Assess corruption level with integrity checks
3. Restore from most recent valid backup
4. Restart services and validate

**Prevention**:
- Regular integrity checks
- Proper shutdown procedures
- Database maintenance schedules

### Scenario 2: Storage Failure

**Symptoms**: File not found errors, I/O errors, storage unavailable

**Recovery**:
1. Identify failed storage backend
2. Switch to backup storage temporarily
3. Restore data from backup storage
4. Update configuration and restart

**Prevention**:
- Multi-backend storage configuration
- Regular storage health checks
- Automated failover mechanisms

### Scenario 3: Configuration Loss

**Symptoms**: Services won't start, authentication failures, missing settings

**Recovery**:
1. Restore configuration from backup
2. Regenerate secrets if compromised
3. Update environment variables
4. Restart services systematically

**Prevention**:
- Version control for configurations
- Encrypted configuration backups
- Configuration validation scripts

### Scenario 4: Complete System Failure

**Symptoms**: Hardware failure, network outage, data center issues

**Recovery**:
1. Provision new infrastructure
2. Restore all components from backup
3. Update DNS and networking
4. Perform full system validation

**Prevention**:
- Infrastructure as Code
- Multi-region deployments
- Disaster recovery testing

## Troubleshooting

### Common Issues

#### Backup Script Fails

```bash
# Check backup script logs
tail -f backups/backup.log

# Verify disk space
df -h

# Check database connectivity
sqlite3 data/rendiff.db "PRAGMA integrity_check;"

# Test database connection (PostgreSQL)
pg_isready -h $POSTGRES_HOST -p $POSTGRES_PORT
```

#### Restore Fails

```bash
# Verify backup file integrity
./scripts/verify-backup.sh rendiff-20240710-120000.db

# Check file permissions
ls -la backups/

# Verify database format
file backups/rendiff-20240710-120000.db

# Check available disk space
df -h data/
```

#### Services Won't Start After Recovery

```bash
# Check service logs
docker-compose logs api
docker-compose logs worker

# Verify configuration
./scripts/validate-configurations.sh

# Check database connection
./scripts/test-database-connection.sh

# Verify ports are available
netstat -tulpn | grep :8000
```

### Debug Commands

```bash
# Database status
./scripts/database-status.sh

# Service health check
./scripts/health-check.sh --detailed

# Configuration validation
./scripts/validate-configurations.sh --verbose

# Backup verification
./scripts/verify-backup.sh --all

# Storage connectivity test
./scripts/test-storage-backends.sh
```

### Performance Issues After Recovery

```bash
# Rebuild database indexes (SQLite)
sqlite3 data/rendiff.db "REINDEX;"

# Update PostgreSQL statistics
psql -c "ANALYZE;"

# Clear application cache
docker-compose restart redis

# Check resource usage
docker stats
```

## Recovery Time Estimates

| Scenario | Estimated Time | Dependencies |
|----------|----------------|--------------|
| Database restore only | 15-30 minutes | Backup size, disk I/O |
| Configuration restore | 5-10 minutes | Number of services |
| Storage restore | 1-4 hours | Data volume, network speed |
| Complete system recovery | 2-6 hours | Infrastructure complexity |
| New infrastructure setup | 4-8 hours | Automation level |

## Contacts and Resources

### Documentation
- [Installation Guide](INSTALLATION.md)
- [Configuration Reference](CONFIG.md)
- [Security Guide](SECURITY.md)
- [Monitoring Guide](MONITORING.md)

### Support Channels
- **Emergency Hotline**: +1-xxx-xxx-xxxx
- **Slack Channel**: #emergency-response
- **Email**: emergency@company.com
- **Ticket System**: https://support.company.com

---

**Document Version**: 1.0  
**Last Updated**: July 10, 2025  
**Review Schedule**: Quarterly  
**Next Review**: October 10, 2025