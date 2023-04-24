import os
import logging

from token_indexer import TokenIndexer


from dotenv import load_dotenv


load_dotenv()

CONTRACT_ADDRESS = os.environ.get("CONTRACT_ADDRESS")


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
    token_indexer = TokenIndexer(contract_address=CONTRACT_ADDRESS)

    indexing_strategy = os.environ.get(
        "INDEXING_STRATEGY",
        input("Enter the indexing strategy (continuously/on_demand): "),
    )

    if indexing_strategy == "continuously":
        token_indexer.index_continuously()
    elif indexing_strategy == "on_demand":
        from_block = int(input("Enter the start block number: "))
        to_block = int(input("Enter the end block number: "))
        token_indexer.on_demand(from_block, to_block)
    else:
        print("Invalid input. Please enter 'continuously' or 'on_demand'.")
