"""Plotly dashboard builder — opens all charts in the default browser."""

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from src.analysis.aggregator import (
    daily_spending,
    monthly_spending,
    spending_by_category,
    top_merchants,
)


def open_dashboard(df: pd.DataFrame) -> None:
    """Build a 2x2 interactive dashboard and open it in the browser."""
    fig = make_subplots(
        rows=2,
        cols=2,
        subplot_titles=(
            "Spending by Category",
            "Top Merchants",
            "Daily Spending",
            "Monthly Spending",
        ),
        specs=[
            [{"type": "pie"}, {"type": "bar"}],
            [{"type": "bar"}, {"type": "bar"}],
        ],
    )

    _add_category_pie(fig, df, row=1, col=1)
    _add_top_merchants(fig, df, row=1, col=2)
    _add_daily(fig, df, row=2, col=1)
    _add_monthly(fig, df, row=2, col=2)

    fig.update_layout(
        title_text="MoneyTalks — Spending Dashboard",
        height=800,
        showlegend=False,
    )
    fig.show()


def _add_category_pie(fig: go.Figure, df: pd.DataFrame, row: int, col: int) -> None:
    by_cat = spending_by_category(df)
    fig.add_trace(
        go.Pie(
            labels=by_cat.index.tolist(),
            values=by_cat.values.tolist(),
            textinfo="label+percent",
            hovertemplate="%{label}<br>$%{value:.2f}<extra></extra>",
        ),
        row=row,
        col=col,
    )


def _add_top_merchants(fig: go.Figure, df: pd.DataFrame, row: int, col: int) -> None:
    top = top_merchants(df)
    fig.add_trace(
        go.Bar(
            x=top["amount"].tolist(),
            y=top["merchant"].tolist(),
            orientation="h",
            hovertemplate="%{y}<br>$%{x:.2f}<extra></extra>",
        ),
        row=row,
        col=col,
    )
    fig.update_yaxes(autorange="reversed", row=row, col=col)


def _add_daily(fig: go.Figure, df: pd.DataFrame, row: int, col: int) -> None:
    daily = daily_spending(df)
    fig.add_trace(
        go.Bar(
            x=daily["date"].astype(str).tolist(),
            y=daily["amount"].tolist(),
            hovertemplate="%{x}<br>$%{y:.2f}<extra></extra>",
        ),
        row=row,
        col=col,
    )


def _add_monthly(fig: go.Figure, df: pd.DataFrame, row: int, col: int) -> None:
    monthly = monthly_spending(df)
    fig.add_trace(
        go.Bar(
            x=monthly["month"].astype(str).tolist(),
            y=monthly["amount"].tolist(),
            hovertemplate="%{x}<br>$%{y:.2f}<extra></extra>",
        ),
        row=row,
        col=col,
    )
