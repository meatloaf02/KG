"""
Memgraph connection module using neo4j Python driver.

Memgraph is compatible with the Bolt protocol, so we can use the
neo4j Python driver for connections. This avoids the mgclient C
extension dependency issues.

Provides connection management, query execution, and retry logic
for the Memgraph knowledge graph database.
"""

import time
from contextlib import contextmanager
from typing import Any, Generator, Optional

from neo4j import GraphDatabase
from neo4j.exceptions import Neo4jError, ServiceUnavailable

from config import MEMGRAPH_HOST, MEMGRAPH_PORT, setup_logging

logger = setup_logging(__name__)

# Global driver instance (lazy initialization)
_driver = None


class MemgraphConnectionError(Exception):
    """Raised when connection to Memgraph fails."""

    pass


class MemgraphQueryError(Exception):
    """Raised when a Memgraph query fails."""

    pass


def get_driver(
    host: Optional[str] = None,
    port: Optional[int] = None,
) -> GraphDatabase.driver:
    """
    Get or create a Memgraph driver instance.

    Args:
        host: Memgraph host (defaults to config)
        port: Memgraph port (defaults to config)

    Returns:
        Neo4j driver instance (compatible with Memgraph)
    """
    global _driver

    if _driver is not None:
        return _driver

    host = host or MEMGRAPH_HOST
    port = port or MEMGRAPH_PORT
    uri = f"bolt://{host}:{port}"

    logger.info(f"Creating Memgraph connection to {uri}")

    try:
        # Memgraph doesn't require authentication by default
        _driver = GraphDatabase.driver(uri, auth=None)
        # Verify connection
        _driver.verify_connectivity()
        return _driver
    except Exception as e:
        raise MemgraphConnectionError(f"Failed to connect to Memgraph: {e}") from e


def get_memgraph(
    host: Optional[str] = None,
    port: Optional[int] = None,
    lazy: bool = True,
):
    """
    Get a Memgraph connection (alias for get_driver for compatibility).

    Args:
        host: Memgraph host (defaults to config)
        port: Memgraph port (defaults to config)
        lazy: Ignored (kept for API compatibility)

    Returns:
        Neo4j driver instance
    """
    return get_driver(host=host, port=port)


def close_connection() -> None:
    """Close the global Memgraph connection."""
    global _driver

    if _driver is not None:
        logger.info("Closing Memgraph connection")
        _driver.close()
        _driver = None


@contextmanager
def memgraph_session(
    host: Optional[str] = None,
    port: Optional[int] = None,
) -> Generator[Any, None, None]:
    """
    Context manager for Memgraph sessions.

    Usage:
        with memgraph_session() as session:
            session.run("MATCH (n) RETURN n LIMIT 10")

    Args:
        host: Memgraph host
        port: Memgraph port

    Yields:
        Neo4j session instance
    """
    driver = get_driver(host=host, port=port)
    session = driver.session()
    try:
        yield session
    finally:
        session.close()


def execute_query(
    query: str,
    parameters: Optional[dict] = None,
    driver=None,
) -> list[dict[str, Any]]:
    """
    Execute a Cypher query and return results.

    Args:
        query: Cypher query string
        parameters: Query parameters
        driver: Optional driver instance (uses global if not provided)

    Returns:
        List of result dictionaries
    """
    driver = driver or get_driver()
    parameters = parameters or {}

    try:
        with driver.session() as session:
            result = session.run(query, parameters)
            return [dict(record) for record in result]
    except Neo4jError as e:
        raise MemgraphQueryError(f"Query failed: {e}") from e


def execute_query_with_retry(
    query: str,
    parameters: Optional[dict] = None,
    driver=None,
    max_retries: int = 3,
    retry_delay: float = 1.0,
) -> list[dict[str, Any]]:
    """
    Execute a Cypher query with retry logic.

    Args:
        query: Cypher query string
        parameters: Query parameters
        driver: Optional driver instance
        max_retries: Maximum number of retries
        retry_delay: Delay between retries in seconds

    Returns:
        List of result dictionaries

    Raises:
        MemgraphQueryError: If query fails after all retries
    """
    driver = driver or get_driver()
    parameters = parameters or {}
    last_error = None

    for attempt in range(max_retries + 1):
        try:
            with driver.session() as session:
                result = session.run(query, parameters)
                return [dict(record) for record in result]
        except (Neo4jError, ServiceUnavailable) as e:
            last_error = e
            if attempt < max_retries:
                logger.warning(
                    f"Query attempt {attempt + 1} failed: {e}. "
                    f"Retrying in {retry_delay}s..."
                )
                time.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
            else:
                logger.error(f"Query failed after {max_retries + 1} attempts")

    raise MemgraphQueryError(f"Query failed after retries: {last_error}") from last_error


