import os
import logging
from contextlib import contextmanager
import psycopg2
from psycopg2.pool import SimpleConnectionPool
from psycopg2.extras import RealDictCursor
from typing import Generator, Optional

from services.exceptions import DatabaseError

logger = logging.getLogger(__name__)

# Global connection pool (singleton)
_connection_pool: Optional[SimpleConnectionPool] = None

# PostgreSQL connection configuration from environment variables
# NO DEFAULT VALUES - must be set in .env file
POSTGRES_HOST = os.getenv("POSTGRES_HOST")
POSTGRES_PORT = os.getenv("POSTGRES_PORT")
POSTGRES_DB = os.getenv("POSTGRES_DB")
POSTGRES_USER = os.getenv("POSTGRES_USER")
POSTGRES_PASSWORD_RAW = os.getenv("POSTGRES_PASSWORD")

if not all([POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD_RAW]):
    raise ValueError("PostgreSQL configuration missing! Check .env file for: POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD")

# Remove quotes (single or double) from password if present
POSTGRES_PASSWORD = POSTGRES_PASSWORD_RAW.strip("'\"")


def get_connection_params() -> dict:
    """
    Get PostgreSQL connection parameters from environment variables.
    
    Includes explicit timeout configuration for production readiness.
    Timeout is loaded from system.ini [resilience] section.
    """
    from services.config_service import get_config_service
    
    config = get_config_service()
    timeout_seconds = int(config.get_database_timeout())
    
    return {
        "host": POSTGRES_HOST,
        "port": POSTGRES_PORT,
        "database": POSTGRES_DB,
        "user": POSTGRES_USER,
        "password": POSTGRES_PASSWORD,
        "client_encoding": "UTF8",  # Force UTF-8 encoding
        "connect_timeout": timeout_seconds,  # Connection timeout in seconds (from system.ini)
    }


def get_connection_pool() -> SimpleConnectionPool:
    """
    Get or create the PostgreSQL connection pool (singleton).
    
    Connection pooling reduces overhead of creating new connections
    for each database operation, improving performance under load.
    
    Pool configuration:
    - minconn=2: Keep 2 connections alive at minimum
    - maxconn=20: Allow up to 20 concurrent connections
    
    Returns:
        SimpleConnectionPool instance (thread-safe for basic usage)
    
    Note: For multi-threaded applications, consider ThreadedConnectionPool
    """
    global _connection_pool
    
    if _connection_pool is None:
        params = get_connection_params()
        
        try:
            _connection_pool = SimpleConnectionPool(
                minconn=2,   # Minimum connections to maintain
                maxconn=20,  # Maximum connections allowed
                **params
            )
            logger.info(
                f"✅ PostgreSQL connection pool initialized: "
                f"min={2}, max={20}, host={params['host']}, db={params['database']}"
            )
        except psycopg2.Error as e:
            logger.error(f"Failed to create connection pool: {e}", exc_info=True)
            raise DatabaseError(
                "Connection pool initialization failed",
                context={
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "host": params.get("host"),
                    "database": params.get("database")
                }
            ) from e
    
    return _connection_pool


@contextmanager
def get_db_connection() -> Generator:
    """Context manager for PostgreSQL database connections with connection pooling.
    
    Retrieves connection from pool, yields it with RealDictCursor,
    commits on success, rolls back on error, and returns to pool.
    
    Connection pooling benefits:
    - Reduced connection overhead
    - Better resource utilization
    - Improved performance under concurrent load
    
    Raises:
        DatabaseError: If connection or transaction fails
    """
    pool = get_connection_pool()
    conn = None
    
    try:
        # Get connection from pool (blocks if pool exhausted)
        conn = pool.getconn()
        
        # Ensure RealDictCursor for this connection
        conn.cursor_factory = RealDictCursor
        
        yield conn
        conn.commit()
    
    except psycopg2.OperationalError as e:
        if conn:
            conn.rollback()
        logger.error(f"Database connection error: {e}", exc_info=True)
        
        params = get_connection_params()
        raise DatabaseError(
            "PostgreSQL connection failed",
            context={
                "host": params.get("host"),
                "database": params.get("database"),
                "port": params.get("port"),
                "error_type": "OperationalError",
                "error_message": str(e)
            }
        ) from e
    
    except psycopg2.Error as e:
        if conn:
            conn.rollback()
        logger.error(f"Database error: {e}", exc_info=True)
        raise DatabaseError(
            "Database operation failed",
            context={
                "error_type": type(e).__name__,
                "error_message": str(e)
            }
        ) from e
    
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Unexpected database error: {e}", exc_info=True)
        raise DatabaseError(
            "Unexpected database error",
            context={
                "error_type": type(e).__name__,
                "error_message": str(e)
            }
        ) from e
    
    finally:
        if conn:
            # Return connection to pool (do NOT close)
            pool.putconn(conn)


def check_db_connection() -> tuple[bool, str]:
    """Check PostgreSQL database connection health.
    
    Returns:
        tuple: (success: bool, message: str)
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT 1 as check_value")
                result = cursor.fetchone()
                # RealDictCursor returns dict, not tuple
                if result and result.get('check_value') == 1:
                    return True, "Adatbázis kapcsolódás sikeres"
                return False, "Adatbázis válasz hibás"
    except psycopg2.OperationalError as e:
        error_msg = f"Adatbázis kapcsolódás sikertelen! Hiba: {str(e)}"
        logger.error(error_msg)
        return False, error_msg
    except Exception as e:
        error_msg = f"Adatbázis kapcsolódás sikertelen! Hiba: {str(e)}"
        logger.error(error_msg)
        return False, error_msg
