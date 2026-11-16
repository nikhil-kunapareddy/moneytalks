"""Import statement files into the database."""

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from src.analysis.categorizer import categorize, clean_merchant
from src.db.repository import insert_transactions
from src.models.transaction import Transaction
from src.parsers import SUPPORTED_SUFFIXES, RawTransaction, detect_parser


@dataclass
class FileResult:
    name: str
    account: Optional[str] = None
    inserted: int = 0
    skipped: int = 0
    error: Optional[str] = None  # why the file wasn't imported


@dataclass
class ImportReport:
    files: list[FileResult] = field(default_factory=list)

    @property
    def inserted(self) -> int:
        return sum(f.inserted for f in self.files)

    @property
    def skipped(self) -> int:
        return sum(f.skipped for f in self.files)

    @property
    def problems(self) -> list[FileResult]:
        return [f for f in self.files if f.error]

    def summary(self) -> str:
        return (
            f"{self.inserted} imported, {self.skipped} skipped "
            f"from {len(self.files)} file(s)."
        )


def statement_files(paths: Iterable[Path]) -> list[Path]:
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


def import_files(
    session: Session, files: Iterable[Path], account: Optional[str] = None
) -> ImportReport:
    """Detect, parse and store each file. Already-stored transactions are skipped."""
    report = ImportReport()
    for path in files:
        result = FileResult(name=path.name)
        report.files.append(result)
        try:
            parser = detect_parser(path)
            if parser is None:
                result.error = "not a recognised statement"
                continue
            raw_txns = parser.parse(str(path))
        except Exception as exc:  # one bad file shouldn't stop the batch
            result.error = f"could not be read ({exc})"
            continue
        if not raw_txns:
            result.error = "no transactions found"
            continue

        transactions = to_models(raw_txns, account)
        result.account = transactions[0].account
        result.inserted, result.skipped = insert_transactions(session, transactions)
    return report


def to_models(raw_txns: list[RawTransaction], account: Optional[str] = None) -> list[Transaction]:
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
