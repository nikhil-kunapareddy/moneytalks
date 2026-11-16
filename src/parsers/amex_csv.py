"""Parser for the CSV export from americanexpress.com (Statements & Activity → Download).

Columns: Date (MM/DD/YYYY), Description, Amount — plus optional extras that
are ignored. Positive amounts are charges; negative ones are payments or credits.
"""

import csv
from datetime import datetime

from src.parsers.base import RawTransaction, classify_money_in, parse_amount

_REQUIRED_COLUMNS = frozenset({"Date", "Description", "Amount"})


class AmexCsvParser:
    ACCOUNT = "Amex"

    @classmethod
    def matches_header(cls, header: list[str]) -> bool:
        return _REQUIRED_COLUMNS <= {column.strip() for column in header}

    def parse(self, csv_path: str) -> list[RawTransaction]:
        transactions = []
        with open(csv_path, newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                amount = parse_amount(row["Amount"])
                if amount == 0:
                    continue
                # Keep internal spacing: clean_merchant() uses 2+ space gaps.
                description = row["Description"].strip()
                transactions.append(RawTransaction(
                    date=datetime.strptime(row["Date"].strip(), "%m/%d/%Y").date(),
                    description=description,
                    amount=abs(amount),
                    transaction_type="charge" if amount > 0 else classify_money_in(description),
                    account=self.ACCOUNT,
                ))
        return transactions
