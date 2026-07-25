"""
ai_service.py
Calls an OpenAI-compatible LLM to generate financial intelligence.
Falls back to a rule-based summary when no API key is set.
"""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd
from utils.config import get_config

_log = logging.getLogger(__name__)


def _warn(exc: Exception) -> None:
    """Log an LLM error and let the caller fall through to the rule-based path."""
    _log.warning("LLM call failed (%s: %s) — using rule-based fallback.", type(exc).__name__, exc)


def _llm_available() -> bool:
    return bool(get_config("OPENAI_API_KEY"))


def _call_llm(system: str, user: str) -> str:
    from openai import OpenAI  # lazy import so app works without openai installed

    model = get_config("LLM_MODEL", "gpt-4o-mini")
    if not model:
        raise ValueError(
            "LLM_MODEL is not set. Add it to your .env or Streamlit secrets."
        )

    client = OpenAI(
        api_key=get_config("OPENAI_API_KEY"),
        base_url=get_config("OPENAI_BASE_URL", "https://api.openai.com/v1"),
    )
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
        temperature=0.7,
        max_tokens=900,
    )
    return response.choices[0].message.content.strip()


# ---------------------------------------------------------------------------
# Spending personality
# ---------------------------------------------------------------------------

def get_spending_personality(df: pd.DataFrame, summary: dict[str, Any]) -> str:
    if _llm_available():
        try:
            top_cats = (
                df.groupby("Category")["Amount"]
                .sum()
                .sort_values(ascending=False)
                .head(3)
                .to_dict()
            )
            user_msg = (
                f"Total spending: ${summary['total_spend']}. "
                f"Top categories: {top_cats}. "
                f"Weekend spend: ${summary['weekend_spend']}, "
                f"Weekday spend: ${summary['weekday_spend']}. "
                f"Average transaction: ${summary['avg_txn']}. "
                f"Total transactions: {summary['total_txns']}."
            )
            return _call_llm(
                system=(
                    "You are a concise financial analyst. "
                    "In 2–3 sentences, describe the user's spending personality "
                    "based on their expense data. Be direct and insightful."
                ),
                user=user_msg,
            )
        except Exception as exc:
            _warn(exc)

    # Rule-based fallback
    top_cat = summary.get("top_category", "various categories")
    if summary["weekend_spend"] > summary["weekday_spend"]:
        style = "weekend-heavy spender"
    elif summary["avg_txn"] > 50:
        style = "big-ticket purchaser"
    else:
        style = "frequent, small-purchase spender"
    return (
        f"You are a {style} with a strong focus on {top_cat}. "
        f"Your average transaction of ${summary['avg_txn']:.2f} across "
        f"{summary['total_txns']} purchases reflects a "
        f"{'spontaneous' if summary['total_txns'] > 30 else 'deliberate'} approach to spending."
    )


# ---------------------------------------------------------------------------
# Spending insights
# ---------------------------------------------------------------------------

def get_spending_insights(df: pd.DataFrame, summary: dict[str, Any]) -> list[str]:
    if _llm_available():
        try:
            monthly_data = summary["monthly"].to_dict(orient="records")
            cat_data = summary["by_category"].head(5).to_dict(orient="records")
            raw = _call_llm(
                system=(
                    "You are a financial analyst. Return exactly 4 bullet-point insights "
                    "about the user's spending. Each insight should be one sentence starting with '- '."
                ),
                user=(
                    f"Monthly data: {monthly_data}. "
                    f"Category breakdown: {cat_data}. "
                    f"Weekend vs weekday: ${summary['weekend_spend']} vs ${summary['weekday_spend']}."
                ),
            )
            return [line.strip()[2:].strip() for line in raw.splitlines() if line.strip().startswith("- ")]
        except Exception as exc:
            _warn(exc)

    # Rule-based fallback
    insights = []
    cat_data = summary["by_category"]
    top_cat_row = cat_data.iloc[0]
    pct = top_cat_row["Amount"] / summary["total_spend"] * 100
    insights.append(
        f"{top_cat_row['Category']} spending accounts for {pct:.0f}% of total expenses."
    )
    if summary["weekend_spend"] > summary["weekday_spend"] * 0.6:
        insights.append("Weekend spending is notably higher than weekdays.")
    else:
        insights.append("Spending is fairly distributed across the week.")
    if len(summary["monthly"]) > 1:
        vals = summary["monthly"]["Amount"].values
        change = (vals[-1] - vals[-2]) / vals[-2] * 100
        direction = "increased" if change > 0 else "decreased"
        insights.append(f"Month-over-month spending has {direction} by {abs(change):.0f}%.")
    insights.append(
        f"Your largest single expense was ${summary['largest_txn']['amount']:.2f} "
        f"at {summary['largest_txn']['merchant']}."
    )
    return insights


