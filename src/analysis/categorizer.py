"""
Rule-based transaction categorisation and merchant name cleaning.

Categorisation priority:
  1. PDF-embedded hint (e.g. "RESTAURANT", "MERCHANDISE")
  2. Keyword match against CATEGORY_RULES in config.py
  3. "uncategorized" fallback
"""

import re
from typing import Optional

from config import CATEGORY_RULES, MERCHANT_ALIASES

# Prefixes injected by Apple Pay or payment intermediaries. They can be
# chained, e.g. "AplPay TST* FUEL AMERICA".
_STRIP_PREFIXES: tuple[str, ...] = ("AplPay ", "IC* ", "TST*", "SQ *")

# Opaque IDs used in place of a merchant name (UUID-like).
_HEX_ID = re.compile(r"^[0-9A-F]{8}-[0-9A-F]{4}-", re.I)
# Reference codes after an asterisk: "AIRBNB * HMKC9SRB2A", "VIATOR *IT-175...".
_REFERENCE = re.compile(r"\s*\*.*$")
# Numeric codes glued to the name: "MBTA-550013128487".
_CODE_SUFFIX = re.compile(r"-\d{4,}\b")
_VOWEL = re.compile(r"[AEIOUY]", re.I)

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
    "FEES": "fees",  # fee / interest sections of Citi, Chase, BofA statements
}


def clean_merchant(description: str) -> str:
    """Return a human-readable merchant name from a raw PDF description.

    pdfplumber's ``layout=True`` mode uses runs of 2+ spaces as column
    separators.  The merchant name is always the first (leftmost) column,
    so we truncate at the first such gap before stripping trailing noise.

    Examples::

        "AplPay UBER EATS         HTTPS://HELP.UBER.COM CA" → "Uber Eats"
        "AplPay STAR OSCO 3588 3588 BOSTON       MA"        → "Star Osco"
        "AplPay MBTA-550013128487 LOCID1 BOSTON  MA"        → "MBTA"
        "AplPay 7-ELEVEN 37526 00073752601 BOSTON MA"       → "7-Eleven"
        "AMAZON MARKETPLACE NA PA AMZN.COM/BILL WA"         → "Amazon"
    """
    upper = description.upper()
    for keyword, alias in MERCHANT_ALIASES.items():
        if keyword.upper() in upper:
            return alias

    name = description.strip()

    # 1. Remove payment-intermediary prefixes (possibly chained).
    stripped = True
    while stripped:
        stripped = False
        for prefix in _STRIP_PREFIXES:
            if name.startswith(prefix):
                name = name[len(prefix):].lstrip()
                stripped = True

    if _HEX_ID.match(name):
        return "Unknown merchant"

    # 2. Truncate at the first column-separator gap (2+ consecutive spaces).
    #    This cleanly removes city, state, URL, and phone columns in one step
    #    for merchants whose name has no internal multi-space padding.
    name = re.split(r"\s{2,}", name)[0]

    # 3. Drop reference codes and strip trailing noise (state codes, URLs, codes).
    name = _CODE_SUFFIX.sub("", _REFERENCE.sub("", name))
    for pattern in _TRAILING_PATTERNS:
        name = pattern.sub("", name)

    # 4. Store numbers are followed by the city ("STAR OSCO 3588 BOSTON"),
    #    so cut at the first word after the first that contains a digit.
    words = name.split()
    for i, word in enumerate(words[1:], start=1):
        if any(ch.isdigit() for ch in word):
            words = words[:i]
            break

    return _title_case(" ".join(words)) or description.strip()


def _title_case(name: str) -> str:
    """Title-case ALL-CAPS words; keep mixed-case words and vowel-less acronyms (F&B)."""
    words = []
    for word in name.split():
        if word.isupper() and _VOWEL.search(word):
            words.append("-".join(p[:1].upper() + p[1:].lower() for p in word.split("-")))
        else:
            words.append(word)
    return " ".join(words)


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
