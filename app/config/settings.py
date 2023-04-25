import os

# Database configuration
PG_HOST = os.environ.get("PG_HOST")
PG_PORT = os.environ.get("PG_PORT")
PG_NAME = os.environ.get("PG_NAME")
PG_USER = os.environ.get("PG_USER")
PG_PASSWORD = os.environ.get("PG_PASSWORD")
POOL_MIN_SIZE = 5
POOL_MAX_SIZE = 10

# Indexer configuration
INDEXING_STRATEGY = os.environ.get("INDEXING_STRATEGY")
CONTRACT_ADDRESS = os.environ.get("CONTRACT_ADDRESS")

# Other settings
LOG_LEVEL = "DEBUG"
