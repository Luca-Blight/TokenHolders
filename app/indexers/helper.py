import os
from datetime import datetime

from web3 import Web3

web3: str = Web3(Web3.HTTPProvider(os.environ.get("ALCHEMY_URL")))


def get_block_date(block_number: int) -> datetime:

    int_timestamp: int = web3.eth.get_block(block_number)["timestamp"]
    block_date = datetime.utcfromtimestamp(int_timestamp)

    return block_date
