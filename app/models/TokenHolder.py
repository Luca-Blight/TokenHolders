from sqlmodel import Field, SQLModel
from datetime import datetime
from sqlalchemy.schema import CheckConstraint


class TokenHolder(SQLModel, table=True):

    __tablename__ = "token_holders"

    id: int = Field(primary_key=True)
    address: str
    balance: float = Field(index=True, default=0)
    total_supply_percentage: float
    weekly_balance_change: float = Field(default=0)
    block_number: int
    transaction_hash: str
    transaction_index: int
    token: str
    block_date: datetime = Field(default=datetime.utcnow)
    last_updated: datetime = Field(default=datetime.utcnow)

    __table_args__ = (
        CheckConstraint("balance >= 0", name="balance_positive_check"),
        CheckConstraint(
            "total_supply_percentage >= 0",
            name="total_supply_percentage_positive_check",
        ),
    )
