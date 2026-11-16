"""Overview dashboard pages.

Builds a JSON payload from charge DataFrames and injects it into the static
HTML templates in ``templates/``. All rendering (charts, hover, insights)
happens client-side. The CLI writes the page to a file and opens a browser;
the Mac app shows the same HTML in its window.
"""

import base64
import json
import tempfile
import webbrowser
from collections.abc import Sequence
from datetime import date, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Optional

import pandas as pd

if TYPE_CHECKING:
    from src.services.overview import Period

from src.analysis.aggregator import (
    daily_spending,
    monthly_spending,
    spending_by_category,
    top_merchants,
)

TEMPLATE_PATH = Path(__file__).parent / "templates" / "dashboard.html"
MESSAGE_TEMPLATE_PATH = Path(__file__).parent / "templates" / "message.html"
ICON_PATH = Path(__file__).parent / "assets" / "icon-128.png"
DEFAULT_OUTPUT = Path(tempfile.gettempdir()) / "moneytalks-dashboard.html"
DATA_PLACEHOLDER = "/*__DATA__*/null"
ICON_PLACEHOLDER = "__ICON__"

WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
CATEGORY_LABELS = {
    "food_dining": "Food & Dining",
    "health_fitness": "Health & Fitness",
}


def open_dashboard(
    periods: Sequence["Period"],
    initial: str = "all",
    output: str | Path | None = None,
    open_browser: bool = True,
) -> Path:
    """Write the dashboard HTML and (optionally) open it. Returns the file path."""
    path = Path(output) if output else DEFAULT_OUTPUT
    path.write_text(render_dashboard(periods, initial), encoding="utf-8")
    if open_browser:
        webbrowser.open(path.resolve().as_uri())
    return path


def render_dashboard(
    periods: Sequence["Period"],
    initial: str = "all",
    notice: Optional[str] = None,
    app: bool = False,
) -> str:
    """Full HTML of the Overview page with a period picker.

    Every period's figures are embedded, so switching between all time, years
    and months happens instantly in the page (also when opened in a browser).
    ``initial`` is the period key shown first; ``notice`` shows as a toast (e.g.
    import results); ``app`` drops the outer grey margin and rounded frame so
    the page fills the Mac app's window.
    """
    if not periods:
        raise ValueError("render_dashboard needs at least one period")
    keys = {p.key for p in periods}
    payload = {
        "periods": [
            {"key": p.key, "label": p.label, "kind": p.kind, "range": _range_label(p.start, p.end)}
            for p in periods
        ],
        "views": {p.key: build_payload(p.df, p.start, p.end) for p in periods},
        "initial": initial if initial in keys else periods[0].key,
        "notice": notice,
    }
    return _fill_template(TEMPLATE_PATH, payload, app=app)


def render_message(
    title: str,
    body: str,
    actions: Sequence[str] = (),
    notice: Optional[str] = None,
) -> str:
    """A simple full-page message (empty database, connection error) for the Mac app.

    ``actions`` may contain "import" and/or "retry".
    """
    payload = {"title": title, "body": body, "actions": list(actions), "notice": notice}
    return _fill_template(MESSAGE_TEMPLATE_PATH, payload, app=True)


def _fill_template(path: Path, payload: dict, app: bool = False) -> str:
    template = path.read_text(encoding="utf-8")
    if app:
        # Set before first paint, so the window never flashes the framed layout.
        template = template.replace('<html lang="en">', '<html lang="en" class="app">', 1)
    # Pages are single self-contained documents, so the icon is inlined.
    # The icon goes in before the data so text in the data is never substituted.
    icon_uri = "data:image/png;base64," + base64.b64encode(ICON_PATH.read_bytes()).decode()
    return template.replace(ICON_PLACEHOLDER, icon_uri).replace(DATA_PLACEHOLDER, _to_js(payload))


def build_payload(df: pd.DataFrame, period_start: date, period_end: date) -> dict:
    """Aggregate charges for ``period_start``..``period_end`` (inclusive)."""
    df = df.assign(category=df["category"].fillna("uncategorized"))
    total = float(df["amount"].sum())
    days = (period_end - period_start).days + 1
    biggest = df.loc[df["amount"].idxmax()]

    return {
        "period": {"label": _range_label(period_start, period_end)},
        "totals": {
            "spent": round(total, 2),
            "charges": len(df),
            "avg": round(total / len(df), 2),
            "merchants": int(df["merchant"].nunique()),
        },
        "categories": _categories(df, total),
        "merchants": _merchants(df, total),
        "daily": _daily(df, period_start, days),
        "weekly": _weekly(df, period_start, period_end),
        "monthly": [
            {"label": row["month"].strftime("%b %Y"), "amount": round(float(row["amount"]), 2)}
            for _, row in monthly_spending(df).iterrows()
        ],
        "weekday": _weekday(df),
        "biggest": {
            "merchant": biggest["merchant"],
            "amount": round(float(biggest["amount"]), 2),
            "date": _day(biggest["date"]),
        },
    }


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _categories(df: pd.DataFrame, total: float) -> list[dict]:
    out = []
    for key, amount in spending_by_category(df).items():
        rows = df[df["category"] == key]
        by_merchant = rows.groupby("merchant")["amount"].sum()
        out.append({
            "label": CATEGORY_LABELS.get(key, key.replace("_", " ").title()),
            "amount": round(float(amount), 2),
            "count": len(rows),
            "share": float(amount) / total,
            "topMerchant": by_merchant.idxmax(),
            "topMerchantAmount": round(float(by_merchant.max()), 2),
        })
    return out


def _merchants(df: pd.DataFrame, total: float) -> list[dict]:
    counts = df["merchant"].value_counts()
    return [
        {
            "name": row["merchant"],
            "amount": round(float(row["amount"]), 2),
            "count": int(counts[row["merchant"]]),
            "share": float(row["amount"]) / total,
        }
        for _, row in top_merchants(df, n=10).iterrows()
    ]


def _daily(df: pd.DataFrame, start: date, days: int) -> list[dict]:
    by_day = daily_spending(df).set_index("date")["amount"]
    out = []
    for i in range(days):
        d = start + timedelta(days=i)
        out.append({"label": _day(d), "amount": round(float(by_day.get(d, 0.0)), 2)})
    return out


def _weekly(df: pd.DataFrame, start: date, end: date) -> list[dict]:
    """Consecutive 7-day buckets starting at the period start."""
    out = []
    week_start = start
    while week_start <= end:
        week_end = min(week_start + timedelta(days=6), end)
        in_week = (df["date"] >= week_start) & (df["date"] <= week_end)
        out.append({
            "label": _range_label(week_start, week_end),
            "amount": round(float(df.loc[in_week, "amount"].sum()), 2),
        })
        week_start = week_end + timedelta(days=1)
    return out


def _weekday(df: pd.DataFrame) -> list[dict]:
    weekday = pd.to_datetime(df["date"]).dt.weekday
    grouped = df.groupby(weekday)["amount"].agg(["sum", "count"])
    return [
        {
            "day": name,
            "count": int(grouped["count"].get(i, 0)),
            "amount": round(float(grouped["sum"].get(i, 0.0)), 2),
        }
        for i, name in enumerate(WEEKDAYS)
    ]


def _day(d: date) -> str:
    return d.strftime("%b %d")


def _range_label(start: date, end: date) -> str:
    return _day(start) if start == end else f"{_day(start)} – {_day(end)}"


def _to_js(payload: dict) -> str:
    # Escape "<" so merchant text from PDFs can never close the <script> tag.
    return json.dumps(payload).replace("<", "\\u003c")
