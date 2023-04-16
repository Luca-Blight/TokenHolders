from sqlmodel import Field, SQLModel
from datetime import datetime


class TokenHolder(SQLModel, table=True):
    __tablename__ = "token_holders"

    address: str = Field(primary_key=True, index=True)
    balance: float = Field(index=True, default=0)
    total_supply: float = Field(default=0)
    total_supply_percentage: float = Field(default=0)
    weekly_balance_change: float = Field(default=0)
    last_updated: datetime = Field(default=datetime.utcnow)
    
    
#index for last_updated?


# token holder's weekly balance change
# % of total supply their balance represents

# rollup_table for precalculations, connect by address
# change from last record to current record