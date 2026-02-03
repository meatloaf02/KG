"""
Memgraph schema initialization CLI.

Creates indexes and constraints for the knowledge graph.
Idempotent - safe to run multiple times.

Usage:
    python -m kg.init              # Initialize schema
    python -m kg.init --seed       # Initialize with seed data
    python -m kg.init --drop       # Drop and recreate schema
    python -m kg.init --status     # Show database status
"""

import argparse
import sys
from pathlib import Path
from typing import Optional

from config import MEMGRAPH_HOST, MEMGRAPH_PORT, setup_logging

logger = setup_logging(__name__)


def init_schema(
    driver=None,
    include_seed_data: bool = False,
    drop_existing: bool = False,
) -> dict:
    """
    Initialize Memgraph schema with indexes and constraints.

    Args:
        driver: Optional driver instance
        include_seed_data: If True, load seed data (products, capabilities)
        drop_existing: If True, clear database first

    Returns:
        Dictionary with initialization statistics
    """
    from kg.connection import (
        clear_database,
        execute_many,
        execute_write,
        get_driver,
    )
    from kg.schema import (
        CONSTRAINT_QUERIES,
        INDEX_QUERIES,
    )

    driver = driver or get_driver()
    stats = {"constraints": 0, "indexes": 0, "seed_nodes": 0, "errors": []}

    # Clear database if requested
    if drop_existing:
        logger.warning("Dropping existing data...")
        clear_database(driver=driver, confirm=True)

    # Create constraints
    logger.info("Creating constraints...")
    for query in CONSTRAINT_QUERIES:
        try:
            execute_write(query, driver=driver)
            stats["constraints"] += 1
            logger.debug(f"Created constraint: {query[:50]}...")
        except Exception as e:
            # Constraint may already exist
            if "already exists" in str(e).lower():
                logger.debug(f"Constraint already exists: {query[:50]}...")
                stats["constraints"] += 1
            else:
                stats["errors"].append(f"Constraint error: {e}")
                logger.warning(f"Failed to create constraint: {e}")

    # Create indexes
    logger.info("Creating indexes...")
    for query in INDEX_QUERIES:
        try:
            execute_write(query, driver=driver)
            stats["indexes"] += 1
            logger.debug(f"Created index: {query[:50]}...")
        except Exception as e:
            # Index may already exist
            if "already exists" in str(e).lower():
                logger.debug(f"Index already exists: {query[:50]}...")
                stats["indexes"] += 1
            else:
                stats["errors"].append(f"Index error: {e}")
                logger.warning(f"Failed to create index: {e}")

    # Load seed data if requested
    if include_seed_data:
        logger.info("Loading seed data...")
        seed_stats = load_seed_data(driver=driver)
        stats["seed_nodes"] = seed_stats.get("nodes_created", 0)

    return stats


