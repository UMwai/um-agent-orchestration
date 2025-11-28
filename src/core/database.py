"""
Database utilities and abstractions
"""

import sqlite3
import json
import threading
import time
from typing import Optional, Dict, Any, List
from contextlib import contextmanager
from collections import deque
from .exceptions import TaskError, safe_execute
from .config import get_config


class ConnectionPool:
    """Simple SQLite connection pool with resource limits"""

    def __init__(self, db_path: str, pool_size: int = 5, timeout: int = 30):
        self.db_path = db_path
        self.pool_size = pool_size
        self.timeout = timeout
        self.connections = deque()
        self.active_connections = 0
        self.lock = threading.Lock()

        # Create initial connections
        for _ in range(min(2, pool_size)):  # Start with 2 connections
            self._create_connection()

    def _create_connection(self) -> sqlite3.Connection:
        """Create a new database connection with optimal settings for concurrency"""
        conn = sqlite3.connect(
            self.db_path,
            check_same_thread=False,
            timeout=self.timeout,
            isolation_level=None,  # Autocommit mode for better concurrency
        )
        conn.row_factory = sqlite3.Row

        # Configure SQLite for optimal concurrent access
        conn.execute("PRAGMA journal_mode=WAL")  # Write-Ahead Logging
        conn.execute("PRAGMA synchronous=NORMAL")  # Good balance of safety/performance
        conn.execute("PRAGMA cache_size=-64000")  # 64MB cache
        conn.execute("PRAGMA temp_store=MEMORY")  # Store temp tables in memory
        conn.execute("PRAGMA mmap_size=268435456")  # 256MB memory map
        conn.execute("PRAGMA busy_timeout=30000")  # 30 second busy timeout
        conn.execute(
            "PRAGMA wal_autocheckpoint=1000"
        )  # Auto checkpoint every 1000 pages

        # Enable foreign key constraints for data integrity
        conn.execute("PRAGMA foreign_keys=ON")

        return conn

    @contextmanager
    def get_connection(self):
        """Get a connection from the pool"""
        conn = None
        try:
            with self.lock:
                if self.connections:
                    conn = self.connections.popleft()
                elif self.active_connections < self.pool_size:
                    conn = self._create_connection()
                    self.active_connections += 1
                else:
                    # Wait for a connection to become available
                    pass

            # If no connection available, wait and retry with exponential backoff
            if conn is None:
                start_time = time.time()
                wait_time = 0.001  # Start with 1ms
                while conn is None and time.time() - start_time < self.timeout:
                    time.sleep(wait_time)
                    wait_time = min(
                        wait_time * 2, 0.1
                    )  # Exponential backoff, max 100ms
                    with self.lock:
                        if self.connections:
                            conn = self.connections.popleft()
                            break

                if conn is None:
                    raise TaskError("Database connection timeout")

            # Verify connection is still valid and optimize if needed
            try:
                conn.execute("SELECT 1")
                # Periodically optimize connections (store timestamp in a dict to avoid modifying conn object)
                if not hasattr(self, "_conn_optimize_times"):
                    self._conn_optimize_times = {}

                conn_id = id(conn)
                last_optimized = self._conn_optimize_times.get(conn_id, 0)
                if time.time() - last_optimized > 3600:  # 1 hour
                    conn.execute("PRAGMA optimize")
                    self._conn_optimize_times[conn_id] = time.time()
            except sqlite3.Error:
                # Connection is stale, create a new one
                try:
                    conn.close()
                except:
                    pass
                conn = self._create_connection()

            yield conn

        except sqlite3.Error as e:
            if conn:
                conn.rollback()
            raise TaskError(f"Database error: {e}")
        finally:
            if conn:
                try:
                    # Return connection to pool
                    with self.lock:
                        if len(self.connections) < self.pool_size:
                            self.connections.append(conn)
                        else:
                            # Pool is full, close this connection
                            conn.close()
                            self.active_connections -= 1
                except sqlite3.Error:
                    # Connection is bad, close it
                    try:
                        conn.close()
                    except:
                        pass
                    with self.lock:
                        self.active_connections -= 1

    def close_all(self):
        """Close all connections in the pool"""
        with self.lock:
            while self.connections:
                conn = self.connections.popleft()
                try:
                    conn.close()
                except sqlite3.Error:
                    pass
            self.active_connections = 0


class DatabaseManager:
    """Manages database connections and common operations with pooling"""

    _pools = {}  # Class-level pool cache
    _pool_lock = threading.Lock()

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or get_config().db_path
        self._pool = self._get_or_create_pool()

    def _get_or_create_pool(self) -> ConnectionPool:
        """Get or create connection pool for this database"""
        with self._pool_lock:
            if self.db_path not in self._pools:
                self._pools[self.db_path] = ConnectionPool(self.db_path)
            return self._pools[self.db_path]

    @contextmanager
    def get_connection(self):
        """Get a database connection from the pool with proper cleanup"""
        with self._pool.get_connection() as conn:
            yield conn

    def execute_query(self, query: str, params: tuple = ()) -> List[sqlite3.Row]:
        """Execute a SELECT query and return results"""
        with self.get_connection() as conn:
            cursor = conn.execute(query, params)
            return cursor.fetchall()

    def execute_update(self, query: str, params: tuple = ()) -> int:
        """Execute an INSERT/UPDATE/DELETE query and return affected rows"""
        with self.get_connection() as conn:
            # Use explicit transaction for better concurrency control
            conn.execute("BEGIN IMMEDIATE")  # Acquire write lock immediately
            try:
                cursor = conn.execute(query, params)
                conn.commit()
                return cursor.rowcount
            except sqlite3.Error:
                conn.rollback()
                raise

    def serialize_json(self, data: Any) -> str:
        """Safely serialize data to JSON"""
        return json.dumps(data) if data else "{}"

    def deserialize_json(self, json_str: Optional[str]) -> Dict[str, Any]:
        """Safely deserialize JSON string"""
        if not json_str:
            return {}
        return safe_execute(lambda: json.loads(json_str), default={})

    def init_schema(self, schema_sql: str):
        """Initialize database schema with proper transaction handling"""
        with self.get_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                conn.execute(schema_sql)
                conn.commit()
            except sqlite3.Error:
                conn.rollback()
                raise

    @classmethod
    def cleanup_pools(cls):
        """Clean up all connection pools - call on shutdown"""
        with cls._pool_lock:
            for pool in cls._pools.values():
                pool.close_all()
            cls._pools.clear()

    def get_pool_stats(self) -> Dict[str, int]:
        """Get connection pool statistics"""
        with self._pool.lock:
            return {
                "available_connections": len(self._pool.connections),
                "active_connections": self._pool.active_connections,
                "pool_size": self._pool.pool_size,
                "total_pool_connections": len(self._pool.connections)
                + self._pool.active_connections,
            }

    def execute_transaction(self, operations: list) -> bool:
        """Execute multiple operations in a single transaction"""
        with self.get_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                for query, params in operations:
                    conn.execute(query, params)
                conn.commit()
                return True
            except sqlite3.Error:
                conn.rollback()
                return False

    def optimize_database(self):
        """Optimize database for better performance"""
        with self.get_connection() as conn:
            # Run VACUUM to optimize database file
            conn.execute("VACUUM")
            # Analyze tables to update query planner statistics
            conn.execute("ANALYZE")
            # Checkpoint WAL to reduce file size
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
