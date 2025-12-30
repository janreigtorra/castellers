"""
Database Connection Pool for PassaFaixa Question Generation

This module provides a connection pool to reuse database connections,
significantly reducing latency when generating multiple questions.
"""

import os
import psycopg2
from psycopg2 import pool
from contextlib import contextmanager
from dotenv import load_dotenv
import threading

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

# Global connection pool
_connection_pool = None
_pool_lock = threading.Lock()


def init_connection_pool(min_conn=2, max_conn=10):
    """
    Initialize the connection pool.
    
    Args:
        min_conn: Minimum number of connections in the pool
        max_conn: Maximum number of connections in the pool
    
    Should be called once at application startup.
    """
    global _connection_pool
    
    if not DATABASE_URL:
        raise ValueError("DATABASE_URL must be set in environment variables")
    
    with _pool_lock:
        if _connection_pool is None:
            try:
                _connection_pool = psycopg2.pool.ThreadedConnectionPool(
                    minconn=min_conn,
                    maxconn=max_conn,
                    dsn=DATABASE_URL
                )
                print(f"[DB Pool] Initialized connection pool (min={min_conn}, max={max_conn})")
            except Exception as e:
                raise Exception(f"Failed to create connection pool: {e}")
        else:
            print("[DB Pool] Connection pool already initialized")


def get_connection_pool():
    """
    Get the global connection pool.
    Initializes it if not already initialized.
    """
    global _connection_pool
    
    if _connection_pool is None:
        init_connection_pool()
    
    return _connection_pool


def _is_connection_healthy(conn):
    """
    Check if a connection is still healthy by running a simple query.
    Returns True if healthy, False otherwise.
    """
    try:
        # Check if connection is closed
        if conn.closed:
            return False
        # Try a simple query to verify connection is alive
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.fetchone()
        cur.close()
        return True
    except Exception:
        return False


@contextmanager
def get_db_connection():
    """
    Context manager for getting a database connection from the pool.
    
    Usage:
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT ...")
            rows = cur.fetchall()
            # Connection is automatically returned to pool
    """
    pool = get_connection_pool()
    conn = None
    conn_is_bad = False
    
    try:
        conn = pool.getconn()
        
        # Verify connection is healthy before using it
        if not _is_connection_healthy(conn):
            # Connection is stale, close it and get a new one
            try:
                pool.putconn(conn, close=True)
            except Exception:
                pass
            conn = pool.getconn()
            
            # If still unhealthy, try one more time
            if not _is_connection_healthy(conn):
                try:
                    pool.putconn(conn, close=True)
                except Exception:
                    pass
                conn = pool.getconn()
        
        yield conn
        
    except psycopg2.pool.PoolError as e:
        # If pool is exhausted, wait a bit and retry once
        import time
        time.sleep(0.1)
        try:
            conn = pool.getconn()
            yield conn
        except Exception as retry_e:
            raise Exception(f"Failed to get connection from pool (retry): {retry_e}")
    except (psycopg2.OperationalError, psycopg2.InterfaceError) as e:
        # Connection error - mark as bad so we close it instead of returning to pool
        conn_is_bad = True
        raise Exception(f"Database error: {e}")
    except Exception as e:
        raise Exception(f"Database error: {e}")
    finally:
        if conn:
            try:
                if conn_is_bad or conn.closed:
                    # Close the bad connection instead of returning to pool
                    pool.putconn(conn, close=True)
                else:
                    pool.putconn(conn)
            except Exception:
                # If we can't return the connection, just ignore
                pass


def close_connection_pool():
    """
    Close all connections in the pool.
    Should be called at application shutdown.
    """
    global _connection_pool
    
    with _pool_lock:
        if _connection_pool:
            _connection_pool.closeall()
            _connection_pool = None
            print("[DB Pool] Connection pool closed")


def get_pool_stats():
    """
    Get statistics about the connection pool.
    Returns dict with pool information.
    """
    pool = get_connection_pool()
    if hasattr(pool, '_used') and hasattr(pool, '_pool'):
        return {
            "used_connections": len(pool._used),
            "available_connections": len(pool._pool),
            "total_connections": len(pool._used) + len(pool._pool)
        }
    return {"status": "pool_active"}

