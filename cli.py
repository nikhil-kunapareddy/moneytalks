"""
MoneyTalks CLI

Usage:
  python cli.py import data/2026-03-10.pdf
  python cli.py visualize --month 2026-02
  python cli.py visualize --year 2026
  python cli.py summary --month 2026-02
  python cli.py categories
"""

from datetime import date, datetime

import click

from src.analysis.aggregator import to_dataframe
from src.analysis.categorizer import categorize, clean_merchant
from src.db.connection import get_session, init_db
from src.db.repository import get_charges, insert_transactions
from src.models.transaction import Transaction
from src.parsers.amex_parser import AmexStatementParser
from src.visualizations.charts import open_dashboard
from config import CATEGORY_RULES


@click.group()
def cli() -> None:
    """MoneyTalks — Amex statement analyser."""


# ---------------------------------------------------------------------------
# import
# ---------------------------------------------------------------------------

@cli.command("import")
@click.argument("pdf_path", type=click.Path(exists=True))
def import_statement(pdf_path: str) -> None:
    """Parse an Amex PDF statement and store transactions to the database."""
    init_db()
    session = get_session()

    click.echo(f"Parsing {pdf_path} ...")
    parser = AmexStatementParser()
    raw_txns = parser.parse(pdf_path)

    if not raw_txns:
        click.echo("No transactions found. Check that the PDF is an Amex statement.")
        return

    transactions = [
        Transaction(
            date=r.date,
            description=r.description,
            merchant=clean_merchant(r.description),
            amount=r.amount,
            category=categorize(r.description, r.category_hint),
            transaction_type=r.transaction_type,
            statement_closing_date=r.statement_closing_date,
        )
        for r in raw_txns
    ]

    inserted, skipped = insert_transactions(session, transactions)
    session.close()
    click.echo(f"{inserted} imported, {skipped} skipped (duplicates).")


# ---------------------------------------------------------------------------
# visualize
# ---------------------------------------------------------------------------

@cli.command()
@click.option("--month", default=None, help="YYYY-MM — filter to a specific month")
@click.option("--year", default=None, help="YYYY — filter to a specific year")
def visualize(month: str | None, year: str | None) -> None:
    """Open an interactive spending dashboard in the browser."""
    start_date, end_date = _parse_date_range(month, year)
    session = get_session()
    charges = get_charges(session, start_date, end_date)
    session.close()

    if not charges:
        click.echo("No charges found for the selected period.")
        return

    click.echo(f"Opening dashboard for {len(charges)} transactions ...")
    open_dashboard(to_dataframe(charges))


# ---------------------------------------------------------------------------
# summary
# ---------------------------------------------------------------------------

@cli.command()
@click.option("--month", default=None, help="YYYY-MM — filter to a specific month")
@click.option("--year", default=None, help="YYYY — filter to a specific year")
def summary(month: str | None, year: str | None) -> None:
    """Print a spending summary to the terminal."""
    start_date, end_date = _parse_date_range(month, year)
    session = get_session()
    charges = get_charges(session, start_date, end_date)
    session.close()

    if not charges:
        click.echo("No charges found.")
        return

    df = to_dataframe(charges)
    total = df["amount"].sum()

    click.echo(f"\nTransactions : {len(charges)}")
    click.echo(f"Total spent  : ${total:,.2f}\n")
    click.echo(f"{'Category':<22} {'Amount':>10}  {'Share':>7}")
    click.echo("-" * 44)
    by_cat = df.groupby("category")["amount"].sum().sort_values(ascending=False)
    for cat, amt in by_cat.items():
        pct = (amt / total) * 100
        click.echo(f"{cat:<22} ${amt:>9,.2f}  {pct:>6.1f}%")


# ---------------------------------------------------------------------------
# categories
# ---------------------------------------------------------------------------

@cli.command()
def categories() -> None:
    """List all category rules."""
    for category, keywords in CATEGORY_RULES.items():
        click.echo(f"\n{click.style(category, bold=True)}")
        for kw in keywords:
            click.echo(f"  {kw}")


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _parse_date_range(
    month: str | None, year: str | None
) -> tuple[date | None, date | None]:
    if month:
        dt = datetime.strptime(month, "%Y-%m")
        start = dt.replace(day=1).date()
        end = (
            dt.replace(year=dt.year + 1, month=1, day=1).date()
            if dt.month == 12
            else dt.replace(month=dt.month + 1, day=1).date()
        )
        return start, end
    if year:
        y = int(year)
        return date(y, 1, 1), date(y + 1, 1, 1)
    return None, None


if __name__ == "__main__":
    cli()
