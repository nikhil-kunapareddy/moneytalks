"""Types and helpers shared by all statement parsers."""

import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

import pdfplumber


@dataclass
class RawTransaction:
    date: date
    description: str
    amount: Decimal  # always positive; the direction is in transaction_type
    transaction_type: str  # "charge" | "payment" | "credit"
    category_hint: Optional[str] = None
    statement_closing_date: Optional[date] = None
    account: str = ""


_PAYMENT_WORDS = ("PAYMENT", "THANK YOU", "AUTOPAY")


def classify_money_in(description: str) -> str:
    """Money coming onto a card is either a bill payment or a credit/refund."""
    upper = description.upper()
    return "payment" if any(word in upper for word in _PAYMENT_WORDS) else "credit"


def parse_amount(raw: str) -> Decimal:
    """'$1,234.56', '-$41.00', '-0.35' → Decimal (signed)."""
    cleaned = raw.replace("$", "").replace(",", "").strip()
    negative = cleaned.startswith("-") or cleaned.endswith("-")
    value = Decimal(cleaned.strip("-"))
    return -value if negative else value


def parse_us_date(raw: str) -> date:
    """MM/DD/YY or MM/DD/YYYY."""
    fmt = "%m/%d/%Y" if re.fullmatch(r"\d{2}/\d{2}/\d{4}", raw) else "%m/%d/%y"
    return datetime.strptime(raw, fmt).date()


def pdf_text(path: str, max_pages: Optional[int] = None) -> str:
    """Plain text of a PDF.

    ``dedupe_chars()`` fixes statements that render bold text by drawing
    every glyph twice (Chase prints "MMaannaaggee" otherwise).
    """
    with pdfplumber.open(path) as pdf:
        pages = pdf.pages[:max_pages] if max_pages else pdf.pages
        return "\n".join(page.dedupe_chars().extract_text() or "" for page in pages)
