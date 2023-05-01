import os
import polars as pl
import logging
import requests
import json
import time
import re
import traceback

from app.models.TokenHolder import TokenHolder
from app.database.main import engine, PG_URL
from datetime import datetime, timedelta
from sqlmodel import select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql import func
from contextlib import contextmanager
from web3 import Web3
from web3.exceptions import BlockNotFound
from typing import List, Dict
from dotenv import load_dotenv


load_dotenv()

ALCHEMY_URL = os.environ.get("ALCHEMY_URL")
web3 = Web3(Web3.HTTPProvider(ALCHEMY_URL))


logging.basicConfig(
    level=logging.INFO,
    format="{asctime} {levelname} {message}",
    style="{",
    datefmt="%m-%d-%y %H:%M:%S",
)

log = logging.getLogger()

# Set up the logger for sqlalchemy.engine
logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO)

log.info(f"pg url: {PG_URL}")
log.info(f"engine: {engine}")


@contextmanager
def get_session():
    session = sessionmaker(bind=engine, expire_on_commit=False)()

    try:
        yield session
    finally:
        session.close()


def is_hex(s):
    return re.match(r"^0x[0-9a-fA-F]{40}$", s) is not None


class TokenIndexer:
    def __init__(self, contract_address: str, total_supply: int):

        if not is_hex(contract_address):
            raise ValueError("Invalid contract address")
        self.contract_address = contract_address
        self.total_supply = total_supply

    def get_transfer_events(
        self, from_block: int, to_block: str = None, contract_address: str = None
    ) -> requests.Response:

        """Get transfer events from Alchemy API, and returns the response"""

        if contract_address is None:
            contract_address = self.contract_address
        # The rest of the get_transfer_events method
        hex_from_block = Web3.to_hex(from_block)

        if to_block:

            hex_to_block = Web3.to_hex(to_block)

            log.info(
                f"get_transfer_events starting from block: {from_block} to block: {to_block}"
            )

        hex_from_block = Web3.to_hex(from_block)
        payload = {
            "jsonrpc": "2.0",
            "id": 0,
            "method": "alchemy_getAssetTransfers",
            "params": [
                {
                    "fromBlock": f"{hex_from_block}",
                    "contractAddresses": [contract_address],
                    "excludeZeroValue": False,
                    "withMetadata": True,
                    "category": ["erc20"],
                }
            ],
        }

        if to_block:
            hex_to_block = Web3.to_hex(to_block)
            payload["params"][0]["toBlock"] = f"{hex_to_block}"
            log.info(
                f"get_transfer_events starting from block: {from_block} to block: {to_block}"
            )
        else:
            payload["params"][0]["toBlock"] = "latest"
            log.info(f"get_transfer_events starting from block: {from_block}")

        transfers = requests.post(url=ALCHEMY_URL, json=payload)
        return transfers

    def process_transfer_events(self, transfers) -> tuple[pl.DataFrame, int]:

        """Process transfer events into a dataframe, and return the dataframe and the last block number processed"""

        records = []

        if transfers.status_code == 400:
            log.error("stream error, status code 400")
        else:
            result = json.loads(transfers.text)
            if result and result.get("result", None):
                if result["result"].get("transfers", None):
                    result: list[dict] = result["result"]["transfers"]
                    for data in result:
                        block_number: int = Web3.to_int(hexstr=str(data["blockNum"]))
                        block_timestamp = data["metadata"]["blockTimestamp"]
                        date_format = "%Y-%m-%dT%H:%M:%S.%fZ"
                        block_date = datetime.strptime(block_timestamp, date_format)
                        from_address: str = data["from"]
                        transaction_hash: str = data["hash"]
                        transaction = web3.eth.get_transaction(transaction_hash)
                        transaction_idx = transaction["transactionIndex"]
                        to_address: str = data["to"]
                        token: str = data["asset"]
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
                                "token": token,
                                "created_at": datetime.now(),
                            }
                        )

            df = pl.DataFrame(records)
            last_block = df["block_number"].max()
            return df, last_block

    def _calculate_total_supply_percentage(
        self, balance: int, total_supply: int
    ) -> float:
          
        return round((balance / total_supply) * 100, 2)

    def _calculate_weekly_balance_change(
        self, new_balance: int, previous_balance: int
    ) -> float:
        if previous_balance == 0 or previous_balance is None:
            return 100 if new_balance > 0 else 0
        return round(((new_balance - previous_balance) / previous_balance) * 100, 2)

    def _create_token_holder(
        self,
        record,
        total_supply_percentage,
        weekly_balance_change,
        balance,
        holder: str,
    ) -> TokenHolder:

        """Create a new token holder record"""

        log.info(f"Creating new token holder record: {record['from_address']}")

        holder = record["from_address"] if holder == "sender" else record["to_address"]

        return TokenHolder(
            address=holder,
            transaction_hash=record["transaction_hash"],
            block_number=record["block_number"],
            transaction_index=record["transaction_idx"],
            total_supply_percentage=total_supply_percentage,
            weekly_balance_change=weekly_balance_change,
            balance=balance,
            block_date=record["block_date"],
            token=record["token"],
            last_updated=record["created_at"],
        )

    def _update_sender_balance(self, session, record: dict, total_supply: int):

        """Update the sender's balance in the database"""

        log.info(f"Updating sender balance: {record['from_address']}")
        sender_stmt = (
            select(TokenHolder)
            .where(TokenHolder.address == record["from_address"])
            .order_by(TokenHolder.id.desc())
            .limit(1)
        )
        sender = session.execute(sender_stmt).one_or_none()

        if sender is not None:

            sender = sender[0]

            one_week_ago = record["block_date"] - timedelta(weeks=1)
            previous_balance = (
                session.query(func.sum(TokenHolder.balance))
                .filter(
                    TokenHolder.address == record["from_address"],
                    TokenHolder.block_date < one_week_ago,
                )
                .scalar()
            )

            # Sender's new balance
            new_sender_balance = round(sender.balance - record["value"], 2)

            if new_sender_balance < 0 and new_sender_balance >= -0.03:
                new_sender_balance = 0

            # Create a new record for the sender with the updated balance

            sender_total_supply_percentage = self._calculate_total_supply_percentage(
                new_sender_balance, total_supply
            )
            weekly_balance_change = self._calculate_weekly_balance_change(
                new_sender_balance, previous_balance
            )

            new_sender = self._create_token_holder(
                record,
                sender_total_supply_percentage,
                weekly_balance_change,
                new_sender_balance,
                "sender",
            )
            return new_sender
        else:

            log.info(
                f"Sender does not exist in the database. Address: {record['from_address']}"
            )
            raise ValueError

    def _update_recipient_balance(self, session, record: dict, total_supply: int):

        log.info(f"Updating recipient balance: {record['to_address']}")

        recipient = (
            select(TokenHolder)
            .where(TokenHolder.address == record["to_address"])
            .order_by(TokenHolder.id.desc())
            .limit(1)
        )
        recipient = session.execute(recipient).one_or_none()

        if recipient is None:

            recipient_total_supply_percentage = round(
                (record["value"] / total_supply) * 100, 2
            )

            recipient = self._create_token_holder(
                record,
                balance=record["value"],
                total_supply_percentage=recipient_total_supply_percentage,
                holder="recipient",
                weekly_balance_change=100,
            )

            return recipient

        else:

            recipient = recipient[0]
            new_recipient_balance = round(recipient.balance + record["value"], 2)
            if new_recipient_balance < 0 and new_recipient_balance >= -0.03:
                new_recipient_balance = 0

            # calculate weekly balance change for recipient
            one_week_ago = record["block_date"] - timedelta(weeks=1)
            previous_balance = (
                session.query(func.sum(TokenHolder.balance))
                .filter(
                    TokenHolder.address == record["to_address"],
                    TokenHolder.block_date < one_week_ago,
                )
                .scalar()
            )

            recipient_total_supply_percentage = self._calculate_total_supply_percentage(
                new_recipient_balance, total_supply
            )
            weekly_balance_change = self._calculate_weekly_balance_change(
                new_recipient_balance, previous_balance
            )

            new_recipient = self._create_token_holder(
                record,
                recipient_total_supply_percentage,
                weekly_balance_change,
                new_recipient_balance,
                "recipient",
            )
            return new_recipient

    def update_balances(self, records: List[Dict], total_supply: int) -> None:

        """Update token holder balances in the database."""

        log.info("Updating token holder balances in the database")
        for record in records:
            from_address = record["from_address"]
            to_address = record["to_address"]
            value = record["value"]

            # Skip zero value transactions, we only care about transfers that have a value
            if value == 0:
                continue

            with get_session() as session:
                if from_address == "0x0000000000000000000000000000000000000000":
                    try:
                        initial_owner = (
                            session.query(TokenHolder)
                            .filter(TokenHolder.address == to_address)
                            .one_or_none()
                        )
                        if initial_owner is None:
                            log.info(
                                f"Initial Supply: {value} Token: {record['token']}"
                            )
                            initial_owner = self._create_token_holder(
                                record,
                                total_supply_percentage=100,
                                weekly_balance_change=0,
                                balance=value,
                                holder="recipient",
                            )

                            session.add(initial_owner)
                            session.commit()
                    except Exception as e:
                        log.error(f"An error occurred: {e}")
                        log.error(
                            traceback.format_exc()
                        )  # Include stack trace in the log message
                        log.warning("Rolling back the transaction")
                        session.rollback()
                        log.warning("Transaction rolled back")
                else:
                    try:

                        sender = self._update_sender_balance(
                            session, record, total_supply
                        )

                        session.add(sender)
                        recipient = self._update_recipient_balance(
                            session, record, total_supply
                        )
                        session.add(recipient)
                        log.info(
                            f"Committing the transaction for both sender: {record['from_address']} and recipient: {record['to_address']}"
                        )

                        session.commit()
                    except Exception as e:
                        log.error(f"An error occurred: {e}")
                        log.error(
                            traceback.format_exc()
                        )  # Include stack trace in the log message
                        log.warning("Rolling back the transaction")
                        session.rollback()
                        log.warning("Transaction rolled back")

    def load_transfer_events(self, balances: pl.DataFrame):

        """Load transfer events into the database, and update token holder balances.
        Sender balances are reduced, receiver balances are increased in one transaction."""

        balances.sort(["block_number", "transaction_idx"], descending=False)
        records = balances.to_dicts()
        # with get_session() as session:
        #     initial_owner = (
        #         session.query(TokenHolder)
        #         .filter(TokenHolder.total_supply_percentage == 100)
        #         .one_or_none()
        #     )

        total_supply = self.total_supply

        self.update_balances(records, total_supply)

    def index_continuously(self):

        """Index transfer events continuously(every 15 seconds),
        starting from the latest block number in the TokenHolder table or from block 0 if the table is empty."""

        # Get the latest block number from the TokenHolder table
        with get_session() as session:
            latest_block = session.query(func.max(TokenHolder.block_number)).scalar()

        # If there's no record in the TokenHolder table, set the last_block to 0
        last_block = latest_block if latest_block is not None else 0

        while True:
            try:
                start = time.time()
                transfers = self.get_transfer_events(from_block=last_block)
                balances, last_block = self.process_transfer_events(transfers)
                self.load_transfer_events(balances)

                if balances.is_empty() is False:
                    log.info("Successfully indexed transfer events")
                    last_block = last_block
                    end = time.time()
                    log.info(f"Time taken: {end - start} seconds")

            except BlockNotFound:
                time.sleep(15)

    def on_demand(self, from_block: int, to_block: int):

        """on demand indexing of transfer events, from a given block to a given block"""

        try:
            start = time.time()
            transfers = self.get_transfer_events(
                from_block=from_block, to_block=to_block
            )
            results = self.process_transfer_events(transfers)

            balances = results[0]

            self.load_transfer_events(balances)

            if balances.is_empty() is False:
                log.info("Successfully indexed transfer events")
                end = time.time()
            log.info(f"Time taken: {end - start} seconds")
        except BlockNotFound:
            time.sleep(15)
