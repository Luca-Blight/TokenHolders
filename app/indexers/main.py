import os
import json
import polars as pl
import logging
import requests
import time

from app.models.TokenHolder import TokenHolder
from app.database.main import engine
from datetime import datetime, timedelta
from sqlmodel import select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql import func
from contextlib import contextmanager
from web3 import Web3
from web3.exceptions import BlockNotFound

from dotenv import load_dotenv

load_dotenv()

ALCHEMY_URL = os.environ.get("ALCHEMY_URL")
web3: str = Web3(Web3.HTTPProvider(os.environ.get("ALCHEMY_URL")))

logging.basicConfig(
    level=logging.INFO,
    format="{asctime} {levelname} {message}",
    style="{",
    datefmt="%m-%d-%y %H:%M:%S",
)

log = logging.getLogger()

pid = os.getpid()
log.info(f"program running under process: {pid}")


@contextmanager
def get_session():
    session = sessionmaker(bind=engine, expire_on_commit=False)()

    try:
        yield session
    finally:
        session.close()


def get_transfer_events(
    from_block: int,
    to_block: str = None,
    contract_address: str = "0xBAac2B4491727D78D2b78815144570b9f2Fe8899",
) -> requests.Response:

    hex_from_block = Web3.to_hex(from_block)

    if to_block:

        hex_to_block = Web3.to_hex(to_block)

        log.info(
            f"get_transfer_events starting from block: {from_block} to block: {to_block}"
        )

        transfers = requests.post(
            url=ALCHEMY_URL,
            json={
                "jsonrpc": "2.0",
                "id": 0,
                "method": "alchemy_getAssetTransfers",
                "params": [
                    {
                        "fromBlock": f"{hex_from_block}",
                        "toBlock": f"{hex_to_block}",
                        "toBlock": "latest",
                        "contractAddresses": [contract_address],
                        "excludeZeroValue": False,
                        "withMetadata": "true",
                        "category": [
                            "erc20",
                        ],
                    }
                ],
            },
        )

        return transfers

    else:
        log.info(f"get_transfer_events starting from block: {from_block}")

        transfers = requests.post(
            url=ALCHEMY_URL,
            json={
                "jsonrpc": "2.0",
                "id": 0,
                "method": "alchemy_getAssetTransfers",
                "params": [
                    {
                        "fromBlock": f"{hex_from_block}",
                        "toBlock": "latest",
                        "contractAddresses": [contract_address],
                        "excludeZeroValue": False,
                        "withMetadata": True,
                        "category": [
                            "erc20",
                        ],
                    }
                ],
            },
        )
    return transfers


def process_transfer_events(transfers) -> tuple[pl.DataFrame, int]:

    records = []

    # texas_timezone = pytz.timezone("US/Central")
    # created_at = pd.Timestamp(datetime.now(tz=texas_timezone))
    if transfers.status_code == 400:
        log.error("stream error, status code 400")
    else:
        result = json.loads(transfers.text)
        if result and result.get("result", None):
            if result["result"].get("transfers", None):
                result: list[dict] = result["result"]["transfers"]
                for data in result:
                    block_number: int = Web3.to_int(hexstr=str(data["blockNum"]))
                    # block_date: datetime = get_block_date(block_number)
                    block_timestamp = data["metadata"]["blockTimestamp"]
                    date_format = "%Y-%m-%dT%H:%M:%S.%fZ"
                    block_date = datetime.strptime(block_timestamp, date_format)
                    from_address: str = data["from"]
                    transaction_hash: str = data["hash"]
                    transaction = web3.eth.get_transaction(transaction_hash)
                    transaction_idx = transaction["transactionIndex"]
                    to_address: str = data["to"]
                    value: float = round(
                        float(data["value"] if data["value"] else 0), 8
                    )

                    records.append(
                        {
                            "block_number": block_number,
                            "from_address": from_address,
                            "to_address": to_address,
                            "value": value,
                            "transaction_hash": transaction_hash,
                            "block_date": block_date,
                            "transaction_idx": transaction_idx,
                            "created_at": datetime.now(),
                        }
                    )

        df = pl.DataFrame(records)
        last_block = df["block_number"].max()
        return df, last_block


