"""
Database connection and session management.
"""

from typing import Optional
from contextlib import contextmanager
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from polyarb.data.models import Base


class Database:
    """
    Database connection manager for Polymarket data storage.
    """
    
    def __init__(
        self, 
        database_url: Optional[str] = None,
        echo: bool = False,
        pool_size: int = 5,
        max_overflow: int = 10
    ):
        """
        Initialize database connection.
        
        Args:
            database_url: PostgreSQL connection URL (e.g., 'postgresql://user:pass@host:port/db')
                         If None, uses in-memory SQLite for testing
            echo: Whether to log SQL statements
            pool_size: Connection pool size
            max_overflow: Max overflow connections
        """
        if database_url is None:
            # Use in-memory SQLite for testing/development
            database_url = "sqlite:///:memory:"
            self.engine = create_engine(
                database_url,
                echo=echo,
                connect_args={"check_same_thread": False},
                poolclass=StaticPool
            )
        else:
            self.engine = create_engine(
                database_url,
                echo=echo,
                pool_size=pool_size,
                max_overflow=max_overflow,
                pool_pre_ping=True  # Verify connections before using
            )
        
        self.SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine
        )
        
        self._initialized = False
    
    def initialize(self) -> None:
        """
        Initialize database schema (create tables).
        """
        Base.metadata.create_all(bind=self.engine)
        self._initialized = True
    
    def drop_all(self) -> None:
        """
        Drop all tables (for testing/development).
        """
        Base.metadata.drop_all(bind=self.engine)
        self._initialized = False
    
    @contextmanager
    def session(self) -> Session:
        """
        Provide a transactional scope for database operations.
        
        Usage:
            with db.session() as session:
                event = session.query(Event).first()
        
        Yields:
            Database session
        """
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    
    def get_session(self) -> Session:
        """
        Get a new database session (caller must close it).
        
        Returns:
            Database session
        """
        return self.SessionLocal()
    
    @property
    def is_initialized(self) -> bool:
        """Check if database is initialized."""
        return self._initialized
