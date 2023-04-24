import os
import polars as pl

from app.models.TokenHolder import TokenHolder
from app.database.main import engine
from sqlmodel import select
from sqlalchemy.orm import sessionmaker
from web3 import Web3

from app.indexers.main import (
    get_transfer_events,
    process_transfer_events,
    load_transfer_events,
)

ALCHEMY_URL = os.environ.get("ALCHEMY_URL")
web3: str = Web3(Web3.HTTPProvider(os.environ.get("ALCHEMY_URL")))


def test_get_transfer_events():
    from_block = 10000000
    to_block = 10000010
    transfers = get_transfer_events(from_block, to_block)
    assert transfers.status_code == 200


def test_process_transfer_events():
    from_block = 10000000
    to_block = 10000010
    transfers = get_transfer_events(from_block, to_block)
    balances, last_block = process_transfer_events(transfers)

    assert isinstance(balances, pl.DataFrame)
    assert last_block >= from_block


def test_load_transfer_events():
    from_block = 10000000
    to_block = 10000010
    transfers = get_transfer_events(from_block, to_block)
    balances, last_block = process_transfer_events(transfers)

    # Create a temporary session for testing
    session = sessionmaker(bind=engine, expire_on_commit=False)()

    # Store the number of records in the TokenHolder table before loading
    num_records_before = session.query(TokenHolder).count()

    # Load the transfer events
    load_transfer_events(balances)

    # Store the number of records in the TokenHolder table after loading
    num_records_after = session.query(TokenHolder).count()

    assert num_records_after >= num_records_before
