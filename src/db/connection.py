"""Database engine, session factory, and schema initialisation."""

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker

from config import DATABASE_URL
from src.models.transaction import Base

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)


def init_db() -> None:
    Base.metadata.create_all(engine)
    _migrate_multi_account()


def _migrate_multi_account() -> None:
    """Upgrade tables created before multi-bank support. Safe to run repeatedly.

    Adds ``account`` (existing rows came from the Amex-only parser, so they are
    labelled "Amex") and ``seq``, and widens the uniqueness rule to match the model.
    """
    columns = {c["name"] for c in inspect(engine).get_columns("transactions")}
    if {"account", "seq"} <= columns:
        return
    with engine.begin() as conn:
        if "account" not in columns:
            conn.execute(text("ALTER TABLE transactions ADD COLUMN account VARCHAR"))
            conn.execute(text("UPDATE transactions SET account = 'Amex' WHERE account IS NULL"))
            conn.execute(text("ALTER TABLE transactions ALTER COLUMN account SET NOT NULL"))
        if "seq" not in columns:
            conn.execute(text("ALTER TABLE transactions ADD COLUMN seq INTEGER NOT NULL DEFAULT 0"))
        conn.execute(text("ALTER TABLE transactions DROP CONSTRAINT IF EXISTS uq_transaction"))
        conn.execute(text(
            "ALTER TABLE transactions ADD CONSTRAINT uq_transaction "
            "UNIQUE (account, date, description, amount, transaction_type, seq)"
        ))


def get_session() -> Session:
    return SessionLocal()
