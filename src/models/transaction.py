"""SQLAlchemy ORM model for a single credit card transaction."""

from datetime import datetime

from sqlalchemy import Column, Date, DateTime, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        UniqueConstraint("date", "description", "amount", name="uq_transaction"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False)
    description = Column(String, nullable=False)
    merchant = Column(String)
    amount = Column(Numeric(10, 2), nullable=False)
    category = Column(String)
    transaction_type = Column(String, nullable=False)  # charge / payment / credit
    statement_closing_date = Column(Date)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<Transaction {self.date} {self.merchant} ${self.amount}>"
