"""Load the periods (all time, years, months) shown on the Overview dashboard."""

import calendar
from dataclasses import dataclass
from datetime import date

import pandas as pd
from sqlalchemy.orm import Session

from src.analysis.aggregator import to_dataframe
from src.db.repository import get_charges, get_date_bounds


@dataclass
class Period:
    key: str  # "all", "2026", "2026-11"
    label: str  # "All time", "2026", "November 2026"
    kind: str  # "all" | "year" | "month"
    df: pd.DataFrame  # charges in the period
    start: date  # inclusive, clamped to the dates covered by imported statements
    end: date  # inclusive

    @property
    def charges(self) -> int:
        return len(self.df)


def load_periods(session: Session) -> list[Period]:
    """All time, then every year and every month that has charges, newest first.

    Each period is clamped to the dates actually covered by imported statements,
    so days outside the data aren't shown as $0. Empty if there are no charges.
    """
    charges = get_charges(session)
    if not charges:
        return []
    df = to_dataframe(charges)
    first, last = get_date_bounds(session)
    dates = pd.to_datetime(df["date"])

    def period(key: str, label: str, kind: str, mask, start: date, end: date) -> Period:
        return Period(key, label, kind, df[mask].reset_index(drop=True),
                      max(start, first), min(end, last))

    periods = [Period("all", "All time", "all", df, first, last)]
    for year in sorted({int(y) for y in dates.dt.year}, reverse=True):
        periods.append(period(str(year), str(year), "year", (dates.dt.year == year).to_numpy(),
                              date(year, 1, 1), date(year, 12, 31)))
    months = sorted({(int(y), int(m)) for y, m in zip(dates.dt.year, dates.dt.month)}, reverse=True)
    for year, month in months:
        mask = ((dates.dt.year == year) & (dates.dt.month == month)).to_numpy()
        last_day = calendar.monthrange(year, month)[1]
        periods.append(period(f"{year}-{month:02d}", date(year, month, 1).strftime("%B %Y"),
                              "month", mask, date(year, month, 1), date(year, month, last_day)))
    return periods
