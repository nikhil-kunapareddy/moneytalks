"""Database read/write helpers for Transaction records."""

from datetime import date

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.models.transaction import Transaction


def insert_transactions(
    session: Session, transactions: list[Transaction]
) -> tuple[int, int]:
    inserted = skipped = 0
    for txn in transactions:
        try:
            session.add(txn)
            session.flush()
            inserted += 1
        except IntegrityError:
            session.rollback()
            skipped += 1
    session.commit()
    return inserted, skipped


def get_charges(
    session: Session,
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[Transaction]:
    query = session.query(Transaction).filter(
        Transaction.transaction_type == "charge"
    )
    if start_date:
        query = query.filter(Transaction.date >= start_date)
    if end_date:
        query = query.filter(Transaction.date < end_date)
    return query.order_by(Transaction.date).all()
