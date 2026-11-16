# MoneyTalks

Import credit card statements from Amex, Chase, Citi and Bank of America, store every transaction in a local PostgreSQL database, and explore your spending through interactive browser-based dashboards.

---

## Features

- **Multi-bank import** — Point it at a folder of PDF/CSV statements; each file's bank is detected automatically and every transaction is stored with its card (e.g. `Chase ••1234`). Re-importing is safe: stored transactions are skipped
- **Smart Categorisation** — Rule-based keyword matching across 9 categories (groceries, dining, travel, transportation, shopping, personal care, convenience, health & fitness, subscriptions), plus fees and interest from the statement's fee sections
- **PostgreSQL Storage** — Persistent, deduplication-safe transaction storage via SQLAlchemy; import the same statement twice without creating duplicates
- **Overview Dashboard** — A single-page dashboard opens in your browser: spending by category, total spent with top merchants, daily/weekly/monthly spending, charges and merchants by weekday, and auto-generated insights
- **Simple CLI** — Four commands cover the full workflow: `import`, `visualize`, `summary`, `categories`

---

## Tech Stack

| Layer | Library |
|---|---|
| PDF extraction | [pdfplumber](https://github.com/jsvine/pdfplumber) |
| Data wrangling | [pandas](https://pandas.pydata.org/) |
| ORM / database | [SQLAlchemy](https://www.sqlalchemy.org/) + [psycopg2](https://www.psycopg.org/) |
| Visualisation | Static HTML + inline SVG (no JS dependencies) |
| CLI | [Click](https://click.palletsprojects.com/) |
| Configuration | [python-dotenv](https://github.com/theskumar/python-dotenv) |

---

## Prerequisites

- Python 3.11+
- PostgreSQL 14+

---

## Installation

```bash
# 1. Clone the repository
git clone <your-repo-url>
cd moneytalks

# 2. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate        # macOS / Linux
# .venv\Scripts\activate         # Windows

# 3. Install dependencies
pip install -r requirements.txt
```

---

## Configuration

Copy the example environment file and fill in your PostgreSQL credentials:

```bash
cp .env.example .env
```

Edit `.env`:

```env
DATABASE_URL=postgresql://user:password@localhost/moneytalks
```

Create the database (first time only):

```bash
createdb moneytalks
```

---

## Usage

Place your statements (PDF or CSV) in the `data/` folder, then use the commands below.

### Import statements

Detects each file's bank, parses it and stores every transaction. Transactions already in the database are skipped, so re-running on the same folder is safe.

```bash
# Every .pdf/.csv in a folder
python cli.py import data/

# Specific files
python cli.py import data/2026-03-10.pdf data/activity.csv

# Override the card label (useful for CSVs, which don't name the card)
python cli.py import data/activity.csv --account "Amex Gold"
```

```
  20261109-statements-1234-.pdf [Chase ••1234]: 15 imported, 0 already stored
  October 27.pdf [Citi ••5678]: 2 imported, 0 already stored

17 imported, 0 skipped from 2 file(s).
```

### Visualise spending

Opens the Overview dashboard in your default browser.

```bash
# All transactions in the database
python cli.py visualize

# Filter to a specific month
python cli.py visualize --month 2026-02

# Filter to a full year
python cli.py visualize --year 2026

# Save the HTML somewhere specific without opening a browser
python cli.py visualize --output overview.html --no-open
```

By default the page is written to `moneytalks-dashboard.html` in your system temp folder.

### Terminal summary

Prints a category breakdown to the terminal.

```bash
python cli.py summary --month 2026-02
```

```
Transactions : 31
Total spent  : $1,573.71

Category               Amount     Share
--------------------------------------------
travel                $709.74    45.1%
groceries             $368.02    23.4%
food_dining           $146.39     9.3%
...
```

### List category rules

```bash
python cli.py categories
```

---

## Mac App

MoneyTalks also ships as a native Mac app (Apple Silicon): a window with the
Overview dashboard whose **Import statement** button opens a file picker for
PDF/CSV statements.

### Install

1. Download `MoneyTalks-<version>.dmg` from the repository's **Releases** page.
2. Open it and drag **MoneyTalks** onto **Applications**.
3. First launch only: the app isn't signed with an Apple Developer ID, so macOS
   blocks it. Open **System Settings → Privacy & Security** and click
   **Open Anyway** next to the MoneyTalks message (or run
   `xattr -dr com.apple.quarantine /Applications/MoneyTalks.app`).

### Database settings

The app uses the same PostgreSQL database as the CLI. Because it has no project
folder, it reads `DATABASE_URL` from:

```
~/Library/Application Support/MoneyTalks/config.env
```

```env
DATABASE_URL=postgresql://user:password@localhost/moneytalks
```

If the app can't connect it shows this path and the error; edit the file and
reopen the app.

### Releases (CI)

Every push to `main` runs `.github/workflows/release.yml` on GitHub's latest macOS runner (Apple Silicon): it
builds the app, smoke-tests the bundle, packages a `.dmg` and publishes a GitHub
release tagged `v<MAJOR>.<MINOR>.<run number>` (MAJOR.MINOR come from
`pyproject.toml`).

### Build locally

```bash
pip install -r requirements-app.txt
packaging/build_macos.sh 0.2.0        # → dist/MoneyTalks-0.2.0.dmg
python app.py                          # or run from source without packaging
```

---

## Project Structure

```
moneytalks/
├── data/                        # Drop PDF/CSV statements here (git-ignored)
│   └── .gitkeep
├── src/
│   ├── parsers/
│   │   ├── __init__.py          # detect_parser(): picks the parser for a file
│   │   ├── base.py              # RawTransaction + shared helpers
│   │   ├── amex_parser.py       # Amex PDF statements
│   │   ├── amex_csv.py          # Amex CSV export
│   │   └── card_pdf.py          # Citi, Chase, Bank of America PDF statements
│   ├── models/
│   │   └── transaction.py       # SQLAlchemy Transaction ORM model
│   ├── db/
│   │   ├── connection.py        # Engine, session factory, schema initialisation
│   │   └── repository.py       # DB read/write helpers
│   ├── analysis/
│   │   ├── categorizer.py       # Merchant name cleaning + rule-based categorisation
│   │   └── aggregator.py       # Pandas aggregations (by category, monthly, etc.)
│   ├── services/
│   │   ├── importer.py          # Import files → DB (shared by CLI and app)
│   │   └── overview.py          # Load charges + period for the dashboard
│   ├── visualizations/
│   │   ├── dashboard.py         # Builds dashboard data, renders the HTML pages
│   │   ├── assets/              # App icon
│   │   └── templates/
│   │       ├── dashboard.html   # Overview dashboard page (HTML/CSS/SVG)
│   │       └── message.html     # App empty-state / error page
│   └── desktop.py               # Mac app window (pywebview) + import bridge
├── packaging/
│   ├── MoneyTalks.spec          # PyInstaller spec for MoneyTalks.app
│   ├── MoneyTalks.icns          # App icon
│   └── build_macos.sh           # Build .app + .dmg
├── .github/workflows/release.yml  # CI: build + release on every push to main
├── app.py                       # Mac app entry point
├── cli.py                       # Click CLI entry point
├── config.py                    # DATABASE_URL + CATEGORY_RULES + MERCHANT_ALIASES
├── pyproject.toml               # Project metadata and tool configuration
├── requirements.txt
├── requirements-app.txt         # + pywebview, PyInstaller (Mac app)
└── .env.example
```

---

## Extending Categories

Open `config.py` and add keywords to an existing category or define a new one:

```python
CATEGORY_RULES: dict[str, list[str]] = {
    "groceries": [
        "WHOLE FOODS", "TRADER JOE", ...  # add more keywords here
    ],
    "subscriptions": [           # new category
        "NETFLIX", "SPOTIFY", "APPLE.COM/BILL",
    ],
}
```

The categoriser checks each keyword in order; the first match wins. Keywords are case-insensitive. The PDF-embedded category hint (e.g. `RESTAURANT`) always takes priority over keyword rules.

---

## Development

Install optional dev tools:

```bash
pip install black isort ruff
```

| Command | Purpose |
|---|---|
| `black .` | Auto-format code |
| `isort .` | Sort imports |
| `ruff check .` | Lint |

Tool configuration is in `pyproject.toml`.

---

## Supported Statements

| Source | Format | Detected by |
|---|---|---|
| American Express | PDF statement | "American Express" on page 1–2 (or a `YYYY-MM-DD.pdf` file name) |
| American Express | CSV download (`Date,Description,Amount`) | CSV header |
| Chase credit cards | PDF statement | `chase.com` |
| Citi credit cards | PDF statement | `citi.com` |
| Bank of America credit cards | PDF statement | `bankofamerica.com` |

Another bank whose PDF lists activity as `MM/DD DESCRIPTION AMOUNT` lines under section headings can usually be added as a small subclass of `SectionedCardParser` in `src/parsers/card_pdf.py`.

---

## License

MIT
