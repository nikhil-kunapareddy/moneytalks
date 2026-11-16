"""MoneyTalks Mac app: a native window around the Overview dashboard.

The window shows the same HTML the CLI writes for the browser. The page's
"Import statement" button calls ``Api.import_statements`` through pywebview,
which opens a native file picker, imports the chosen statements and reloads
the page. Updates come from GitHub Releases (src/updater.py): checked at launch
and from MoneyTalks ▸ Check for Updates…, downloaded in the background and
installed on quit or via the page's "Restart to update" banner.

Database settings come from config.py; inside the app bundle that means
``~/Library/Application Support/MoneyTalks/config.env``.
"""

import json
import sys
import tempfile
import webbrowser
from datetime import date
from pathlib import Path
from typing import Optional

import webview
from sqlalchemy.exc import SQLAlchemyError
from webview.menu import Menu, MenuAction

from config import APP_CONFIG_FILE, AUTO_UPDATE
from src.db.connection import get_session, init_db
from src.services.importer import import_files, statement_files
from src.services.overview import Period, load_periods
from src.updater import REPO, Updater, app_bundle
from src.visualizations.dashboard import render_dashboard, render_message

WINDOW_TITLE = "MoneyTalks"
FILE_TYPES = ("Statements (*.pdf;*.csv)",)


def build_page(notice: Optional[str] = None, period: str = "all") -> str:
    """HTML for the window: the dashboard, an empty state, or a connection error.

    ``period`` is the period key to open on (kept across imports).
    """
    try:
        init_db()
        session = get_session()
        try:
            periods = load_periods(session)
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

    if not periods:
        return render_message(
            "No transactions yet",
            "Import a credit card statement to see your Overview. PDF statements from "
            "Amex, Chase, Citi and Bank of America work, as does the Amex CSV download.",
            actions=["import"],
            notice=notice,
        )
    return render_dashboard(periods, period, notice=notice, app=True)


class Api:
    """Methods the page can call as ``window.pywebview.api.<name>()``."""

    def import_statements(self, period: str = "all") -> Optional[str]:
        """File picker → import → reload, staying on the period being viewed."""
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

        window.load_html(build_page(notice, period))
        return notice

    def refresh(self) -> None:
        webview.windows[0].load_html(build_page())

    def check_for_updates(self) -> None:
        UPDATER.check(manual=True)

    def restart_to_update(self) -> None:
        if UPDATER.restart_to_update():
            webview.windows[0].destroy()  # the installer swaps the app and relaunches it

    def open_url(self, url: str) -> None:
        if isinstance(url, str) and url.startswith(f"https://github.com/{REPO}/"):  # this repo only
            webbrowser.open(url)


def _push_update_state(state: dict) -> None:
    """Show the updater's state in the page banner (window.mtUpdate)."""
    if not webview.windows:
        return
    try:
        webview.windows[0].evaluate_js(f"window.mtUpdate && window.mtUpdate({json.dumps(state)})")
    except Exception:
        pass  # window closing or page mid-reload; the loaded event re-sends the state


UPDATER = Updater(on_change=_push_update_state)


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
    periods = [
        Period("all", "All time", "all", df, date(2026, 1, 1), date(2026, 1, 31)),
        Period("2026-01", "January 2026", "month", df, date(2026, 1, 1), date(2026, 1, 31)),
    ]
    pages = [
        render_dashboard(periods, "2026-01", notice="ok", app=True),
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

    import certifi

    from src.updater import current_version, version_key

    assert Path(certifi.where()).is_file(), "certifi CA bundle missing"
    assert version_key("v0.2.10") > version_key("0.2.9") > version_key("0.2.0-local"), "version compare"
    assert "window.mtUpdate" in pages[0], "update banner not injected"
    print(f"MoneyTalks {current_version()} smoke test passed")
    return 0


def update_now() -> int:
    """Headless: check, download and stage the latest release, then install it on exit."""
    from src.updater import current_version, download, fetch_latest, install_blocker, launch_installer, stage, version_key

    release = fetch_latest()
    print(f"installed {current_version()}, latest {release.version}")
    if version_key(release.version) <= version_key(current_version()):
        print("already up to date")
        return 0
    blocker = install_blocker()
    if blocker:
        print(f"can't install: {blocker}")
        return 1
    dmg = download(release, lambda p: print(f"\rdownloading {p}%", end="", flush=True))
    print()
    staged = stage(dmg, release.version)
    launch_installer(staged, relaunch=False)
    print(f"staged {staged}; it replaces {app_bundle()} as this process exits")
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if "--smoke-test" in argv:
        return smoke_test()
    if "--update-now" in argv:
        return update_now()

    window = webview.create_window(
        WINDOW_TITLE,
        html=build_page(),
        js_api=Api(),
        width=1380,
        height=940,
        min_size=(960, 700),
        background_color="#f2f2f2",  # same as the page, no grey flash on load
    )
    # Re-send the update banner after every page load (imports reload the page).
    window.events.loaded += lambda: _push_update_state(UPDATER.state)
    # ⌘Q and the close button both fire "closing": install a downloaded update then.
    window.events.closing += lambda: UPDATER.install_on_quit()

    if AUTO_UPDATE and app_bundle() is not None:
        UPDATER.start_automatic_checks()

    webview.start(menu=[
        Menu("__app__", [MenuAction("Check for Updates…", lambda: UPDATER.check(manual=True))]),
    ])
    return 0
