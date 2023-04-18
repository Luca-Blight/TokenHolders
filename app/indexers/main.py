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
from helper import get_block_date
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
                        "metadata": "true",
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
                        "metadata": "true",
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
                    block_date: datetime = get_block_date(block_number)
                    from_address: str = data["from"]
                    transaction_hash: str = data["hash"]
                    transaction = web3.eth.get_transaction(transaction_hash)
                    transaction_idx = transaction["transactionIndex"]
                    to_address: str = data["to"]
                    value: int = round(data["value"] if data["value"] else 0, 2)
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


def load_transfer_events(balances):

    balances.sort(["block_number", "transaction_idx"], descending=False)
    balances.write_csv(
        "/Users/Zachary_Royals/Documents/Code/Data-Engineer-Coding-Challenge/notebooks/doge_transfer.csv"
    )
    records = balances.to_dicts()
    # order is extremely important here, otherwise total balances will be incorrect
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

        if value == 0:
            continue

        with get_session() as session:

            # existing_record = session.query(TokenHolder).filter(TokenHolder.transaction_hash == transaction_hash).one_or_none()

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
                try:
                    # Retrieve the protocol id from the database and add it to the financial object
                    sender_stmt = (
                        select(TokenHolder)
                        .where(TokenHolder.address == from_address)
                        .order_by(TokenHolder.id.desc())
                        .limit(1)
                    )
                    sender = session.execute(sender_stmt).one_or_none()
                    if sender is not None:

                        sender = sender[0]

                        # Sender's new balance
                        new_sender_balance = sender.balance - value

                        if new_sender_balance < 0:
                            log.info(
                                f"Sender balance is negative: {new_sender_balance}"
                            )
                            continue

                        # Create a new record for the sender with the updated balance
                        new_sender = TokenHolder(
                            address=from_address,
                            block_number=block_number,
                            transaction_hash=transaction_hash,
                            transaction_index=transaction_idx,
                            balance=new_sender_balance,
                            block_date=block_date,
                            last_updated=created_at,
                        )
                        session.add(new_sender)

                    else:
                        log.info("Sender not found")

                    # Retrieve the protocol id from the database and add it to the financial object
                    recipient = (
                        select(TokenHolder)
                        .where(TokenHolder.address == to_address)
                        .order_by(TokenHolder.id.desc())
                        .limit(1)
                    )
                    recipient = session.execute(recipient).one_or_none()

                    if recipient is None:
                        recipient = TokenHolder(
                            address=to_address,
                            transaction_hash=transaction_hash,
                            block_number=block_number,
                            transaction_index=transaction_idx,
                            balance=value,
                            block_date=block_date,
                            last_updated=created_at,
                        )
                        session.add(recipient)

                    else:
                        recipient = recipient[0]

                        # Recipient's new balance
                        new_recipient_balance = recipient.balance + value

                        # Create a new record for the recipient with the updated balance
                        new_recipient = TokenHolder(
                            address=to_address,
                            transaction_hash=transaction_hash,
                            block_number=block_number,
                            transaction_index=transaction_idx,
                            balance=new_recipient_balance,
                            block_date=block_date,
                            last_updated=created_at,
                        )
                        session.add(new_recipient)

                    total_supply = 16969696969
                    total_supply_percentage = (value / total_supply) * 100

                    # Update total supply and total supply percentage for the recipient
                    recipient.total_supply_percentage = total_supply_percentage

                    # Calculate the weekly balance change
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
                        weekly_balance_change = 100 if recipient.balance > 0 else 0
                        recipient.weekly_balance_change = weekly_balance_change

                    else:
                        weekly_balance_change = (
                            (recipient.balance - previous_balance) / previous_balance
                        ) * 100
                        recipient.weekly_balance_change = weekly_balance_change

                    session.commit()
                except Exception as e:
                    log.error(e)


def index_continuously():

    last_block = 0

    while True:
        try:

            transfers = get_transfer_events(from_block=last_block)
            balances, last_block = process_transfer_events(transfers)

            load_transfer_events(balances)

            if balances.is_empty() is False:
                log.info("Successfully indexed transfer events")
                last_block = last_block

        except BlockNotFound:
            time.sleep(15)


if __name__ == "__main__":
    index_continuously()

    # indexing_strategy = os.environ.get("INDEXING_STRATEGY", input("Enter the indexing strategy (continuously/on_demand): "))

    # if indexing_strategy == "continuously":
    #     index_continuously()
    # elif indexing_strategy == "on_demand":
    #     print("Not implemented yet.")
    # else:
    #     print("Invalid input. Please enter 'continuously' or 'on_demand'.")
