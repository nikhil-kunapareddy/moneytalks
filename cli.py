"""
MoneyTalks CLI

Usage:
  python cli.py import data/                 # every .pdf/.csv in the folder
  python cli.py import data/2026-03-10.pdf
  python cli.py visualize --month 2026-02
  python cli.py visualize --year 2026
  python cli.py summary --month 2026-02
  python cli.py categories
"""

from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path

import click

from src.analysis.aggregator import to_dataframe
from src.analysis.categorizer import categorize, clean_merchant
from src.db.connection import get_session, init_db
from src.db.repository import get_charges, get_date_bounds, insert_transactions
from src.models.transaction import Transaction
from src.parsers import SUPPORTED_SUFFIXES, RawTransaction, detect_parser
from src.visualizations.dashboard import open_dashboard
from config import CATEGORY_RULES


@click.group()
def cli() -> None:
    """MoneyTalks — credit card statement analyser."""


# ---------------------------------------------------------------------------
# import
# ---------------------------------------------------------------------------

@cli.command("import")
@click.argument("paths", nargs=-1, required=True, type=click.Path(exists=True, path_type=Path))
@click.option(
    "--account",
    default=None,
    help='Label stored on every transaction, overriding the detected card (e.g. "Amex Gold")',
)
def import_statement(paths: tuple[Path, ...], account: str | None) -> None:
    """Import statements from files or folders (Amex, Chase, Citi, Bank of America).

    Re-importing a file is safe: transactions already stored are skipped.
    """
    files = _statement_files(paths)
    if not files:
        click.echo("No .pdf or .csv files found.")
        return

    init_db()
    session = get_session()
    total_inserted = total_skipped = 0
    try:
        for path in files:
            parser = detect_parser(path)
            if parser is None:
                click.echo(f"  {path.name}: skipped, not a recognised statement")
                continue
            try:
                raw_txns = parser.parse(str(path))
            except Exception as exc:  # one bad file shouldn't stop the batch
                click.echo(f"  {path.name}: could not be read ({exc})")
                continue
            if not raw_txns:
                click.echo(f"  {path.name}: no transactions found")
                continue

            transactions = _to_models(raw_txns, account)
            inserted, skipped = insert_transactions(session, transactions)
            total_inserted += inserted
            total_skipped += skipped
            click.echo(
                f"  {path.name} [{transactions[0].account}]: "
                f"{inserted} imported, {skipped} already stored"
            )
    finally:
        session.close()

    click.echo(f"\n{total_inserted} imported, {total_skipped} skipped from {len(files)} file(s).")


def _statement_files(paths: tuple[Path, ...]) -> list[Path]:
    """Expand folders (non-recursive) into their .pdf/.csv files."""
    files: list[Path] = []
    for path in paths:
        if path.is_dir():
            files.extend(sorted(
                p for p in path.iterdir()
                if p.is_file() and p.suffix.lower() in SUPPORTED_SUFFIXES
            ))
        else:
            files.append(path)
    return files


def _to_models(raw_txns: list[RawTransaction], account: str | None) -> list[Transaction]:
    seen: Counter = Counter()
    models = []
    for r in raw_txns:
        # Number identical rows so a genuine repeat (same day, merchant, amount)
        # is stored, while re-importing the same statement is still a no-op.
        key = (r.date, r.description, r.amount, r.transaction_type)
        models.append(Transaction(
            account=account or r.account,
            seq=seen[key],
            date=r.date,
            description=r.description,
            merchant=clean_merchant(r.description),
            amount=r.amount,
            category=categorize(r.description, r.category_hint),
            transaction_type=r.transaction_type,
            statement_closing_date=r.statement_closing_date,
        ))
        seen[key] += 1
    return models


# ---------------------------------------------------------------------------
# visualize
# ---------------------------------------------------------------------------

@cli.command()
@click.option("--month", default=None, help="YYYY-MM — filter to a specific month")
@click.option("--year", default=None, help="YYYY — filter to a specific year")
@click.option(
    "--output",
    type=click.Path(dir_okay=False),
    default=None,
    help="Save the dashboard HTML here (default: a file in the system temp folder)",
)
@click.option("--no-open", is_flag=True, help="Write the file without opening a browser")
def visualize(
    month: str | None, year: str | None, output: str | None, no_open: bool
) -> None:
    """Open the Overview dashboard in the browser."""
    start_date, end_date = _parse_date_range(month, year)
    init_db()
    session = get_session()
    charges = get_charges(session, start_date, end_date)

    if not charges:
        session.close()
        click.echo("No charges found for the selected period.")
        return

    # The period is the filter range clamped to the dates actually covered by
    # imported statements, so days outside the data aren't shown as $0.
    first, last = get_date_bounds(session)
    period_start = max(start_date, first) if start_date else first
    period_end = min(end_date - timedelta(days=1), last) if end_date else last
    session.close()

    path = open_dashboard(
        to_dataframe(charges),
        period_start,
        period_end,
        output=output,
        open_browser=not no_open,
    )
    click.echo(f"Dashboard for {len(charges)} transactions: {path}")


# ---------------------------------------------------------------------------
# summary
# ---------------------------------------------------------------------------

@cli.command()
@click.option("--month", default=None, help="YYYY-MM — filter to a specific month")
@click.option("--year", default=None, help="YYYY — filter to a specific year")
def summary(month: str | None, year: str | None) -> None:
    """Print a spending summary to the terminal."""
    start_date, end_date = _parse_date_range(month, year)
    init_db()
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
