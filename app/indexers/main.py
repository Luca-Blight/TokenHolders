import httpx
import time
import logging

from sqlalchemy.orm import sessionmaker
from datetime import datetime
from app.models.TokenHolder import TokenHolder
from database.main import engine
from sqlmodel import select
from web3 import Web3
from web3.exceptions import BlockNotFound
from contextlib import contextmanager
from datetime import timedelta
from sqlalchemy.sql import func

import requests
import os
import json
import polars as pl
from dotenv import load_dotenv

load_dotenv()


ALCHEMY_URL = os.environ.get('ALCHEMY_URL')

logging.basicConfig(
    level=logging.INFO,
    format="{asctime} {levelname} {message}",
    style="{",
    datefmt="%m-%d-%y %H:%M:%S",
)

log = logging.getLogger()


@contextmanager
def get_session():
    session = sessionmaker(bind=engine, expire_on_commit=False)()

    try:
        yield session
    finally:
        session.close()


def get_transfer_events(from_block: int, to_block: str = None, contract_address: str = '0xBAac2B4491727D78D2b78815144570b9f2Fe8899'):
    
    hex_from_block = Web3.to_hex(from_block)
    
    if to_block:
        
        hex_to_block = Web3.to_hex(to_block)
        
        transfers = requests.post(
                    url=ALCHEMY_URL,
                    json={
                        "jsonrpc": "2.0",
                        "id": 0,
                        "method": "alchemy_getAssetTransfers",
                        "params": [
                            {
                                "fromBlock": f'{hex_from_block}',
                                "toBlock": f'{hex_to_block}',
                                "toBlock": "latest",
                                'contractAddresses': [contract_address],
                                "excludeZeroValue": False,
                                
                                "category": [
                                    "erc20",
                                ],
                            }
                        ],
                    },
                )
            
        return transfers

    else:
        transfers = requests.post(
                url=ALCHEMY_URL,
                json={
                    "jsonrpc": "2.0",
                    "id": 0,
                    "method": "alchemy_getAssetTransfers",
                    "params": [
                        {
                            "fromBlock": f'{hex_from_block}',
                            "toBlock": "latest",
                            'contractAddresses': [contract_address],
                            "excludeZeroValue": False,
                            
                            "category": [
                                "erc20",
                            ],
                        }
                    ],
                },
            )

    return transfers



def process_transfer_events(transfers):
    
    
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
                    from_address: str = data["from"]
                    to_address: str = data["to"]
                    value: int = data['value']                    
                    records.append({"block_number": block_number, "from_address": from_address, "to_address": to_address, "value": value})

        df = pl.DataFrame(records)
        last_block = df["block_number"].max()
        return df, last_block

def load_transfer_events(balances):
    
    
    records = balances.to_dicts()
    
    # order is extremely important here, otherwise total balances will be incorrect

    for record in records:

        from_address = record['from_address']
        to_address = record['to_address']
        value = record['value']
        
        
        with get_session() as session:
            # Retrieve the protocol id from the database and add it to the financial object
            sender = select(TokenHolder).where(TokenHolder.address == from_address)
            sender = session.execute(sender).one_or_none()
                            
            sender.balance -= value
            sender.last_updated = datetime.now()
            
            # Retrieve the protocol id from the database and add it to the financial object
            recipient = select(TokenHolder).where(TokenHolder.address == to_address)
            recipient = session.execute(recipient).one_or_none()
            
            if recipient is None:
                recipient = TokenHolder(address=to_address, balances=value, last_updated=datetime.now())
                recipient = recipient.execute(sender).one_or_none()
                session.add(recipient)
                
            else:
                sender.address = to_address
                sender.balance += value
                sender.last_updated = datetime.now()
                
                
            total_supply = session.query(func.sum(TokenHolder.balance)).scalar()
            total_supply_percentage = (value / total_supply) * 100

            # Update total supply and total supply percentage for the recipient
            recipient.total_supply = total_supply
            recipient.total_supply_percentage = total_supply_percentage

            # Calculate the weekly balance change
            one_week_ago = datetime.utcnow() - timedelta(weeks=1)
            previous_balance = (
                session.query(func.sum(TokenHolder.balance))
                .filter(TokenHolder.address == to_address, TokenHolder.last_updated < one_week_ago)
                .scalar()
            )

            if previous_balance is not None:
                weekly_balance_change = ((recipient.balance - previous_balance) / previous_balance) * 100
                recipient.weekly_balance_change = weekly_balance_change

                
            session.commit()
            
            



def index_continuously():
    
    last_block = 0

    while True:
        try:
            transfers = get_transfer_events(from_block=last_block)
            balances, last_block = process_transfer_events(transfers)
            
            load_transfer_events(balances)
            
            if balances:
                last_block = last_block
                
        except BlockNotFound:
            time.sleep(15)


        

if __name__ == "__main__":
    # index_continuously()

    indexing_strategy = os.environ.get("INDEXING_STRATEGY", input("Enter the indexing strategy (continuously/on_demand): "))
    
    if indexing_strategy == "continuously":
        index_continuously()
    elif indexing_strategy == "on_demand":
        print("Not implemented yet.")
    else:
        print("Invalid input. Please enter 'continuously' or 'on_demand'.")
