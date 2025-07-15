# Repository Structure

This document outlines the clean, organized structure of the FFmpeg API project.

## Directory Structure

```
ffmpeg-api/
├── .github/
│   └── workflows/
│       ├── ci-cd.yml              # Main CI/CD pipeline
│       └── stable-build.yml       # Stable build validation
├── .gitignore                     # Git ignore patterns
├── .python-version                # Python version pinning
├── alembic/                       # Database migrations
│   ├── versions/
│   │   ├── 001_initial_schema.py
│   │   └── 002_add_api_key_table.py
│   └── alembic.ini
├── api/                           # Main API application
│   ├── __init__.py
│   ├── main.py                    # FastAPI application
│   ├── config.py                  # Application configuration
│   ├── dependencies.py            # Dependency injection
│   ├── middleware/
│   │   ├── __init__.py
│   │   └── security.py            # Security middleware
│   ├── models/                    # Database models
│   │   ├── __init__.py
│   │   ├── api_key.py
│   │   ├── database.py
│   │   └── job.py
│   ├── routers/                   # API route handlers
│   │   ├── __init__.py
│   │   ├── admin.py
│   │   ├── api_keys.py
│   │   ├── convert.py
│   │   ├── health.py
│   │   └── jobs.py
│   ├── services/                  # Business logic layer
│   │   ├── __init__.py
│   │   ├── api_key.py
│   │   ├── job_service.py
│   │   ├── queue.py
│   │   └── storage.py
│   └── utils/                     # Utility functions
│       ├── __init__.py
│       ├── database.py
│       ├── error_handlers.py
│       ├── logger.py
│       └── validators.py
├── config/                        # Configuration files
│   ├── krakend.json              # API gateway config
│   └── prometheus.yml            # Prometheus config
├── docker/                        # Docker configuration
│   ├── api/
│   │   ├── Dockerfile            # API container
│   │   └── Dockerfile.old        # Backup
│   ├── postgres/
│   │   └── init/                 # DB initialization
│   ├── redis/
│   │   └── redis.conf
│   ├── worker/
│   │   └── Dockerfile            # Worker container
│   ├── install-ffmpeg.sh         # FFmpeg installation
│   └── requirements-stable.txt   # Stable dependencies
├── docs/                          # Documentation
│   ├── API.md                    # API documentation
│   ├── DEPLOYMENT.md             # Deployment guide
│   ├── INSTALLATION.md           # Installation guide
│   ├── SETUP.md                  # Setup instructions
│   ├── fixes/                    # Bug fix documentation
│   ├── rca/                      # Root cause analysis
│   └── stable-build-solution.md  # Stable build guide
├── k8s/                          # Kubernetes manifests
│   └── base/
│       └── api-deployment.yaml   # API deployment
├── monitoring/                    # Monitoring configuration
│   ├── alerts/
│   │   └── production-alerts.yml # Production alerts
│   ├── dashboards/
│   │   └── rendiff-overview.json # Grafana dashboard
│   └── datasources/
│       └── prometheus.yml        # Prometheus datasource
├── scripts/                       # Utility scripts
│   ├── backup-database.sh        # Database backup
│   ├── docker-entrypoint.sh      # Docker entrypoint
│   ├── generate-api-key.py       # API key generation
│   ├── health-check.sh           # Health check script
│   ├── init-db.py               # Database initialization
│   ├── manage-api-keys.sh        # API key management
│   ├── validate-configurations.sh # Config validation
│   ├── validate-dockerfile.py    # Dockerfile validation
│   ├── validate-production.sh    # Production validation
│   ├── validate-stable-build.sh  # Build validation
│   └── verify-deployment.sh      # Deployment verification
├── tests/                         # Test suite
│   ├── conftest.py               # Test configuration
│   ├── test_api_keys.py          # API key tests
│   ├── test_health.py            # Health endpoint tests
│   ├── test_jobs.py              # Job management tests
│   ├── test_models.py            # Model tests
│   └── test_services.py          # Service tests
├── traefik/                       # Reverse proxy config
│   ├── certs/
│   │   └── generate-self-signed.sh
│   ├── dynamic.yml
│   └── traefik.yml
├── worker/                        # Background worker
│   ├── __init__.py
│   ├── main.py                   # Worker application
│   ├── tasks.py                  # Celery tasks
│   ├── processors/               # Processing modules
│   │   ├── __init__.py
│   │   ├── analysis.py
│   │   ├── streaming.py
│   │   └── video.py
│   └── utils/                    # Worker utilities
│       ├── __init__.py
│       ├── ffmpeg.py
│       ├── progress.py
│       ├── quality.py
│       └── resource_manager.py
├── docker-compose.yml             # Main compose file
├── docker-compose.prod.yml        # Production overrides
├── docker-compose.stable.yml      # Stable build config
├── requirements.txt               # Python dependencies
├── README.md                     # Project documentation
├── LICENSE                       # License file
├── VERSION                       # Version information
├── SECURITY.md                   # Security documentation
├── DEPLOYMENT.md                 # Deployment documentation
├── AUDIT_REPORT.md               # Audit report
└── PRODUCTION_READINESS_AUDIT.md # Production readiness audit
```

## Key Features

### Clean Architecture
- **Separation of Concerns**: Clear separation between API, business logic, and data layers
- **Modular Design**: Each component has a specific responsibility
- **Testable**: Comprehensive test suite with proper mocking

### Production Ready
- **CI/CD Pipeline**: Automated testing, building, and deployment
- **Monitoring**: Grafana dashboards and Prometheus alerts
- **Security**: Authentication, authorization, and security middleware
- **Backup**: Automated database backup with encryption

### Docker Support
- **Multi-stage Builds**: Optimized container images
- **Stable Dependencies**: Pinned versions for consistency
- **Health Checks**: Container health monitoring
- **Multi-environment**: Development, staging, and production configs

### Kubernetes Ready
- **Manifests**: Production-ready Kubernetes deployments
- **Security**: Non-root containers with security contexts
- **Scaling**: Horizontal pod autoscaling support
- **Secrets**: Proper secret management

## Removed Files

The following files and directories were removed during cleanup:

### Removed Files:
- `Dockerfile.genai` - GenAI-specific Dockerfile
- `rendiff` - Orphaned file
- `setup.py` & `setup.sh` - Old setup scripts
- `requirements-genai.txt` - GenAI requirements
- `docker-compose.genai.yml` - GenAI compose file
- `config/storage.yml*` - Old storage configs
- `docs/AUDIT_REPORT.md` - Duplicate audit report

### Removed Directories:
- `api/genai/` - GenAI module
- `cli/` - Command-line interface
- `setup/` - Setup utilities
- `storage/` - Storage abstractions
- `docker/setup/` - Docker setup
- `docker/traefik/` - Traefik configs
- `k8s/overlays/` - Empty overlays

### Removed Scripts:
- SSL management scripts
- Traefik management scripts
- System updater scripts
- Interactive setup scripts

## File Organization Principles

1. **Logical Grouping**: Related files are grouped in appropriate directories
2. **Clear Naming**: Files and directories have descriptive names
3. **Consistent Structure**: Similar components follow the same organization pattern
4. **Minimal Root**: Only essential files in the root directory
5. **Documentation**: Each major component has appropriate documentation

## Next Steps

1. **Development**: Use the clean structure for new feature development
2. **Testing**: Expand test coverage using the organized test suite
3. **Deployment**: Deploy using the CI/CD pipeline and K8s manifests
4. **Monitoring**: Set up monitoring using the provided configurations
5. **Maintenance**: Follow the backup and maintenance procedures

This clean structure provides a solid foundation for production deployment and future development.