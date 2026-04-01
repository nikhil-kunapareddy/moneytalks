"""
Rule-based transaction categorisation and merchant name cleaning.

Categorisation priority:
  1. PDF-embedded hint (e.g. "RESTAURANT", "MERCHANDISE")
  2. Keyword match against CATEGORY_RULES in config.py
  3. "uncategorized" fallback
"""

import re
from typing import Optional

from config import CATEGORY_RULES

# Prefixes injected by Apple Pay or payment intermediaries.
_STRIP_PREFIXES: tuple[str, ...] = ("AplPay ", "IC* ", "TST* ")

# Applied sequentially after prefix removal to strip trailing noise.
# Order matters: state code must be removed before URL so that
# "AMZN.COM/BILL WA" becomes "AMZN.COM/BILL" → then the URL is removed.
_TRAILING_PATTERNS: tuple[re.Pattern, ...] = (
    re.compile(r"\s+\d{3}[-.\s]\d{3}[-.\s]\d{4}$"),  # phone:  617-782-0453
    re.compile(r"\s+[A-Z]{2}$"),                        # state:  MA, CA, NY
    re.compile(r"\s+\S+\.(com|org|net)\S*$", re.I),    # URL:    AMZN.COM/BILL
    re.compile(r"\s+\d{4,}$"),                           # codes:  store / order numbers
)

# PDF-embedded category hints → internal category names.
_HINT_MAP: dict[str, str] = {
    "RESTAURANT": "food_dining",
    "MERCHANDISE": "shopping",
    "GROCERY": "groceries",
    "TRAVEL": "travel",
    "GAS": "transportation",
}


def clean_merchant(description: str) -> str:
    """Return a human-readable merchant name from a raw PDF description.

    pdfplumber's ``layout=True`` mode uses runs of 2+ spaces as column
    separators.  The merchant name is always the first (leftmost) column,
    so we truncate at the first such gap before stripping trailing noise.

    Examples::

        "AplPay UBER EATS         HTTPS://HELP.UBER.COM CA" → "UBER EATS"
        "IC* COSTCO BY INSTACAR   SAN FRANCISCO  CA"        → "COSTCO BY INSTACAR"
        "AMAZON MARKETPLACE NA PA AMZN.COM/BILL WA"         → "AMAZON MARKETPLACE NA PA"
    """
    name = description

    # 1. Remove payment-intermediary prefix.
    for prefix in _STRIP_PREFIXES:
        if name.startswith(prefix):
            name = name[len(prefix):]
            break

    # 2. Truncate at the first column-separator gap (2+ consecutive spaces).
    #    This cleanly removes city, state, URL, and phone columns in one step
    #    for merchants whose name has no internal multi-space padding.
    name = re.split(r"\s{2,}", name)[0]

    # 3. Strip any remaining trailing noise (state codes, URLs, numeric codes).
    for pattern in _TRAILING_PATTERNS:
        name = pattern.sub("", name)

    return name.strip()


def categorize(description: str, category_hint: Optional[str] = None) -> str:
    """Return the category for a transaction.

    Args:
        description: Raw merchant description from the PDF.
        category_hint: Optional hint extracted from the statement
            (e.g. "RESTAURANT"). Takes priority over keyword rules.

    Returns:
        Category string (e.g. "food_dining") or "uncategorized".
    """
    if category_hint and category_hint in _HINT_MAP:
        return _HINT_MAP[category_hint]

    desc_upper = description.upper()
    for category, keywords in CATEGORY_RULES.items():
        for keyword in keywords:
            if keyword.upper() in desc_upper:
                return category

    return "uncategorized"
