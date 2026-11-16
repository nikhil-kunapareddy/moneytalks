"""SQLAlchemy ORM model for a single credit card transaction."""

from datetime import datetime

from sqlalchemy import Column, Date, DateTime, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class Transaction(Base):
    __tablename__ = "transactions"
    # Re-importing a statement must not duplicate rows, but genuinely identical
    # rows (two $2.40 fares on one day, a $1 charge and its $1 refund) must be
    # kept. ``seq`` numbers identical rows within one statement to tell them apart.
    __table_args__ = (
        UniqueConstraint(
            "account", "date", "description", "amount", "transaction_type", "seq",
            name="uq_transaction",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    account = Column(String, nullable=False)  # e.g. "Chase ••1234"
    seq = Column(Integer, nullable=False, default=0, server_default="0")
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
