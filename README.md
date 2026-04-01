# MoneyTalks

Parse your American Express credit card PDF statements, store transactions in PostgreSQL, and explore your spending through interactive browser-based dashboards.

---

## Features

- **PDF Parsing** — Extracts all transactions from Amex Blue Cash Everyday statements using pdfplumber, handling multi-column layouts and multi-line descriptions automatically
- **Smart Categorisation** — Rule-based keyword matching across 8 categories (groceries, dining, travel, transportation, shopping, personal care, convenience, health & fitness)
- **PostgreSQL Storage** — Persistent, deduplication-safe transaction storage via SQLAlchemy; import the same statement twice without creating duplicates
- **Interactive Dashboards** — Four Plotly charts open directly in your browser: spending by category, top merchants, daily spending, and monthly trends
- **Simple CLI** — Four commands cover the full workflow: `import`, `visualize`, `summary`, `categories`

---

## Tech Stack

| Layer | Library |
|---|---|
| PDF extraction | [pdfplumber](https://github.com/jsvine/pdfplumber) |
| Data wrangling | [pandas](https://pandas.pydata.org/) |
| ORM / database | [SQLAlchemy](https://www.sqlalchemy.org/) + [psycopg2](https://www.psycopg.org/) |
| Visualisation | [Plotly](https://plotly.com/python/) |
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

Place your Amex PDF statement in the `data/` folder, then use the commands below.

### Import a statement

Parses the PDF and stores all transactions to the database. Duplicate transactions are skipped automatically.

```bash
python cli.py import data/2026-03-10.pdf
```

```
Parsing data/2026-03-10.pdf ...
31 imported, 0 skipped (duplicates).
```

### Visualise spending

Opens an interactive 2×2 dashboard in your default browser.

```bash
# All transactions in the database
python cli.py visualize

# Filter to a specific month
python cli.py visualize --month 2026-02

# Filter to a full year
python cli.py visualize --year 2026
```

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

## Project Structure

```
moneytalks/
├── data/                        # Drop PDF statements here (git-ignored)
│   └── .gitkeep
├── src/
│   ├── parsers/
│   │   └── amex_parser.py       # PDF text extraction → RawTransaction objects
│   ├── models/
│   │   └── transaction.py       # SQLAlchemy Transaction ORM model
│   ├── db/
│   │   ├── connection.py        # Engine, session factory, schema initialisation
│   │   └── repository.py       # DB read/write helpers
│   ├── analysis/
│   │   ├── categorizer.py       # Merchant name cleaning + rule-based categorisation
│   │   └── aggregator.py       # Pandas aggregations (by category, monthly, etc.)
│   └── visualizations/
│       └── charts.py            # Plotly dashboard builder
├── cli.py                       # Click CLI entry point
├── config.py                    # DATABASE_URL + CATEGORY_RULES
├── pyproject.toml               # Project metadata and tool configuration
├── requirements.txt
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

## Contributing

We use a **Git Flow-lite** branching model:

```
main          ← stable, production-ready
└── dev       ← integration branch; all features merge here first
    ├── feature/backend-*
    └── feature/frontend-*
```

### Branching rules

- Always branch off `dev`, never directly off `main`
- Use the prefixes below to keep the branch list organised:

| Work | Branch prefix | Example |
|---|---|---|
| Backend (parser, DB, API) | `feature/backend-` | `feature/backend-multi-card-support` |
| Frontend (UI, dashboards) | `feature/frontend-` | `feature/frontend-spending-trends` |
| Bug fix | `fix/` | `fix/amex-parser-date-format` |
| Refactor | `refactor/` | `refactor/categorizer-rules` |

### Workflow

```bash
# 1. Start from an up-to-date dev branch
git checkout dev && git pull origin dev

# 2. Create your feature branch
git checkout -b feature/backend-your-feature

# 3. Commit your changes
git add <files>
git commit -m "feat(backend): short description of change"

# 4. Push and open a PR into dev
git push -u origin feature/backend-your-feature
```

Open a pull request targeting `dev`. Once `dev` is stable and tested, it is merged into `main` via a separate PR.

### Commit message style

```
<type>(<scope>): <short description>

Types : feat | fix | refactor | docs | chore
Scopes: backend | frontend | parser | db | cli | config
```

Examples:
- `feat(backend): add REST API endpoint for transactions`
- `feat(frontend): add monthly spending bar chart`
- `fix(parser): handle Amex statements with foreign currency charges`

---

## Supported Statements

| Card | Status |
|---|---|
| Amex Blue Cash Everyday | Supported |

Support for additional Amex card types or other banks can be added by implementing a new parser in `src/parsers/` following the same `RawTransaction` interface.

---

## License

MIT
