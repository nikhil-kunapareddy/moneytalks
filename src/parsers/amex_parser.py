"""
Parser for American Express (Blue Cash Everyday) PDF statements.

Transaction layout in the PDF (text extracted with layout=True):
  MM/DD/YY[*]  DESCRIPTION [CITY STATE]  AMOUNT
               CATEGORY_HINT (optional, e.g. RESTAURANT)

Sections:
  "Payments and Credits" → payments and credits
  "New Charges"          → charges (anchored after P&C to skip Account Summary)
  "Total Fees"           → end of charges
"""

import re
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Optional

import pdfplumber

from src.parsers.base import RawTransaction

__all__ = ["AmexStatementParser", "RawTransaction"]


class AmexStatementParser:
    ACCOUNT = "Amex"
    _DATE_RE = re.compile(r"^(\d{2}/\d{2}/\d{2})\*?\s+")
    _AMOUNT_RE = re.compile(r"(-?\$?[\d,]+\.\d{2})\s*$")
    _CATEGORY_HINTS = frozenset({"RESTAURANT", "MERCHANDISE", "GROCERY", "TRAVEL", "GAS"})

    @classmethod
    def matches(cls, text: str) -> bool:
        lower = text.lower()
        return "americanexpress.com" in lower or "american express" in lower

    def parse(self, pdf_path: str) -> list[RawTransaction]:
        stmt_date = self._date_from_filename(Path(pdf_path).stem)
        text = self._extract_text(pdf_path)

        payments_credits = self._parse_payments_credits(text, stmt_date)
        charges = self._parse_charges(text, stmt_date)

        return payments_credits + charges

    # ------------------------------------------------------------------
    # Text extraction
    # ------------------------------------------------------------------

    def _extract_text(self, pdf_path: str) -> str:
        pages = []
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                # layout=True preserves column positions so amounts stay
                # on the same line as dates even in multi-column layouts.
                text = page.extract_text(layout=True)
                if text:
                    pages.append(text)
        return "\n".join(pages)

    def _date_from_filename(self, stem: str) -> Optional[date]:
        try:
            return datetime.strptime(stem, "%Y-%m-%d").date()
        except ValueError:
            return None

    # ------------------------------------------------------------------
    # Section slicing
    # ------------------------------------------------------------------

    def _parse_payments_credits(
        self, text: str, stmt_date: Optional[date]
    ) -> list[RawTransaction]:
        section = self._slice_section(text, "Payments and Credits", "New Charges")
        if not section:
            return []

        transactions = []
        for txn in self._parse_transactions(section, "payment", stmt_date):
            desc_upper = txn.description.upper()
            if (
                "CREDIT" in desc_upper
                or "REBATE" in desc_upper
                or "CASH BACK" in desc_upper
                or "OFFER" in desc_upper
            ):
                txn.transaction_type = "credit"
            transactions.append(txn)
        return transactions

    def _parse_charges(
        self, text: str, stmt_date: Optional[date]
    ) -> list[RawTransaction]:
        # "New Charges" also appears in the page 1 Account Summary
        # ("New Charges +$1,573.71"), so we anchor the search after
        # "Payments and Credits" which is unique to page 3.
        anchor = text.find("Payments and Credits")
        search_from = anchor if anchor != -1 else 0

        nc_idx = text.find("New Charges", search_from)
        if nc_idx == -1:
            return []

        # "Fees" also appears in the Account Summary ("Fees +$0.00").
        # "Total Fees" is unique to the actual Fees section on page 5.
        fees_idx = text.find("Total Fees", nc_idx)
        section = text[nc_idx:fees_idx] if fees_idx != -1 else text[nc_idx:]

        return self._parse_transactions(section, "charge", stmt_date)

    def _slice_section(self, text: str, start: str, end: str) -> Optional[str]:
        start_idx = text.find(start)
        if start_idx == -1:
            return None
        end_idx = text.find(end, start_idx + len(start))
        return text[start_idx:end_idx] if end_idx != -1 else text[start_idx:]

    # ------------------------------------------------------------------
    # Transaction parsing
    # ------------------------------------------------------------------

    def _parse_transactions(
        self, section: str, tx_type: str, stmt_date: Optional[date]
    ) -> list[RawTransaction]:
        blocks = self._split_into_blocks(section)
        results = []
        for block in blocks:
            txn = self._parse_block(block, tx_type, stmt_date)
            if txn:
                results.append(txn)
        return results

    def _split_into_blocks(self, text: str) -> list[list[str]]:
        """Group lines into blocks where each block starts with a date line."""
        blocks: list[list[str]] = []
        current: list[str] = []

        for line in text.split("\n"):
            if self._DATE_RE.match(line.strip()):
                if current:
                    blocks.append(current)
                current = [line.strip()]
            elif current and line.strip():
                current.append(line.strip())

        if current:
            blocks.append(current)

        return blocks

    def _parse_block(
        self, block: list[str], tx_type: str, stmt_date: Optional[date]
    ) -> Optional[RawTransaction]:
        if not block:
            return None

        first_line = block[0]
        date_match = self._DATE_RE.match(first_line)
        if not date_match:
            return None

        try:
            txn_date = datetime.strptime(date_match.group(1), "%m/%d/%y").date()
        except ValueError:
            return None

        # Amount: rightmost dollar value across all lines in the block.
        # We search the first line first (most common case with layout=True),
        # then fall back to subsequent lines.
        amount, amount_line_idx = self._find_amount(block)
        if amount is None:
            return None

        # Description: everything on the first line after the date,
        # up to (but not including) the amount if it's on that line.
        after_date = first_line[date_match.end():]
        if amount_line_idx == 0:
            amt_match = self._AMOUNT_RE.search(after_date)
            description = after_date[: amt_match.start()].strip() if amt_match else after_date.strip()
        else:
            description = after_date.strip()

        # Category hint: a subsequent line that is a known hint keyword.
        category_hint: Optional[str] = None
        for extra in block[1:]:
            if extra.strip().upper() in self._CATEGORY_HINTS:
                category_hint = extra.strip().upper()
                break

        return RawTransaction(
            date=txn_date,
            description=description,
            amount=abs(amount),
            transaction_type=tx_type,
            category_hint=category_hint,
            statement_closing_date=stmt_date,
            account=self.ACCOUNT,
        )

    def _find_amount(
        self, block: list[str]
    ) -> tuple[Optional[Decimal], int]:
        """Return (amount, line_index) for the first line that has an amount."""
        for i, line in enumerate(block):
            match = self._AMOUNT_RE.search(line)
            if match:
                raw = match.group(1).replace("$", "").replace(",", "")
                return Decimal(raw), i
        return None, -1
