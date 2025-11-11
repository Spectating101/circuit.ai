"""
Database Connection Manager

Handles:
- SQLAlchemy engine creation
- Session management
- Connection pooling
- Multiple database support
"""

import os
from typing import AsyncGenerator, Optional
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from loguru import logger

# Base for all models
Base = declarative_base()


class DatabaseConfig:
    """Database configuration."""

    def __init__(self):
        """Initialize database configuration from environment."""
        self.database_url = os.getenv(
            "DATABASE_URL",
            "postgresql://circuit_ai:password@localhost:5432/circuit_ai"
        )

        # Convert postgres:// to postgresql:// for SQLAlchemy
        if self.database_url.startswith("postgres://"):
            self.database_url = self.database_url.replace("postgres://", "postgresql://", 1)

        # For async support
        self.async_database_url = self.database_url
        if self.async_database_url.startswith("postgresql://"):
            self.async_database_url = self.async_database_url.replace(
                "postgresql://", "postgresql+asyncpg://", 1
            )

        # Connection pool settings
        self.pool_size = int(os.getenv("DB_POOL_SIZE", "10"))
        self.max_overflow = int(os.getenv("DB_MAX_OVERFLOW", "20"))
        self.pool_timeout = int(os.getenv("DB_POOL_TIMEOUT", "30"))
        self.pool_recycle = int(os.getenv("DB_POOL_RECYCLE", "3600"))

        # Query settings
        self.echo_sql = os.getenv("DB_ECHO_SQL", "false").lower() == "true"


class DatabaseManager:
    """Database connection manager."""

    def __init__(self, config: Optional[DatabaseConfig] = None):
        """
        Initialize database manager.

        Args:
            config: Database configuration
        """
        self.config = config or DatabaseConfig()
        self._engine = None
        self._async_engine = None
        self._session_factory = None
        self._async_session_factory = None

    def get_engine(self):
        """
        Get sync database engine (lazy initialization).

        Returns:
            SQLAlchemy Engine
        """
        if self._engine is None:
            self._engine = create_engine(
                self.config.database_url,
                pool_size=self.config.pool_size,
                max_overflow=self.config.max_overflow,
                pool_timeout=self.config.pool_timeout,
                pool_recycle=self.config.pool_recycle,
                echo=self.config.echo_sql,
                pool_pre_ping=True,  # Verify connections before using
            )
            logger.info(f"Database engine created: {self._mask_url(self.config.database_url)}")

        return self._engine

    def get_async_engine(self):
        """
        Get async database engine (lazy initialization).

        Returns:
            SQLAlchemy AsyncEngine
        """
        if self._async_engine is None:
            self._async_engine = create_async_engine(
                self.config.async_database_url,
                pool_size=self.config.pool_size,
                max_overflow=self.config.max_overflow,
                pool_timeout=self.config.pool_timeout,
                pool_recycle=self.config.pool_recycle,
                echo=self.config.echo_sql,
                pool_pre_ping=True,
            )
            logger.info(f"Async database engine created: {self._mask_url(self.config.async_database_url)}")

        return self._async_engine

    def get_session_factory(self):
        """
        Get sync session factory (lazy initialization).

        Returns:
            SQLAlchemy sessionmaker
        """
        if self._session_factory is None:
            self._session_factory = sessionmaker(
                bind=self.get_engine(),
                autocommit=False,
                autoflush=False,
            )
            logger.debug("Session factory created")

        return self._session_factory

    def get_async_session_factory(self):
        """
        Get async session factory (lazy initialization).

        Returns:
            SQLAlchemy async_sessionmaker
        """
        if self._async_session_factory is None:
            self._async_session_factory = async_sessionmaker(
                bind=self.get_async_engine(),
                class_=AsyncSession,
                autocommit=False,
                autoflush=False,
                expire_on_commit=False,
            )
            logger.debug("Async session factory created")

        return self._async_session_factory

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Async context manager for database sessions.

        Yields:
            AsyncSession

        Example:
            async with db_manager.session() as session:
                result = await session.execute(query)
                await session.commit()
        """
        session_factory = self.get_async_session_factory()
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception as e:
                await session.rollback()
                logger.error(f"Database session error: {e}")
                raise
            finally:
                await session.close()

    async def create_all_tables(self):
        """
        Create all tables defined in models.

        Note: In production, use Alembic migrations instead.
        """
        # Import all models to ensure they're registered
        from src.models import analytics_models, webhook_models, admin_models

        async with self.get_async_engine().begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            logger.info("All database tables created")

    async def drop_all_tables(self):
        """
        Drop all tables.

        WARNING: Only use in development/testing!
        """
        async with self.get_async_engine().begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            logger.warning("All database tables dropped")

    async def close(self):
        """Close all database connections."""
        if self._async_engine:
            await self._async_engine.dispose()
            logger.info("Async database engine disposed")

        if self._engine:
            self._engine.dispose()
            logger.info("Database engine disposed")

    def _mask_url(self, url: str) -> str:
        """
        Mask sensitive parts of database URL for logging.

        Args:
            url: Database URL

        Returns:
            Masked URL
        """
        if "@" in url:
            parts = url.split("@")
            credentials_part = parts[0]
            if "://" in credentials_part:
                protocol, credentials = credentials_part.split("://", 1)
                if ":" in credentials:
                    username = credentials.split(":", 1)[0]
                    return f"{protocol}://{username}:***@{parts[1]}"
        return url


# Global database manager instance
db_manager = DatabaseManager()


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency for FastAPI to get database session.

    Yields:
        AsyncSession

    Example:
        @app.get("/users")
        async def get_users(session: AsyncSession = Depends(get_db_session)):
            result = await session.execute(select(User))
            return result.scalars().all()
    """
    async with db_manager.session() as session:
        yield session


async def init_database():
    """
    Initialize database on application startup.

    Call this in FastAPI startup event.
    """
    logger.info("Initializing database...")

    # Test connection
    try:
        async with db_manager.session() as session:
            await session.execute("SELECT 1")
            logger.info("Database connection verified")
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        raise

    logger.info("Database initialization complete")


async def close_database():
    """
    Close database connections on application shutdown.

    Call this in FastAPI shutdown event.
    """
    logger.info("Closing database connections...")
    await db_manager.close()
    logger.info("Database connections closed")
