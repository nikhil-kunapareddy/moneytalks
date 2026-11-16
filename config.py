"""
Application configuration.

``DATABASE_URL`` is read from the environment (via .env).
``CATEGORY_RULES`` maps category names to lists of keyword substrings;
keywords are matched case-insensitively against the raw transaction description.
"""

import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://localhost/moneytalks")

# Display-name overrides for merchants. If a keyword appears in the raw
# description (case-insensitive), the merchant is shown under that name.
# First match wins, so list more specific keywords first.
MERCHANT_ALIASES: dict[str, str] = {
    "AUDIBLE": "Audible",  # before AMZN: "Audible*... Amzn.com/bill"
    "AMAZON": "Amazon",
    "AMZN": "Amazon",
    "ALIEXPRESS": "AliExpress",
    "GOOGLE CLOUD": "Google Cloud",
    "GOOGLE *": "Google",
    "METAPAY": "Meta Pay",
    "SPOTHERO": "SpotHero",
    "DOLLARTREE": "Dollar Tree",
    "DOLLAR TREE": "Dollar Tree",
    "UBER EATS": "Uber Eats",
    "UBER *EATS": "Uber Eats",
    "UBER TRIP": "Uber",
    "LYFT": "Lyft",
    "COSTCO BY INSTACAR": "Costco via Instacart",
    "INSTACART": "Instacart",
    "AIRBNB": "Airbnb",
    "DOORDASH": "DoorDash",
    "MYPROTEIN": "Myprotein",
    "MBTA": "MBTA",
}

CATEGORY_RULES: dict[str, list[str]] = {
    "groceries": [
        "STAR OSCO", "STAR MARKET", "WOLLASTON", "COSTCO", "WHOLE FOODS",
        "TRADER JOE", "STOP & SHOP", "MARKET BASKET", "SHAW'S", "HANNAFORD",
        "ALDI", "ROCHE BROS", "PRICE RITE", "GROCER",
    ],
    "food_dining": [
        "UBER EATS", "UBER *EATS", "DOORDASH", "GRUBHUB", "TST*", "RESTAURANT", "RSTR",
        "CAFE", "COFFEE", "MCDONALD", "SUBWAY", "CHIPOTLE", "FUEL AMERICA",
        "DELAWARE NORTH", "F&B", "DINER", "BISTRO", "GRILL", "PIZZA",
        "STARBUCKS", "DUNKIN", "PANERA", "SWEETGREEN", "ISLAND FISH",
        "THE PIT", "VERSAILLES",
    ],
    "transportation": [
        "MBTA", "UBER TRIP", "LYFT", "DELTA", "AMERICAN AIRLINES",
        "UNITED AIRLINES", "SOUTHWEST", "JETBLUE", "AMTRAK", "BLUE BIKE",
        "SPOTHERO", "PARKING",
    ],
    "shopping": [
        "AMAZON", "TARGET", "WALMART", "BEST BUY", "ALIEXPRESS",
        "DOLLARTREE", "DOLLAR TREE",
    ],
    "travel": [
        "AIRBNB", "HOTEL", "MARRIOTT", "HILTON", "HYATT", "VIATOR",
        "EXPEDIA", "BOOKING.COM", "VRBO", "PRICELINE",
    ],
    "personal_care": [
        "SUPERCUTS", "GREAT CLIPS", "SALON", "SPA", "BARBER",
    ],
    "convenience": [
        "7-ELEVEN", "CVS", "WALGREENS", "RITE AID",
    ],
    "health_fitness": [
        "MYPROTEIN", "GNC", "VITAMIN", "PLANET FITNESS", "ANYTIME FITNESS",
        "PELOTON",
    ],
    "subscriptions": [
        "AUDIBLE", "GOOGLE CLOUD", "GOOGLE *", "NETFLIX", "SPOTIFY",
        "APPLE.COM/BILL", "YOUTUBE",
    ],
}
