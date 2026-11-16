"""Load the charges and date range shown on the Overview dashboard."""

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional

import pandas as pd
from sqlalchemy.orm import Session

from src.analysis.aggregator import to_dataframe
from src.db.repository import get_charges, get_date_bounds


@dataclass
class Overview:
    df: pd.DataFrame
    start: date  # inclusive
    end: date  # inclusive

    @property
    def charges(self) -> int:
        return len(self.df)


def load_overview(
    session: Session,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> Optional[Overview]:
    """Charges in [start_date, end_date), or None if there are none.

    The period is the filter range clamped to the dates actually covered by
    imported statements, so days outside the data aren't shown as $0.
    """
    charges = get_charges(session, start_date, end_date)
    if not charges:
        return None
    first, last = get_date_bounds(session)
    period_start = max(start_date, first) if start_date else first
    period_end = min(end_date - timedelta(days=1), last) if end_date else last
    return Overview(to_dataframe(charges), period_start, period_end)
