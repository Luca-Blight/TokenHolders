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
    total_supply = int(os.environ.get("TOTAL_SUPPLY"))

    indexing_strategy = "continuously" if not indexing_strategy else indexing_strategy
    contract_address = (
        "0xBAac2B4491727D78D2b78815144570b9f2Fe8899"
        if not contract_address
        else contract_address
    )

    log.info(f"indexing strategy: {indexing_strategy}")
    log.info(f"contract address: {contract_address}")

    if indexing_strategy == "continuously":
        token_indexer = TokenIndexer(
            contract_address=contract_address, total_supply=total_supply
        )
        token_indexer.index_continuously()

    elif indexing_strategy == "on_demand":

        from_block = int(os.environ.get("FROM_BLOCK"))
        to_block = int(os.environ.get("TO_BLOCK"))

        token_indexer = TokenIndexer(
            contract_address=contract_address, total_supply=total_supply
        )
        token_indexer.on_demand(from_block, to_block)

    else:
        log.info(
            "Invalid input. Please set the INDEXING_STRATEGY environment variable to 'continuously' or 'on_demand'."
        )
