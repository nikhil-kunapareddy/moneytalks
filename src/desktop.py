"""MoneyTalks Mac app: a native window around the Overview dashboard.

The window shows the same HTML the CLI writes for the browser. The page's
"Import statement" button calls ``Api.import_statements`` through pywebview,
which opens a native file picker, imports the chosen statements and reloads
the page.

Database settings come from config.py; inside the app bundle that means
``~/Library/Application Support/MoneyTalks/config.env``.
"""

import sys
import tempfile
from datetime import date
from pathlib import Path
from typing import Optional

import webview
from sqlalchemy.exc import SQLAlchemyError

from config import APP_CONFIG_FILE
from src.db.connection import get_session, init_db
from src.services.importer import import_files, statement_files
from src.services.overview import load_overview
from src.visualizations.dashboard import render_dashboard, render_message

WINDOW_TITLE = "MoneyTalks"
FILE_TYPES = ("Statements (*.pdf;*.csv)",)


def build_page(notice: Optional[str] = None) -> str:
    """HTML for the window: the dashboard, an empty state, or a connection error."""
    try:
        init_db()
        session = get_session()
        try:
            overview = load_overview(session)
        finally:
            session.close()
    except SQLAlchemyError as exc:
        return render_message(
            "Can't reach your database",
            "MoneyTalks couldn't connect to PostgreSQL. Check that Postgres is running "
            f"and that DATABASE_URL in\n{APP_CONFIG_FILE}\nis correct, then try again "
            "(reopen the app after editing the file).\n\n"
            f"{_first_line(exc)}",
            actions=["retry"],
            notice=notice,
        )

    if overview is None:
        return render_message(
            "No transactions yet",
            "Import a credit card statement to see your Overview. PDF statements from "
            "Amex, Chase, Citi and Bank of America work, as does the Amex CSV download.",
            actions=["import"],
            notice=notice,
        )
    return render_dashboard(overview.df, overview.start, overview.end, notice=notice, app=True)


class Api:
    """Methods the page can call as ``window.pywebview.api.<name>()``."""

    def import_statements(self) -> Optional[str]:
        window = webview.windows[0]
        chosen = window.create_file_dialog(
            webview.FileDialog.OPEN, allow_multiple=True, file_types=FILE_TYPES
        )
        if not chosen:
            return None  # cancelled

        try:
            init_db()
            session = get_session()
            try:
                report = import_files(session, statement_files(Path(p) for p in chosen))
            finally:
                session.close()
            notice = report.summary()
            if report.problems:
                notice += " " + "; ".join(f"{f.name}: {f.error}" for f in report.problems)
        except SQLAlchemyError as exc:
            notice = f"Import failed: {_first_line(exc)}"

        window.load_html(build_page(notice))
        return notice

    def refresh(self) -> None:
        webview.windows[0].load_html(build_page())


def _first_line(exc: Exception) -> str:
    text = str(exc).strip().splitlines()
    return f"{type(exc).__name__}: {text[0] if text else ''}"


def smoke_test() -> int:
    """Run by CI against the built app: bundled code, templates and native libraries load."""
    import pandas as pd
    import psycopg2  # noqa: F401 (loads the bundled libpq)
    import pypdfium2

    from src.parsers import detect_parser

    pypdfium2.PdfDocument.new()  # loads the bundled pdfium library

    df = pd.DataFrame([{
        "date": date(2026, 1, 5), "merchant": "Smoke Test", "description": "SMOKE TEST",
        "amount": 12.5, "category": "shopping", "transaction_type": "charge",
    }])
    pages = [
        render_dashboard(df, date(2026, 1, 1), date(2026, 1, 31), notice="ok", app=True),
        render_message("Title", "Body", actions=["import", "retry"]),
    ]
    for html in pages:
        assert "data:image/png;base64," in html, "icon not embedded"
        assert "/*__DATA__*/" not in html, "data not injected"

    with tempfile.TemporaryDirectory() as tmp:
        sample = Path(tmp) / "activity.csv"
        sample.write_text("Date,Description,Amount\n01/05/2026,SMOKE TEST,12.50\n")
        parser = detect_parser(sample)
        assert parser is not None and len(parser.parse(str(sample))) == 1, "CSV parser"

    print("MoneyTalks smoke test passed")
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if "--smoke-test" in argv:
        return smoke_test()

    webview.create_window(
        WINDOW_TITLE,
        html=build_page(),
        js_api=Api(),
        width=1380,
        height=940,
        min_size=(960, 700),
        background_color="#f2f2f2",  # same as the page, no grey flash on load
    )
    webview.start()
    return 0