def load_seed_data(driver=None) -> dict:
    """
    Load seed data (Workday company, products, capabilities).

    Args:
        driver: Optional driver instance

    Returns:
        Dictionary with load statistics
    """
    from kg.connection import execute_write, get_driver

    driver = driver or get_driver()
    stats = {"nodes_created": 0, "relationships_created": 0}

    # Seed data queries
    seed_queries = [
        # Workday Company
        """
        MERGE (c:Company {id: 'workday'})
        ON CREATE SET
            c.name = 'Workday, Inc.',
            c.ticker = 'WDAY',
            c.cik = '0001327811',
            c.created_at = timestamp()
        """,
        # Products
        """
        MERGE (p:Product {id: 'workday-hcm'})
        ON CREATE SET
            p.name = 'Workday Human Capital Management',
            p.normalized_name = 'workday hcm',
            p.description = 'Human resources management suite',
            p.created_at = timestamp()
        """,
        """
        MERGE (p:Product {id: 'workday-financials'})
        ON CREATE SET
            p.name = 'Workday Financial Management',
            p.normalized_name = 'workday financials',
            p.description = 'Financial management and accounting suite',
            p.created_at = timestamp()
        """,
        """
        MERGE (p:Product {id: 'workday-planning'})
        ON CREATE SET
            p.name = 'Workday Adaptive Planning',
            p.normalized_name = 'workday planning',
            p.description = 'Enterprise planning and budgeting',
            p.created_at = timestamp()
        """,
        """
        MERGE (p:Product {id: 'workday-payroll'})
        ON CREATE SET
            p.name = 'Workday Payroll',
            p.normalized_name = 'workday payroll',
            p.description = 'Payroll processing solution',
            p.created_at = timestamp()
        """,
        """
        MERGE (p:Product {id: 'workday-recruiting'})
        ON CREATE SET
            p.name = 'Workday Recruiting',
            p.normalized_name = 'workday recruiting',
            p.description = 'Talent acquisition platform',
            p.created_at = timestamp()
        """,
        """
        MERGE (p:Product {id: 'workday-learning'})
        ON CREATE SET
            p.name = 'Workday Learning',
            p.normalized_name = 'workday learning',
            p.description = 'Learning management system',
            p.created_at = timestamp()
        """,
        """
        MERGE (p:Product {id: 'workday-prism'})
        ON CREATE SET
            p.name = 'Workday Prism Analytics',
            p.normalized_name = 'workday prism',
            p.description = 'Analytics and reporting platform',
            p.created_at = timestamp()
        """,
        """
        MERGE (p:Product {id: 'workday-peakon'})
        ON CREATE SET
            p.name = 'Workday Peakon Employee Voice',
            p.normalized_name = 'workday peakon',
            p.description = 'Employee engagement platform',
            p.created_at = timestamp()
        """,
        # AI/ML Capabilities
        """
        MERGE (cap:Capability {id: 'ai'})
        ON CREATE SET
            cap.name = 'Artificial Intelligence',
            cap.normalized_name = 'artificial intelligence',
            cap.category = 'artificial_intelligence',
            cap.created_at = timestamp()
        """,
        """
        MERGE (cap:Capability {id: 'ml'})
        ON CREATE SET
            cap.name = 'Machine Learning',
            cap.normalized_name = 'machine learning',
            cap.category = 'machine_learning',
            cap.created_at = timestamp()
        """,
        """
        MERGE (cap:Capability {id: 'nlp'})
        ON CREATE SET
            cap.name = 'Natural Language Processing',
            cap.normalized_name = 'natural language processing',
            cap.category = 'artificial_intelligence',
            cap.created_at = timestamp()
        """,
        """
        MERGE (cap:Capability {id: 'predictive-analytics'})
        ON CREATE SET
            cap.name = 'Predictive Analytics',
            cap.normalized_name = 'predictive analytics',
            cap.category = 'analytics',
            cap.created_at = timestamp()
        """,
        """
        MERGE (cap:Capability {id: 'automation'})
        ON CREATE SET
            cap.name = 'Automation',
            cap.normalized_name = 'automation',
            cap.category = 'automation',
            cap.created_at = timestamp()
        """,
        """
        MERGE (cap:Capability {id: 'generative-ai'})
        ON CREATE SET
            cap.name = 'Generative AI',
            cap.normalized_name = 'generative ai',
            cap.category = 'artificial_intelligence',
            cap.created_at = timestamp()
        """,
        """
        MERGE (cap:Capability {id: 'llm'})
        ON CREATE SET
            cap.name = 'Large Language Model',
            cap.normalized_name = 'large language model',
            cap.category = 'artificial_intelligence',
            cap.created_at = timestamp()
        """,
        """
        MERGE (cap:Capability {id: 'deep-learning'})
        ON CREATE SET
            cap.name = 'Deep Learning',
            cap.normalized_name = 'deep learning',
            cap.category = 'machine_learning',
            cap.created_at = timestamp()
        """,
        # Risk Topics
        """
        MERGE (r:RiskTopic {id: 'cybersecurity-risk'})
        ON CREATE SET
            r.name = 'Cybersecurity Risk',
            r.normalized_name = 'cybersecurity risk',
            r.category = 'cybersecurity',
            r.created_at = timestamp()
        """,
        """
        MERGE (r:RiskTopic {id: 'data-breach'})
        ON CREATE SET
            r.name = 'Data Breach',
            r.normalized_name = 'data breach',
            r.category = 'cybersecurity',
            r.created_at = timestamp()
        """,
        """
        MERGE (r:RiskTopic {id: 'regulatory-compliance'})
        ON CREATE SET
            r.name = 'Regulatory Compliance',
            r.normalized_name = 'regulatory compliance',
            r.category = 'regulatory',
            r.created_at = timestamp()
        """,
        """
        MERGE (r:RiskTopic {id: 'competition-risk'})
        ON CREATE SET
            r.name = 'Competition Risk',
            r.normalized_name = 'competition risk',
            r.category = 'competition',
            r.created_at = timestamp()
        """,
        """
        MERGE (r:RiskTopic {id: 'ai-ethics'})
        ON CREATE SET
            r.name = 'AI Ethics and Bias',
            r.normalized_name = 'ai ethics',
            r.category = 'technology',
            r.created_at = timestamp()
        """,
        # Company owns products
        """
        MATCH (c:Company {id: 'workday'})
        MATCH (p:Product)
        WHERE p.id STARTS WITH 'workday-'
        MERGE (c)-[:OWNS]->(p)
        """,
    ]

    for query in seed_queries:
        try:
            execute_write(query, driver=driver)
            stats["nodes_created"] += 1
        except Exception as e:
            logger.warning(f"Seed data error: {e}")

    logger.info(f"Loaded {stats['nodes_created']} seed data items")
    return stats


