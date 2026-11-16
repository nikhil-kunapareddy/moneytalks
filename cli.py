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

from datetime import date, datetime
from pathlib import Path

import click

from src.analysis.aggregator import to_dataframe
from src.db.connection import get_session, init_db
from src.db.repository import get_charges
from src.services.importer import import_files, statement_files
from src.services.overview import load_overview
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
    files = statement_files(paths)
    if not files:
        click.echo("No .pdf or .csv files found.")
        return

    init_db()
    session = get_session()
    try:
        report = import_files(session, files, account)
    finally:
        session.close()

    for result in report.files:
        if result.error:
            click.echo(f"  {result.name}: skipped, {result.error}")
        else:
            click.echo(
                f"  {result.name} [{result.account}]: "
                f"{result.inserted} imported, {result.skipped} already stored"
            )
    click.echo(f"\n{report.summary()}")


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
    try:
        overview = load_overview(session, start_date, end_date)
    finally:
        session.close()

    if overview is None:
        click.echo("No charges found for the selected period.")
        return

    path = open_dashboard(
        overview.df,
        overview.start,
        overview.end,
        output=output,
        open_browser=not no_open,
    )
    click.echo(f"Dashboard for {overview.charges} transactions: {path}")


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