# ---------------------------------------------------------------------------
# Saving recommendations
# ---------------------------------------------------------------------------

def get_saving_recommendations(df: pd.DataFrame, summary: dict[str, Any]) -> list[str]:
    if _llm_available():
        try:
            cat_data = summary["by_category"].to_dict(orient="records")
            raw = _call_llm(
                system=(
                    "You are a personal finance coach. Return exactly 3 actionable saving "
                    "recommendations based on the spending data. "
                    "Each should be one sentence starting with '- '."
                ),
                user=f"Spending by category: {cat_data}. Total spend: ${summary['total_spend']}.",
            )
            return [line.strip()[2:].strip() for line in raw.splitlines() if line.strip().startswith("- ")]
        except Exception as exc:
            _warn(exc)

    # Rule-based fallback
    recs = []
    cat_data = summary["by_category"]
    top = cat_data.iloc[0]
    recs.append(
        f"Reducing {top['Category']} expenses by 15% could save "
        f"${top['Amount'] * 0.15:.0f} per month."
    )
    entertainment = cat_data[cat_data["Category"] == "Entertainment"]["Amount"]
    if not entertainment.empty and entertainment.values[0] > 30:
        recs.append("Review streaming subscriptions — consolidating services may reduce costs.")
    recs.append("Setting a weekly spending cap for your top category helps build saving habits.")
    return recs


# ---------------------------------------------------------------------------
# Goal planning
# ---------------------------------------------------------------------------

def get_goal_plan(goal: str, df: pd.DataFrame, summary: dict[str, Any]) -> str:
    if _llm_available():
        try:
            return _call_llm(
                system=(
                    "You are a practical financial planner. "
                    "Given the user's current spending data and their savings goal, "
                    "create a concise, realistic 3-step action plan (4–6 sentences total)."
                ),
                user=(
                    f"Savings goal: {goal}. "
                    f"Monthly spend: ${summary['total_spend']}. "
                    f"Top category: {summary['top_category']}. "
                    f"Category breakdown: {summary['by_category'].head(5).to_dict(orient='records')}."
                ),
            )
        except Exception as exc:
            _warn(exc)

    amount_str = "".join(c for c in goal if c.isdigit() or c == ".")
    target = float(amount_str) if amount_str else 500
    monthly_cut = target / 3
    top_cat = summary.get("top_category", "your top category")
    return (
        f"To reach your goal of {goal}, aim to cut ${monthly_cut:.0f}/month "
        f"from {top_cat} spending.\n\n"
        f"**Step 1:** Track daily {top_cat} expenses for one week to find quick wins.\n\n"
        f"**Step 2:** Set a monthly budget for your top 3 categories and review weekly.\n\n"
        f"**Step 3:** Move savings directly to a separate account at the start of each month."
    )


# ---------------------------------------------------------------------------
# Financial Memory Snapshot
# ---------------------------------------------------------------------------

def generate_memory_snapshot(
    df: pd.DataFrame,
    summary: dict[str, Any],
    personality: str,
    insights: list[str],
    recommendations: list[str],
    goal: str,
) -> str:
    month_label = df["Month"].mode()[0] if not df["Month"].mode().empty else "N/A"

    key_insight    = None
    recommendation = None

    if _llm_available():
        try:
            key_insight = _call_llm(
                system="Return a single impactful sentence summarising the user's biggest financial insight.",
                user=(
                    f"Top category: {summary['top_category']} "
                    f"({summary['by_category'].iloc[0]['Amount'] / summary['total_spend'] * 100:.0f}% of spend). "
                    f"Insights: {insights[:2]}."
                ),
            )
            recommendation = _call_llm(
                system="Return a single actionable recommendation sentence for this user.",
                user=f"Recommendations: {recommendations}. Top category: {summary['top_category']}.",
            )
        except Exception as exc:
            _warn(exc)
            key_insight    = None
            recommendation = None
    if not _llm_available() or key_insight is None:
        pct = summary["by_category"].iloc[0]["Amount"] / summary["total_spend"] * 100
        key_insight = (
            f"{summary['top_category']} expenses account for {pct:.0f}% of monthly spending."
        )
        recommendation = recommendations[0] if recommendations else "Review your top spending category."

    snapshot = f"""
--------------------------------------------------
         FINANCIAL MEMORY SNAPSHOT
--------------------------------------------------
Month:              {month_label}
Total Spending:     ${summary['total_spend']:,.2f}
Total Transactions: {summary['total_txns']}
Top Category:       {summary['top_category']}
Top Merchant:       {summary['top_merchant']}

Spending Personality:
{personality}

Key Insight:
{key_insight}

Recommendation:
{recommendation}

Savings Goal:
{goal if goal.strip() else 'No goal set.'}
--------------------------------------------------
""".strip()
    return snapshot
