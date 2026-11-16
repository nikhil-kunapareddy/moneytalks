"""Database read/write helpers for Transaction records."""

from datetime import date

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.models.transaction import Transaction


def insert_transactions(
    session: Session, transactions: list[Transaction]
) -> tuple[int, int]:
    """Insert transactions, skipping ones already stored. Returns (inserted, skipped)."""
    inserted = skipped = 0
    for txn in transactions:
        # A savepoint per row: a duplicate only rolls back itself, not the
        # rows inserted before it in the same session.
        try:
            with session.begin_nested():
                session.add(txn)
            inserted += 1
        except IntegrityError:
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


def get_date_bounds(session: Session) -> tuple[date | None, date | None]:
    """Return the first and last transaction dates stored (any type)."""
    return session.query(func.min(Transaction.date), func.max(Transaction.date)).one()