def load_transfer_events(balances: pl.DataFrame):
    
    # order is extremely important here, otherwise total balances will be incorrect, hence the sort and synchronous processing
    balances.sort(["block_number", "transaction_idx"], descending=False)


    records = balances.to_dicts()
    log.info(f"Processing {len(records)} records")
    for idx, record in enumerate(records):

        log.info(f"Processing record: {idx}")

        from_address = record["from_address"]
        to_address = record["to_address"]
        value = record["value"]
        block_date = record["block_date"]
        block_number = record["block_number"]
        transaction_hash = record["transaction_hash"]
        transaction_idx = record["transaction_idx"]

        created_at = record["created_at"]

        # Skip zero value transactions, we only care about transfers that have a value
        if value == 0:
            continue

        with get_session() as session:

            if from_address == "0x0000000000000000000000000000000000000000":
                # Process initial owner

                initial_owner = (
                    session.query(TokenHolder)
                    .filter(TokenHolder.address == to_address)
                    .one_or_none()
                )

                if initial_owner is None:
                    log.info(f"Initial Supply: {value} DOGE")
                    total_supply = session.query(func.sum(TokenHolder.balance)).scalar()
                    total_supply_percentage = 100

                    initial_owner = TokenHolder(
                        address=to_address,
                        transaction_hash=transaction_hash,
                        block_number=block_number,
                        transaction_index=transaction_idx,
                        balance=value,
                        block_date=block_date,
                        total_supply_percentage=total_supply_percentage,
                        last_updated=created_at,
                    )
                    session.add(initial_owner)

                    session.commit()
                else:
                    continue
            else:
                # Make necessary calculations and commit for the sender
                sender_stmt = (
                    select(TokenHolder)
                    .where(TokenHolder.address == from_address)
                    .order_by(TokenHolder.id.desc())
                    .limit(1)
                )
                sender = session.execute(sender_stmt).one_or_none()

                if sender is not None:

                    sender = sender[0]

                    one_week_ago = datetime.utcnow() - timedelta(weeks=1)
                    previous_balance = (
                        session.query(func.sum(TokenHolder.balance))
                        .filter(
                            TokenHolder.address == from_address,
                            TokenHolder.block_date < one_week_ago,
                        )
                        .scalar()
                    )

                    # Sender's new balance
                    new_sender_balance = round(sender.balance - value, 2)

                    if new_sender_balance < 0 and new_sender_balance >= -0.03:
                        new_sender_balance = 0

                    # Create a new record for the sender with the updated balance
                    total_supply = 16969696969
                    sender_total_supply_percentage = round(
                        (new_sender_balance / total_supply) * 100, 2
                    )
                    # already checked for negative value above

                    if previous_balance == 0:
                        weekly_balance_change = 100 if value > 0 else 0

                    else:
                        weekly_balance_change = round(
                            ((new_sender_balance - previous_balance) / previous_balance)
                            * 100
                        )

                    sender = TokenHolder(
                        address=from_address,
                        block_number=block_number,
                        transaction_hash=transaction_hash,
                        transaction_index=transaction_idx,
                        total_supply_percentage=sender_total_supply_percentage,
                        weekly_balance_change=weekly_balance_change,
                        balance=new_sender_balance,
                        block_date=block_date,
                        last_updated=created_at,
                    )
                    session.add(sender)

                    # Make necessary calculations and commit for the recipient
                    recipient = (
                        select(TokenHolder)
                        .where(TokenHolder.address == to_address)
                        .order_by(TokenHolder.id.desc())
                        .limit(1)
                    )
                    recipient = session.execute(recipient).one_or_none()

                    # calculate total supply percentage for recipient

                    if recipient is None:

                        total_supply = 16969696969
                        recipient_total_supply_percentage = round(
                            (value / total_supply) * 100, 2
                        )  # since this is the first time the recipient is receiving tokens, their total supply percentage is just the value of the transaction

                        # Create a new record for the recipient with the updated balance
                        recipient = TokenHolder(
                            address=to_address,
                            transaction_hash=transaction_hash,
                            block_number=block_number,
                            transaction_index=transaction_idx,
                            total_supply_percentage=recipient_total_supply_percentage,
                            balance=value,
                            block_date=block_date,
                            last_updated=created_at,
                        )
                        session.add(recipient)

                    else:

                        # Update the existing record for the recipient with the updated balance, total supply percentage, and weekly balance change.
                        recipient = recipient[0]
                        new_recipient_balance = round(recipient.balance + value, 2)
                        if new_recipient_balance < 0 and new_recipient_balance >= -0.03:
                            new_sender_balance = 0

                        total_supply = 16969696969
                        recipient_total_supply_percentage = round(
                            (new_recipient_balance / total_supply) * 100, 2
                        )

                        # calculate weekly balance change for recipient
                        one_week_ago = datetime.utcnow() - timedelta(weeks=1)
                        previous_balance = (
                            session.query(func.sum(TokenHolder.balance))
                            .filter(
                                TokenHolder.address == to_address,
                                TokenHolder.block_date < one_week_ago,
                            )
                            .scalar()
                        )

                        if previous_balance == 0:
                            weekly_balance_change = 100 if value > 0 else 0

                        else:
                            weekly_balance_change = round(
                                (
                                    (new_recipient_balance - previous_balance)
                                    / previous_balance
                                )
                                * 100,
                                2,
                            )

                        new_recipient = TokenHolder(
                            address=to_address,
                            transaction_hash=transaction_hash,
                            block_number=block_number,
                            transaction_index=transaction_idx,
                            total_supply_percentage=recipient_total_supply_percentage,
                            weekly_balance_change=weekly_balance_change,
                            balance=new_recipient_balance,
                            block_date=block_date,
                            last_updated=created_at,
                        )
                        session.add(new_recipient)

                    session.commit()


def index_continuously():

    last_block = 0

    while True:
        try:
            start = time.time()
            transfers = get_transfer_events(from_block=last_block)
            balances, last_block = process_transfer_events(transfers)

            load_transfer_events(balances)

            if balances.is_empty() is False:
                log.info("Successfully indexed transfer events")
                last_block = last_block
                end = time.time()
                log.info(f"Time taken: {end - start} seconds")

        except BlockNotFound:
            time.sleep(15)


def on_demand(from_block: int, to_block: int):

    try:
        start = time.time()
        transfers = get_transfer_events(from_block=from_block, to_block=to_block)
        balances, last_block = process_transfer_events(transfers)

        load_transfer_events(balances)

        if balances.is_empty() is False:
            log.info("Successfully indexed transfer events")
            end = time.time()
        log.info(f"Time taken: {end - start} seconds")
    except BlockNotFound:
        time.sleep(15)


if __name__ == "__main__":
    index_continuously()

    indexing_strategy = os.environ.get(
        "INDEXING_STRATEGY",
        input("Enter the indexing strategy (continuously/on_demand): "),
    )

    if indexing_strategy == "continuously":
        index_continuously()
    elif indexing_strategy == "on_demand":
        from_block = int(input("Enter the start block number: "))
        to_block = int(input("Enter the end block number: "))
        on_demand(from_block, to_block)
        print("Not implemented yet.")
    else:
        print("Invalid input. Please enter 'continuously' or 'on_demand'.")
