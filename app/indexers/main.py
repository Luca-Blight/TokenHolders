import os
import logging

from token_indexer import TokenIndexer
from dotenv import load_dotenv


load_dotenv()


logging.basicConfig(
    level=logging.INFO,
    format="{asctime} {levelname} {message}",
    style="{",
    datefmt="%m-%d-%y %H:%M:%S",
)

log = logging.getLogger()

pid = os.getpid()
log.info(f"program running under process: {pid}")


if __name__ == "__main__":

    indexing_strategy = os.environ.get("INDEXING_STRATEGY")
    contract_address = os.environ.get("CONTRACT_ADDRESS")

    if indexing_strategy == "continuously":
        token_indexer = TokenIndexer(contract_address=contract_address)
        token_indexer.index_continuously()

    elif indexing_strategy == "on_demand":

        from_block = int(os.environ.get("FROM_BLOCK"))
        to_block = int(os.environ.get("TO_BLOCK"))

        token_indexer = TokenIndexer(contract_address=contract_address)
        token_indexer.on_demand(from_block, to_block)

    else:
        log.info(
            "Invalid input. Please set the INDEXING_STRATEGY environment variable to 'continuously' or 'on_demand'."
        )
