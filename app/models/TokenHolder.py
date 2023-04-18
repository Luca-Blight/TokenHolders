from sqlmodel import Field, SQLModel
from datetime import datetime
from sqlalchemy.schema import CheckConstraint
from sqlalchemy import Column, Sequence, Integer, BigInteger


# what's the max integer size for the id?


class TokenHolder(SQLModel, table=True):

    __tablename__ = "token_holders"

    id: int = Field(primary_key=True)
    address: str
    balance: float = Field(index=True)
    total_supply: int = Field(default=16969696969, sa_column=Column(BigInteger()))
    total_supply_percentage: float = Field(default=0)
    weekly_balance_change: float = Field(default=0)
    block_number: int
    transaction_hash: str
    transaction_index: int
    block_date: datetime = Field(default=datetime.utcnow)
    last_updated: datetime = Field(default=datetime.utcnow)

    __table_args__ = (CheckConstraint("balance >= 0", name="balance_positive_check"),)


# index for last_updated?


# token holder's weekly balance change
# % of total supply their balance represents

# rollup_table for precalculations, connect by address
# change from last record to current record
