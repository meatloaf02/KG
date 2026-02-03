# Knowledge graph schema and operations module

from kg.connection import (
    # Connection management
    get_memgraph,
    close_connection,
    memgraph_session,
    check_connection,
    # Query execution
    execute_query,
    execute_query_with_retry,
    execute_write,
    execute_many,
    # Utilities
    get_node_count,
    get_relationship_count,
    get_database_stats,
    clear_database,
    # Exceptions
    MemgraphConnectionError,
    MemgraphQueryError,
)

from kg.init import (
    init_schema,
    load_seed_data,
    show_status,
)

from kg.schema import (
    # Node labels
    NODE_DOCUMENT,
    NODE_COMPANY,
    NODE_PRODUCT,
    NODE_CAPABILITY,
    NODE_RISK_TOPIC,
    NODE_EVENT,
    # Relationship types
    REL_MENTIONS,
    REL_DISCLOSES,
    REL_ANNOUNCES,
    REL_HAS_CAPABILITY,
    REL_OWNS,
    # Categories
    CAPABILITY_CATEGORIES,
    RISK_CATEGORIES,
    EVENT_TYPES,
    # Schema queries
    INDEX_QUERIES,
    CONSTRAINT_QUERIES,
    get_all_schema_queries,
    get_index_queries,
    get_constraint_queries,
    # Node creation templates
    CREATE_DOCUMENT,
    CREATE_COMPANY,
    CREATE_PRODUCT,
    CREATE_CAPABILITY,
    CREATE_RISK_TOPIC,
    CREATE_EVENT,
    # Relationship creation templates
    CREATE_MENTIONS_PRODUCT,
    CREATE_MENTIONS_CAPABILITY,
    CREATE_DISCLOSES,
    CREATE_ANNOUNCES_EVENT,
    CREATE_ANNOUNCES_CAPABILITY,
    CREATE_HAS_CAPABILITY,
    CREATE_OWNS,
    # Query templates
    GET_DOCUMENT_GRAPH,
    GET_CAPABILITY_TIMELINE,
    GET_RISKS_BY_CATEGORY,
    COUNT_MENTIONS_BY_QUARTER,
    GET_PRODUCT_CAPABILITIES,
    # Data classes
    Evidence,
    DocumentNode,
    CapabilityNode,
    ProductNode,
    RiskTopicNode,
    EventNode,
)

__all__ = [
    # Connection management
    "get_memgraph",
    "close_connection",
    "memgraph_session",
    "check_connection",
    # Query execution
    "execute_query",
    "execute_query_with_retry",
    "execute_write",
    "execute_many",
    # Connection utilities
    "get_node_count",
    "get_relationship_count",
    "get_database_stats",
    "clear_database",
    # Exceptions
    "MemgraphConnectionError",
    "MemgraphQueryError",
    # Schema initialization
    "init_schema",
    "load_seed_data",
    "show_status",
    # Node labels
    "NODE_DOCUMENT",
    "NODE_COMPANY",
    "NODE_PRODUCT",
    "NODE_CAPABILITY",
    "NODE_RISK_TOPIC",
    "NODE_EVENT",
    # Relationship types
    "REL_MENTIONS",
    "REL_DISCLOSES",
    "REL_ANNOUNCES",
    "REL_HAS_CAPABILITY",
    "REL_OWNS",
    # Categories
    "CAPABILITY_CATEGORIES",
    "RISK_CATEGORIES",
    "EVENT_TYPES",
    # Schema queries
    "INDEX_QUERIES",
    "CONSTRAINT_QUERIES",
    "get_all_schema_queries",
    "get_index_queries",
    "get_constraint_queries",
    # Node creation templates
    "CREATE_DOCUMENT",
    "CREATE_COMPANY",
    "CREATE_PRODUCT",
    "CREATE_CAPABILITY",
    "CREATE_RISK_TOPIC",
    "CREATE_EVENT",
    # Relationship creation templates
    "CREATE_MENTIONS_PRODUCT",
    "CREATE_MENTIONS_CAPABILITY",
    "CREATE_DISCLOSES",
    "CREATE_ANNOUNCES_EVENT",
    "CREATE_ANNOUNCES_CAPABILITY",
    "CREATE_HAS_CAPABILITY",
    "CREATE_OWNS",
    # Query templates
    "GET_DOCUMENT_GRAPH",
    "GET_CAPABILITY_TIMELINE",
    "GET_RISKS_BY_CATEGORY",
    "COUNT_MENTIONS_BY_QUARTER",
    "GET_PRODUCT_CAPABILITIES",
    # Data classes
    "Evidence",
    "DocumentNode",
    "CapabilityNode",
    "ProductNode",
    "RiskTopicNode",
    "EventNode",
]
