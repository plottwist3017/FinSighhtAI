"""
expense_service.py
Parses, validates, categorises, and summarises expense CSV data.
"""

from __future__ import annotations

import io
from typing import Any

import pandas as pd

# ---------------------------------------------------------------------------
# Category keyword mapping
# ---------------------------------------------------------------------------
CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "Food": [
        "starbucks", "mcdonald", "subway", "chipotle", "dunkin", "doordash",
        "ubereats", "grubhub", "pizza", "burger", "cafe", "coffee", "restaurant",
        "dining", "food", "bakery", "sushi", "taco", "deli", "lunch", "dinner",
        "breakfast", "panera", "chick-fil-a", "wendy", "domino",
    ],
    "Transportation": [
        "uber", "lyft", "taxi", "gas", "shell", "bp", "chevron", "exxon",
        "transport", "parking", "metro", "transit", "train", "bus", "airline",
        "flight", "delta", "united", "american air", "spirit",
    ],
    "Shopping": [
        "amazon", "walmart", "target", "costco", "ebay", "etsy", "best buy",
        "ikea", "zara", "h&m", "gap", "nordstrom", "macy", "tj maxx", "marshalls",
        "shop", "store", "market", "mall",
    ],
    "Entertainment": [
        "netflix", "spotify", "hulu", "disney", "youtube", "twitch", "steam",
        "cinema", "movie", "theater", "concert", "ticket", "game", "amc",
        "playstation", "xbox", "apple tv",
    ],
    "Education": [
        "udemy", "coursera", "edx", "khan", "tuition", "school", "university",
        "college", "textbook", "course", "class", "learning", "book",
    ],
    "Bills": [
        "electric", "water", "internet", "cable", "phone", "verizon", "at&t",
        "t-mobile", "utility", "bill", "insurance", "rent", "mortgage", "comcast",
        "xfinity", "spectrum",
    ],
    "Healthcare": [
        "pharmacy", "cvs", "walgreens", "hospital", "clinic", "doctor", "dentist",
        "medical", "health", "prescription", "drug", "optician",
    ],
    "Travel": [
        "hotel", "airbnb", "booking", "expedia", "hilton", "marriott", "hyatt",
        "resort", "vrbo", "vacation", "trip", "travel", "cruise",
    ],
}


def categorise_row(merchant: str, description: str) -> str:
    text = f"{merchant} {description}".lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            return category
    return "Other"


# ---------------------------------------------------------------------------
# Main parsing entry point
# ---------------------------------------------------------------------------

def parse_expenses(file_bytes: bytes | str) -> tuple[pd.DataFrame, list[str]]:
    """
    Parse uploaded CSV bytes into a clean DataFrame.

    Returns (df, errors).  If critical errors exist df will be empty.
    """
    errors: list[str] = []

    try:
        if isinstance(file_bytes, bytes):
            df = pd.read_csv(io.BytesIO(file_bytes))
        else:
            df = pd.read_csv(io.StringIO(file_bytes))
    except Exception as exc:
        return pd.DataFrame(), [f"Could not parse CSV: {exc}"]

    # Normalise column names
    df.columns = [c.strip().title() for c in df.columns]

    required = {"Date", "Merchant", "Amount"}
    missing = required - set(df.columns)
    if missing:
        errors.append(f"Missing required columns: {', '.join(sorted(missing))}")
        return pd.DataFrame(), errors

    # Add Description if absent
    if "Description" not in df.columns:
        df["Description"] = ""

    df["Description"] = df["Description"].fillna("")
    df["Merchant"]    = df["Merchant"].fillna("Unknown")

    # Parse dates
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    invalid_dates = df["Date"].isna().sum()
    if invalid_dates:
        errors.append(f"{invalid_dates} row(s) had unparseable dates and were dropped.")
    df = df.dropna(subset=["Date"])

    # Parse amounts
    df["Amount"] = (
        df["Amount"]
        .astype(str)
        .str.replace(r"[^\d.\-]", "", regex=True)
    )
    df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce")
    invalid_amounts = df["Amount"].isna().sum()
    if invalid_amounts:
        errors.append(f"{invalid_amounts} row(s) had invalid amounts and were dropped.")
    df = df.dropna(subset=["Amount"])

    # Keep only positive transactions
    df = df[df["Amount"] > 0].copy()

    # Derived columns
    df["Category"]   = df.apply(lambda r: categorise_row(r["Merchant"], r["Description"]), axis=1)
    df["Month"]      = df["Date"].dt.to_period("M").astype(str)
    df["DayOfWeek"]  = df["Date"].dt.day_name()
    df["IsWeekend"]  = df["Date"].dt.dayofweek >= 5

    df = df.sort_values("Date").reset_index(drop=True)
    return df, errors


# ---------------------------------------------------------------------------
# Analytics helpers
# ---------------------------------------------------------------------------

def compute_summary(df: pd.DataFrame) -> dict[str, Any]:
    if df.empty:
        return {}

    total_spend    = df["Amount"].sum()
    total_txns     = len(df)
    avg_txn        = df["Amount"].mean()
    largest        = df.loc[df["Amount"].idxmax()]
    top_category   = df.groupby("Category")["Amount"].sum().idxmax()
    top_merchant   = df.groupby("Merchant")["Amount"].sum().idxmax()
    monthly        = df.groupby("Month")["Amount"].sum().reset_index()
    by_category    = df.groupby("Category")["Amount"].sum().reset_index().sort_values("Amount", ascending=False)
    by_merchant    = df.groupby("Merchant")["Amount"].sum().reset_index().sort_values("Amount", ascending=False).head(10)
    weekend_spend  = df[df["IsWeekend"]]["Amount"].sum()
    weekday_spend  = df[~df["IsWeekend"]]["Amount"].sum()

    return {
        "total_spend":    round(total_spend, 2),
        "total_txns":     total_txns,
        "avg_txn":        round(avg_txn, 2),
        "largest_txn":    {
            "amount":      round(float(largest["Amount"]), 2),
            "merchant":    largest["Merchant"],
            "date":        str(largest["Date"].date()),
        },
        "top_category":   top_category,
        "top_merchant":   top_merchant,
        "monthly":        monthly,
        "by_category":    by_category,
        "by_merchant":    by_merchant,
        "weekend_spend":  round(weekend_spend, 2),
        "weekday_spend":  round(weekday_spend, 2),
    }
