"""Parsers for Citi, Chase and Bank of America credit-card PDF statements.

All three list activity as dated lines under section headings::

    Payments and Other Credits
    10/07 10/07 PAYMENT FROM CHK 0000 ...            -0.35
    Purchases and Adjustments
    11/01 11/02 Google CLOUD ...                       0.56

A line is ``MM/DD [MM/DD] DESCRIPTION AMOUNT``; the optional second date is the
posting date. The section heading decides what the amount means. Each bank
subclass only says how to recognise it, where the closing date and the card's
last four digits are printed, and how to tidy its descriptions.
"""

import re
from datetime import date
from typing import Optional

from src.parsers.base import (
    RawTransaction,
    classify_money_in,
    parse_amount,
    parse_us_date,
    pdf_text,
)

# Section heading (upper-cased, whole line) → what its rows are.
_SECTIONS: dict[str, str] = {
    "PAYMENTS, CREDITS AND ADJUSTMENTS": "money_in",
    "PAYMENTS AND OTHER CREDITS": "money_in",
    "PURCHASE": "purchase",
    "PURCHASES": "purchase",
    "STANDARD PURCHASES": "purchase",
    "PURCHASES AND ADJUSTMENTS": "purchase",
    "CASH ADVANCES": "purchase",
    "FEES CHARGED": "fee",
    "FEES": "fee",
    "INTEREST CHARGED": "fee",
}
# Headings that end the activity listing (APR tables, year-to-date totals).
_SECTION_ENDS = ("TOTALS YEAR-TO-DATE", "INTEREST CHARGE CALCULATION")
_SECTION_END_LINES = frozenset({"INTEREST CHARGES"})

_LINE_RE = re.compile(
    r"^(?P<date>\d{2}/\d{2})(?:\s+\d{2}/\d{2})?\s+(?P<desc>.+?)\s+(?P<amount>-?\$?[\d,]+\.\d{2})$"
)


class SectionedCardParser:
    BANK: str = ""
    DETECT: tuple[str, ...] = ()  # lower-case text that identifies the bank
    CLOSING_RE: re.Pattern
    LAST4_RE: re.Pattern

    @classmethod
    def matches(cls, text: str) -> bool:
        lower = text.lower()
        return any(marker in lower for marker in cls.DETECT)

    def parse(self, pdf_path: str) -> list[RawTransaction]:
        text = pdf_text(pdf_path)
        closing = self._closing_date(text)
        account = self._account(text)

        transactions = []
        section: Optional[str] = None
        for raw_line in text.splitlines():
            line = raw_line.strip()
            heading = line.upper()
            if heading in _SECTIONS:
                section = _SECTIONS[heading]
                continue
            if heading in _SECTION_END_LINES or any(end in heading for end in _SECTION_ENDS):
                section = None
                continue
            if section is None:
                continue

            match = _LINE_RE.match(line)
            if not match:
                continue
            amount = parse_amount(match["amount"])
            if amount == 0:
                continue  # e.g. "INTEREST CHARGED ON PURCHASES 0.00"

            description = self.clean_description(match["desc"])
            if amount < 0:
                tx_type = classify_money_in(description) if section == "money_in" else "credit"
            else:
                tx_type = "charge"

            transactions.append(RawTransaction(
                date=self._date_in_period(match["date"], closing),
                description=description,
                amount=abs(amount),
                transaction_type=tx_type,
                category_hint="FEES" if section == "fee" and tx_type == "charge" else None,
                statement_closing_date=closing,
                account=account,
            ))
        return transactions

    def clean_description(self, description: str) -> str:
        return description.strip()

    # ------------------------------------------------------------------

    def _closing_date(self, text: str) -> date:
        match = self.CLOSING_RE.search(text)
        if not match:
            raise ValueError(f"couldn't find the {self.BANK} statement closing date")
        return parse_us_date(match.group(1))

    def _account(self, text: str) -> str:
        match = self.LAST4_RE.search(text)
        return f"{self.BANK} ••{match.group(1)}" if match else self.BANK

    @staticmethod
    def _date_in_period(mm_dd: str, closing: date) -> date:
        """Statements print MM/DD only; a month after the closing month is last year."""
        month, day = (int(part) for part in mm_dd.split("/"))
        year = closing.year - 1 if month > closing.month else closing.year
        return date(year, month, day)


class CitiParser(SectionedCardParser):
    BANK = "Citi"
    DETECT = ("citi.com", "citi cards")
    CLOSING_RE = re.compile(r"Billing Period:\s*\d{2}/\d{2}/\d{2,4}\s*-\s*(\d{2}/\d{2}/\d{2,4})")
    LAST4_RE = re.compile(r"ending in:?\s*(\d{4})")


class ChaseParser(SectionedCardParser):
    BANK = "Chase"
    DETECT = ("chase.com",)
    CLOSING_RE = re.compile(r"Opening/Closing Date\s*\d{2}/\d{2}/\d{2,4}\s*-\s*(\d{2}/\d{2}/\d{2,4})")
    LAST4_RE = re.compile(r"Account Number:\s*(?:X{4}\s*){3}(\d{4})")


class BankOfAmericaParser(SectionedCardParser):
    BANK = "Bank of America"
    DETECT = ("bankofamerica.com",)
    CLOSING_RE = re.compile(r"Statement Closing Date\s*(\d{2}/\d{2}/\d{2,4})")
    LAST4_RE = re.compile(r"Account\s*#\s*(?:\d{4}\s*){3}(\d{4})")
    # Rows end with a reference number and the card's last four digits.
    _REF_AND_CARD = re.compile(r"\s+\d{4,}\s+\d{4}$")

    def clean_description(self, description: str) -> str:
        return self._REF_AND_CARD.sub("", description).strip()
