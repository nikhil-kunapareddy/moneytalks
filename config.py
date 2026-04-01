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

CATEGORY_RULES: dict[str, list[str]] = {
    "groceries": [
        "STAR OSCO", "STAR MARKET", "WOLLASTON", "COSTCO", "WHOLE FOODS",
        "TRADER JOE", "STOP & SHOP", "MARKET BASKET", "SHAW'S", "HANNAFORD",
        "ALDI", "ROCHE BROS", "PRICE RITE",
    ],
    "food_dining": [
        "UBER EATS", "DOORDASH", "GRUBHUB", "TST*", "RESTAURANT", "RSTR",
        "CAFE", "COFFEE", "MCDONALD", "SUBWAY", "CHIPOTLE", "FUEL AMERICA",
        "DELAWARE NORTH", "F&B", "DINER", "BISTRO", "GRILL", "PIZZA",
        "STARBUCKS", "DUNKIN", "PANERA", "SWEETGREEN", "ISLAND FISH",
        "THE PIT", "VERSAILLES",
    ],
    "transportation": [
        "MBTA", "UBER TRIP", "LYFT", "DELTA", "AMERICAN AIRLINES",
        "UNITED AIRLINES", "SOUTHWEST", "JETBLUE", "AMTRAK", "BLUE BIKE",
    ],
    "shopping": [
        "AMAZON", "TARGET", "WALMART", "BEST BUY",
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
}