def execute_write(
    query: str,
    parameters: Optional[dict] = None,
    driver=None,
) -> None:
    """
    Execute a write query (no return value expected).

    Args:
        query: Cypher query string
        parameters: Query parameters
        driver: Optional driver instance
    """
    driver = driver or get_driver()
    parameters = parameters or {}

    try:
        with driver.session() as session:
            session.run(query, parameters)
    except Neo4jError as e:
        raise MemgraphQueryError(f"Write query failed: {e}") from e


def execute_many(
    queries: list[str],
    driver=None,
    stop_on_error: bool = False,
) -> dict[str, Any]:
    """
    Execute multiple queries.

    Args:
        queries: List of Cypher queries
        driver: Optional driver instance
        stop_on_error: If True, stop on first error

    Returns:
        Dictionary with success/failure counts
    """
    driver = driver or get_driver()
    stats = {"success": 0, "failed": 0, "errors": []}

    with driver.session() as session:
        for query in queries:
            try:
                session.run(query)
                stats["success"] += 1
            except Neo4jError as e:
                stats["failed"] += 1
                stats["errors"].append(str(e))
                if stop_on_error:
                    raise MemgraphQueryError(f"Query failed: {e}") from e

    return stats


def check_connection(driver=None) -> bool:
    """
    Check if Memgraph connection is working.

    Args:
        driver: Optional driver instance

    Returns:
        True if connection is working
    """
    driver = driver or get_driver()

    try:
        with driver.session() as session:
            result = session.run("RETURN 1 as test")
            record = result.single()
            return record is not None and record["test"] == 1
    except Exception as e:
        logger.error(f"Connection check failed: {e}")
        return False


def get_node_count(label: Optional[str] = None, driver=None) -> int:
    """
    Get count of nodes, optionally filtered by label.

    Args:
        label: Optional node label to filter by
        driver: Optional driver instance

    Returns:
        Node count
    """
    driver = driver or get_driver()

    if label:
        query = f"MATCH (n:{label}) RETURN count(n) as count"
    else:
        query = "MATCH (n) RETURN count(n) as count"

    results = execute_query(query, driver=driver)
    return results[0]["count"] if results else 0


def get_relationship_count(
    rel_type: Optional[str] = None, driver=None
) -> int:
    """
    Get count of relationships, optionally filtered by type.

    Args:
        rel_type: Optional relationship type to filter by
        driver: Optional driver instance

    Returns:
        Relationship count
    """
    driver = driver or get_driver()

    if rel_type:
        query = f"MATCH ()-[r:{rel_type}]->() RETURN count(r) as count"
    else:
        query = "MATCH ()-[r]->() RETURN count(r) as count"

    results = execute_query(query, driver=driver)
    return results[0]["count"] if results else 0


def get_database_stats(driver=None) -> dict[str, Any]:
    """
    Get database statistics.

    Args:
        driver: Optional driver instance

    Returns:
        Dictionary with database statistics
    """
    driver = driver or get_driver()

    # Get node counts by label
    label_query = """
    MATCH (n)
    RETURN labels(n) as labels, count(*) as count
    """
    label_results = execute_query(label_query, driver=driver)

    # Get relationship counts by type
    rel_query = """
    MATCH ()-[r]->()
    RETURN type(r) as type, count(*) as count
    """
    rel_results = execute_query(rel_query, driver=driver)

    return {
        "total_nodes": get_node_count(driver=driver),
        "total_relationships": get_relationship_count(driver=driver),
        "nodes_by_label": {
            r["labels"][0] if r["labels"] else "unlabeled": r["count"]
            for r in label_results
        },
        "relationships_by_type": {r["type"]: r["count"] for r in rel_results},
    }


def clear_database(driver=None, confirm: bool = False) -> None:
    """
    Clear all data from the database.

    WARNING: This deletes all nodes and relationships!

    Args:
        driver: Optional driver instance
        confirm: Must be True to actually clear the database
    """
    if not confirm:
        raise ValueError("Must set confirm=True to clear database")

    driver = driver or get_driver()
    logger.warning("Clearing all data from Memgraph database!")

    execute_write("MATCH (n) DETACH DELETE n", driver=driver)
    logger.info("Database cleared")
