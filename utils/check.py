import sys
sys.path.insert(0, '.')

print("Testing imports...")
from services.expense_service import parse_expenses, compute_summary
print("  expense_service OK")
from services.ai_service import (
    get_spending_personality, get_spending_insights,
    get_saving_recommendations, get_goal_plan, generate_memory_snapshot,
)
print("  ai_service OK")
from blockchain.blockchain_service import (
    is_connected, hash_snapshot, get_wallet_address,
    save_snapshot_to_chain, get_on_chain_snapshots,
)
print("  blockchain_service OK (web3 optional)")

print("\nTesting CSV parse with sample data...")
with open("data/sample_expenses.csv", "rb") as f:
    raw = f.read()
df, errors = parse_expenses(raw)
print("  Parsed", len(df), "rows — errors:", errors)
summary = compute_summary(df)
print("  Total spend:", summary["total_spend"])
print("  Top category:", summary["top_category"])
print("  Top merchant:", summary["top_merchant"])

print("\nTesting rule-based AI (no API key)...")
personality = get_spending_personality(df, summary)
print("  Personality:", personality[:80])
insights = get_spending_insights(df, summary)
print("  Insights count:", len(insights), "| first:", insights[0][:60])
recs = get_saving_recommendations(df, summary)
print("  Recs count:", len(recs), "| first:", recs[0][:60])
snapshot = generate_memory_snapshot(df, summary, personality, insights, recs, "Save $300 in 2 months")
print("  Snapshot length:", len(snapshot), "chars")

print("\nTesting hash...")
h = hash_snapshot(snapshot)
print("  Hash (hex):", h.hex()[:20], "...")

print("\nALL CHECKS PASSED")
