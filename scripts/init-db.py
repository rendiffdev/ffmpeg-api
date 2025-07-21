#!/usr/bin/env python3
"""
Database initialization script for Rendiff
Creates tables and initial data
"""
import os
import sys
import asyncio
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import structlog
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from api.config import settings
from api.models.database import Base
from api.models.job import Job
from api.models.user import User

logger = structlog.get_logger()

def create_sync_engine():
    """Create synchronous engine for initial setup"""
    if "sqlite" in settings.DATABASE_URL:
        # Convert async URL to sync for initial setup
        sync_url = settings.DATABASE_URL.replace("sqlite+aiosqlite://", "sqlite:///")
        engine = create_engine(
            sync_url,
            connect_args={"check_same_thread": False},
            echo=settings.DEBUG
        )
    else:
        # For PostgreSQL, use psycopg2 instead of asyncpg
        sync_url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
        engine = create_engine(sync_url, echo=settings.DEBUG)
    
    return engine

async def create_async_engine_instance():
    """Create async engine for async operations"""
    if "sqlite" in settings.DATABASE_URL:
        engine = create_async_engine(
            settings.DATABASE_URL,
            connect_args={"check_same_thread": False},
            echo=settings.DEBUG
        )
    else:
        engine = create_async_engine(settings.DATABASE_URL, echo=settings.DEBUG)
    
    return engine

def init_sqlite_pragmas(engine):
    """Configure SQLite for optimal performance"""
    if "sqlite" in str(engine.url):
        logger.info("Configuring SQLite pragmas...")
        
        with engine.connect() as conn:
            # Enable WAL mode for better concurrency
            conn.execute(text("PRAGMA journal_mode=WAL"))
            
            # Set cache size (negative value = KB, positive = pages)
            conn.execute(text("PRAGMA cache_size=-64000"))  # 64MB cache
            
            # Enable foreign keys
            conn.execute(text("PRAGMA foreign_keys=ON"))
            
            # Set synchronous mode
            conn.execute(text("PRAGMA synchronous=NORMAL"))
            
            # Set temp store in memory
            conn.execute(text("PRAGMA temp_store=MEMORY"))
            
            # Set mmap size (256MB)
            conn.execute(text("PRAGMA mmap_size=268435456"))
            
            conn.commit()

def create_data_directory():
    """Ensure data directory exists for SQLite"""
    if "sqlite" in settings.DATABASE_URL:
        db_path = Path(settings.DATABASE_URL.replace("sqlite+aiosqlite:///", ""))
        db_path.parent.mkdir(parents=True, exist_ok=True)
        logger.info(f"Ensured data directory exists: {db_path.parent}")

def check_database_connection():
    """Test database connection"""
    logger.info("Testing database connection...")
    
    try:
        engine = create_sync_engine()
        
        with engine.connect() as conn:
            if "sqlite" in str(engine.url):
                result = conn.execute(text("SELECT sqlite_version()"))
                version = result.fetchone()[0]
                logger.info(f"Connected to SQLite version: {version}")
            else:
                result = conn.execute(text("SELECT version()"))
                version = result.fetchone()[0]
                logger.info(f"Connected to PostgreSQL: {version[:50]}...")
        
        engine.dispose()
        return True
        
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return False

def create_tables():
    """Create all database tables"""
    logger.info("Creating database tables...")
    
    try:
        engine = create_sync_engine()
        
        # Configure SQLite if needed
        init_sqlite_pragmas(engine)
        
        # Create all tables
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")
        
        engine.dispose()
        return True
        
    except Exception as e:
        logger.error(f"Failed to create tables: {e}")
        return False

async def create_initial_data():
    """Create initial data if needed"""
    logger.info("Creating initial data...")
    
    try:
        engine = await create_async_engine_instance()
        async_session = async_sessionmaker(engine, expire_on_commit=False)
        
        async with async_session() as session:
            # Check if we need to create initial data
            from sqlalchemy import select
            
            # For now, just ensure the tables are accessible
            # In the future, we could create default users, settings, etc.
            result = await session.execute(text("SELECT COUNT(*) FROM jobs"))
            job_count = result.scalar()
            logger.info(f"Found {job_count} existing jobs")
            
            await session.commit()
        
        await engine.dispose()
        return True
        
    except Exception as e:
        logger.error(f"Failed to create initial data: {e}")
        return False

async def verify_database():
    """Verify database is working correctly"""
    logger.info("Verifying database...")
    
    try:
        engine = await create_async_engine_instance()
        async_session = async_sessionmaker(engine, expire_on_commit=False)
        
        async with async_session() as session:
            # Test basic operations
            await session.execute(text("SELECT 1"))
            
            # Test each table
            tables = ['jobs', 'users']
            for table in tables:
                try:
                    result = await session.execute(text(f"SELECT COUNT(*) FROM {table}"))
                    count = result.scalar()
                    logger.info(f"Table '{table}': {count} records")
                except Exception as e:
                    logger.warning(f"Table '{table}' check failed: {e}")
        
        await engine.dispose()
        logger.info("Database verification completed")
        return True
        
    except Exception as e:
        logger.error(f"Database verification failed: {e}")
        return False

def migration_needed():
    """Check if database migration is needed"""
    # For future use - check schema versions, etc.
    return False

def run_migrations():
    """Run database migrations if needed"""
    if migration_needed():
        logger.info("Running database migrations...")
        # Future: Alembic or custom migration logic
        pass
    else:
        logger.info("No migrations needed")

async def main():
    """Main initialization process"""
    logger.info("=== Rendiff Database Initialization ===")
    
    # Step 1: Create data directory
    create_data_directory()
    
    # Step 2: Test connection
    if not check_database_connection():
        logger.error("Database connection failed - aborting")
        return False
    
    # Step 3: Run migrations if needed
    run_migrations()
    
    # Step 4: Create tables
    if not create_tables():
        logger.error("Table creation failed - aborting")
        return False
    
    # Step 5: Create initial data
    if not await create_initial_data():
        logger.warning("Initial data creation failed - continuing")
    
    # Step 6: Verify everything works
    if not await verify_database():
        logger.error("Database verification failed")
        return False
    
    logger.info("=== Database initialization completed successfully ===")
    return True

if __name__ == "__main__":
    import asyncio
    
    # Configure logging
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("Database initialization cancelled")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        sys.exit(1)