"""
Connection pooling for storage backends to reduce overhead
"""
import asyncio
from typing import Dict, Any, Optional
from contextlib import asynccontextmanager
import structlog

logger = structlog.get_logger()

class StorageConnectionPool:
    """Connection pool manager for storage backends."""
    
    def __init__(self, max_connections: int = 20, timeout: float = 30.0):
        self.max_connections = max_connections
        self.timeout = timeout
        self.pools: Dict[str, asyncio.Queue] = {}
        self.active_connections: Dict[str, int] = {}
    
    async def get_pool(self, backend_name: str) -> asyncio.Queue:
        """Get or create connection pool for backend."""
        if backend_name not in self.pools:
            self.pools[backend_name] = asyncio.Queue(maxsize=self.max_connections)
            self.active_connections[backend_name] = 0
        return self.pools[backend_name]
    
    @asynccontextmanager
    async def get_connection(self, backend_name: str, backend_factory):
        """Get connection from pool or create new one."""
        pool = await self.get_pool(backend_name)
        connection = None
        
        try:
            # Try to get existing connection from pool
            connection = pool.get_nowait()
            logger.debug(f"Reusing pooled connection for {backend_name}")
        except asyncio.QueueEmpty:
            # Create new connection if pool is empty and under limit
            if self.active_connections[backend_name] < self.max_connections:
                try:
                    connection = await asyncio.wait_for(
                        backend_factory(), 
                        timeout=self.timeout
                    )
                    self.active_connections[backend_name] += 1
                    logger.debug(f"Created new connection for {backend_name}")
                except asyncio.TimeoutError:
                    logger.error(f"Connection timeout for {backend_name}")
                    raise
            else:
                # Wait for connection to become available
                try:
                    connection = await asyncio.wait_for(
                        pool.get(), 
                        timeout=self.timeout
                    )
                    logger.debug(f"Got connection from pool for {backend_name}")
                except asyncio.TimeoutError:
                    logger.error(f"Pool exhausted for {backend_name}")
                    raise
        
        try:
            yield connection
        finally:
            # Return connection to pool if still valid
            if connection and self._is_connection_valid(connection):
                try:
                    pool.put_nowait(connection)
                    logger.debug(f"Returned connection to pool for {backend_name}")
                except asyncio.QueueFull:
                    # Pool is full, close the connection
                    await self._close_connection(connection)
                    self.active_connections[backend_name] -= 1
            else:
                # Connection is invalid, create new one next time
                if connection:
                    await self._close_connection(connection)
                    self.active_connections[backend_name] -= 1
    
    def _is_connection_valid(self, connection) -> bool:
        """Check if connection is still valid."""
        # Basic validation - can be extended per backend type
        return hasattr(connection, 'is_connected') and getattr(connection, 'is_connected', True)
    
    async def _close_connection(self, connection):
        """Close a connection properly."""
        try:
            if hasattr(connection, 'close'):
                await connection.close()
            elif hasattr(connection, 'disconnect'):
                await connection.disconnect()
        except Exception as e:
            logger.warning(f"Error closing connection: {e}")
    
    async def close_all(self):
        """Close all pooled connections."""
        for backend_name, pool in self.pools.items():
            while not pool.empty():
                try:
                    connection = pool.get_nowait()
                    await self._close_connection(connection)
                except asyncio.QueueEmpty:
                    break
            self.active_connections[backend_name] = 0
        logger.info("All storage connections closed")

# Global connection pool instance
storage_pool = StorageConnectionPool()