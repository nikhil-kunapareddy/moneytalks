"""Statement parsers and automatic bank detection."""

import csv
import re
from pathlib import Path
from typing import Optional, Protocol

from src.parsers.amex_csv import AmexCsvParser
from src.parsers.amex_parser import AmexStatementParser
from src.parsers.base import RawTransaction, pdf_text
from src.parsers.card_pdf import BankOfAmericaParser, ChaseParser, CitiParser

SUPPORTED_SUFFIXES = (".pdf", ".csv")

# Checked in order; bank-specific web addresses come before the looser Amex check.
_PDF_PARSERS = (CitiParser, ChaseParser, BankOfAmericaParser, AmexStatementParser)


class StatementParser(Protocol):
    def parse(self, path: str) -> list[RawTransaction]: ...


def detect_parser(path: Path) -> Optional[StatementParser]:
    """Pick the parser for a statement file, or None if it isn't recognised."""
    suffix = path.suffix.lower()
    if suffix == ".csv":
        with open(path, newline="", encoding="utf-8-sig") as f:
            header = next(csv.reader(f), [])
        return AmexCsvParser() if AmexCsvParser.matches_header(header) else None

    if suffix == ".pdf":
        text = pdf_text(str(path), max_pages=2)
        for parser_cls in _PDF_PARSERS:
            if parser_cls.matches(text):
                return parser_cls()
        # Original convention in this repo: Amex statements saved as YYYY-MM-DD.pdf
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", path.stem):
            return AmexStatementParser()
    return None


__all__ = [
    "SUPPORTED_SUFFIXES",
    "RawTransaction",
    "StatementParser",
    "detect_parser",
]
