"""Pandas-based aggregations used by the CLI summary and visualisation commands."""

import pandas as pd

from src.models.transaction import Transaction


def to_dataframe(transactions: list[Transaction]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "date": t.date,
                "merchant": t.merchant,
                "description": t.description,
                "amount": float(t.amount),
                "category": t.category,
                "transaction_type": t.transaction_type,
            }
            for t in transactions
        ]
    )


def spending_by_category(df: pd.DataFrame) -> pd.Series:
    return df.groupby("category")["amount"].sum().sort_values(ascending=False)


def monthly_spending(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["month"] = pd.to_datetime(df["date"]).dt.to_period("M")
    return df.groupby("month")["amount"].sum().reset_index()


def top_merchants(df: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    return (
        df.groupby("merchant")["amount"]
        .sum()
        .sort_values(ascending=False)
        .head(n)
        .reset_index()
    )


def daily_spending(df: pd.DataFrame) -> pd.DataFrame:
    return df.groupby("date")["amount"].sum().reset_index()