def show_status(driver=None) -> None:
    """
    Show database status and statistics.

    Args:
        driver: Optional driver instance
    """
    from kg.connection import check_connection, get_database_stats, get_driver

    driver = driver or get_driver()

    print("\n" + "=" * 50)
    print("Memgraph Database Status")
    print("=" * 50)

    # Connection check
    if check_connection(driver):
        print(f"Connection: OK ({MEMGRAPH_HOST}:{MEMGRAPH_PORT})")
    else:
        print(f"Connection: FAILED ({MEMGRAPH_HOST}:{MEMGRAPH_PORT})")
        return

    # Get statistics
    stats = get_database_stats(driver)

    print(f"\nTotal Nodes: {stats['total_nodes']}")
    print(f"Total Relationships: {stats['total_relationships']}")

    if stats["nodes_by_label"]:
        print("\nNodes by Label:")
        for label, count in sorted(stats["nodes_by_label"].items()):
            print(f"  {label}: {count}")

    if stats["relationships_by_type"]:
        print("\nRelationships by Type:")
        for rel_type, count in sorted(stats["relationships_by_type"].items()):
            print(f"  {rel_type}: {count}")

    print("=" * 50 + "\n")


def main():
    """Main CLI entrypoint."""
    parser = argparse.ArgumentParser(
        description="Memgraph Knowledge Graph Schema Initialization",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m kg.init              # Initialize schema (indexes, constraints)
  python -m kg.init --seed       # Initialize with seed data
  python -m kg.init --drop       # Drop all data and recreate schema
  python -m kg.init --status     # Show database status
  python -m kg.init --host localhost --port 7687
        """,
    )

    parser.add_argument(
        "--seed",
        action="store_true",
        help="Load seed data (Workday products, capabilities)",
    )
    parser.add_argument(
        "--drop",
        action="store_true",
        help="Drop existing data before initialization (WARNING: deletes all data)",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show database status and statistics",
    )
    parser.add_argument(
        "--host",
        type=str,
        default=None,
        help=f"Memgraph host (default: {MEMGRAPH_HOST})",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help=f"Memgraph port (default: {MEMGRAPH_PORT})",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose output",
    )

    args = parser.parse_args()

    # Set up logging level
    if args.verbose:
        import logging

        logging.getLogger().setLevel(logging.DEBUG)

    # Import here to handle connection errors gracefully
    try:
        from kg.connection import get_driver

        driver = get_driver(host=args.host, port=args.port)
    except Exception as e:
        print(f"Error: Could not connect to Memgraph: {e}")
        print(f"\nMake sure Memgraph is running on {args.host or MEMGRAPH_HOST}:{args.port or MEMGRAPH_PORT}")
        print("\nTo start Memgraph with Docker:")
        print("  docker compose up -d memgraph")
        sys.exit(1)

    try:
        # Status only
        if args.status:
            show_status(driver)
            return

        # Confirm drop
        if args.drop:
            response = input("WARNING: This will delete all data. Continue? [y/N] ")
            if response.lower() != "y":
                print("Aborted.")
                return

        # Initialize schema
        print(f"Initializing Memgraph schema on {args.host or MEMGRAPH_HOST}:{args.port or MEMGRAPH_PORT}...")

        stats = init_schema(
            driver=driver,
            include_seed_data=args.seed,
            drop_existing=args.drop,
        )

        print("\nInitialization complete:")
        print(f"  Constraints: {stats['constraints']}")
        print(f"  Indexes: {stats['indexes']}")
        if args.seed:
            print(f"  Seed nodes: {stats['seed_nodes']}")
        if stats["errors"]:
            print(f"  Errors: {len(stats['errors'])}")
            for error in stats["errors"][:5]:
                print(f"    - {error}")

        # Show final status
        show_status(driver)

    except KeyboardInterrupt:
        print("\nInterrupted by user.")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error: {e}")
        if args.verbose:
            import traceback

            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
