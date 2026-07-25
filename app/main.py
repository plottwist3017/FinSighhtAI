"""
FinSight AI — Main Streamlit Application
Built using IBM Bob · Made by Kavya Raval
"""

from __future__ import annotations

import sys
import os

# Make sure sibling packages resolve from repo root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import datetime

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from services.expense_service import parse_expenses, compute_summary
from services.ai_service import (
    get_spending_personality,
    get_spending_insights,
    get_saving_recommendations,
    get_goal_plan,
    generate_memory_snapshot,
)
from blockchain.blockchain_service import (
    is_connected,
    save_snapshot_to_chain,
    get_on_chain_snapshots,
    get_wallet_address,
    hash_snapshot,
)

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="FinSight AI",
    page_icon="💡",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ---------------------------------------------------------------------------
# Global CSS
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
    /* ── Hide Streamlit chrome ── */
    #MainMenu { visibility:hidden; }
    footer     { visibility:hidden; }
    [data-testid="stSidebar"] { display:none; }
    [data-testid="collapsedControl"] { display:none; }

    /* ── Hero banner ── */
    .hero {
        background: linear-gradient(135deg, #0f172a 0%, #1e3a5f 60%, #2d1b69 100%);
        border-radius: 20px;
        padding: 52px 48px 44px;
        text-align: center;
        margin-bottom: 8px;
        position: relative;
        overflow: hidden;
    }
    .hero-eyebrow {
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 0.18em;
        text-transform: uppercase;
        color: #7dd3fc;
        margin-bottom: 14px;
    }
    .hero-title {
        font-size: 48px;
        font-weight: 800;
        color: #ffffff;
        line-height: 1.1;
        margin-bottom: 10px;
        letter-spacing: -0.02em;
    }
    .hero-title span { color: #818cf8; }
    .hero-subtitle {
        font-size: 17px;
        color: #94a3b8;
        max-width: 520px;
        margin: 0 auto 28px;
        line-height: 1.6;
    }
    .hero-pills {
        display: flex;
        justify-content: center;
        gap: 10px;
        flex-wrap: wrap;
        margin-bottom: 4px;
    }
    .hero-pill {
        background: rgba(255,255,255,0.08);
        border: 1px solid rgba(255,255,255,0.15);
        border-radius: 20px;
        padding: 5px 14px;
        font-size: 12px;
        color: #cbd5e1;
    }
    .hero-badge {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        background: rgba(99,102,241,0.2);
        border: 1px solid rgba(99,102,241,0.4);
        border-radius: 20px;
        padding: 4px 12px;
        font-size: 11px;
        color: #a5b4fc;
        margin-top: 18px;
    }

    /* ── Nav tab bar ── */
    .nav-bar {
        display: flex;
        gap: 8px;
        background: #f7f8fa;
        border: 1px solid #e5e7eb;
        border-radius: 14px;
        padding: 6px;
        margin: 18px 0 28px;
    }
    .nav-btn {
        flex: 1;
        text-align: center;
        padding: 10px 8px;
        border-radius: 10px;
        font-size: 14px;
        font-weight: 600;
        color: #64748b;
        cursor: pointer;
        border: none;
        background: transparent;
        transition: background 0.15s;
    }
    .nav-btn.active {
        background: #ffffff;
        color: #1e293b;
        box-shadow: 0 1px 4px rgba(0,0,0,0.10);
    }

    /* ── KPI cards ── */
    .kpi-card {
        background:#f8fafc;
        border:1px solid #e2e8f0;
        border-radius:12px;
        padding:20px 24px;
        text-align:center;
    }
    .kpi-label { font-size:13px; color:#64748b; margin-bottom:4px; }
    .kpi-value { font-size:28px; font-weight:700; color:#1e293b; }

    /* ── Snapshot box ── */
    .snapshot-box {
        background:#f8fafc;
        border:1px solid #e2e8f0;
        border-radius:12px;
        padding:24px 28px;
        font-family:monospace;
        white-space:pre-wrap;
        font-size:14px;
        color:#1e293b;
    }

    /* ── Success box ── */
    .success-box {
        background:#f0fdf4;
        border:1px solid #bbf7d0;
        border-radius:10px;
        padding:18px 22px;
        color:#14532d;
    }

    /* ── Insight bullet ── */
    .insight-item {
        padding:10px 16px;
        background:#f1f5f9;
        border-left:3px solid #6366f1;
        border-radius:6px;
        margin-bottom:8px;
        font-size:14px;
        color:#1e293b;
    }

    /* ── Blockchain status chip ── */
    .chain-status {
        display:inline-flex;
        align-items:center;
        gap:6px;
        background:#f1f5f9;
        border:1px solid #e2e8f0;
        border-radius:20px;
        padding:4px 12px;
        font-size:12px;
        color:#475569;
        margin-bottom:20px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Session state helpers
# ---------------------------------------------------------------------------
def _init_state() -> None:
    defaults = {
        "df":           None,
        "summary":      None,
        "personality":  None,
        "insights":     None,
        "recs":         None,
        "goal_plan":    None,
        "goal_text":    "",
        "snapshot":     None,
        "tx_result":    None,
        "parse_errors": [],
        "chain_snaps":  None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


_init_state()


# ---------------------------------------------------------------------------
# Hero intro
# ---------------------------------------------------------------------------
connected = is_connected()
chain_dot  = "🟢" if connected else "🔴"
chain_text = "Monad Testnet · Connected" if connected else "Monad Testnet · Offline"

st.markdown(
    f"""
    <div class="hero">
        <div class="hero-eyebrow">Powered by AI · Built on Monad</div>
        <div class="hero-title">Fin<span>Sight</span> AI</div>
        <div class="hero-subtitle">
            An AI-Powered Financial Intelligence Platform
        </div>
        <div class="hero-pills">
            <span class="hero-pill">📊 Smart Analytics</span>
            <span class="hero-pill">🤖 AI Insights</span>
            <span class="hero-pill">🔗 Monad Blockchain</span>
            <span class="hero-pill">🎯 Goal Planning</span>
        </div>
        <div><span class="hero-badge">{chain_dot} {chain_text}</span></div>
        <div style="margin-top:10px;font-size:11px;color:#64748b;">Built using IBM Bob · Made by Kavya Raval</div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Horizontal nav tab bar (uses Streamlit buttons to set session state)
# ---------------------------------------------------------------------------
PAGES = ["📤 Upload", "📊 Dashboard", "🤖 AI Insights", "🔗 Financial Memory"]

if "page" not in st.session_state:
    st.session_state["page"] = PAGES[0]

col1, col2, col3, col4 = st.columns(4)
for col, label in zip([col1, col2, col3, col4], PAGES):
    with col:
        active = st.session_state["page"] == label
        if st.button(
            label,
            key=f"nav_{label}",
            use_container_width=True,
            type="primary" if active else "secondary",
        ):
            st.session_state["page"] = label
            st.rerun()

page = st.session_state["page"]
st.markdown("---")


# ===========================================================================
# PAGE 1 — UPLOAD
# ===========================================================================
if page == "📤 Upload":
    st.markdown("# 📤 Upload Expenses")
    st.markdown("Upload a CSV file to begin your financial analysis.")

    st.markdown(
        """
        **Expected columns:** `Date`, `Merchant`, `Amount`, `Description` *(optional)*

        ```
        Date,Merchant,Amount,Description
        2026-07-01,Starbucks,6.50,Coffee
        2026-07-02,Uber,18.00,Ride
        2026-07-05,Walmart,54.00,Groceries
        ```
        """
    )

    uploaded = st.file_uploader(
        "Drag & drop your expense CSV here",
        type=["csv"],
        help="CSV with Date, Merchant, Amount columns.",
    )

    # Sample CSV download
    sample = (
        "Date,Merchant,Amount,Description\n"
        "2026-07-01,Starbucks,6.50,Coffee\n"
        "2026-07-02,Uber,18.00,Ride\n"
        "2026-07-03,Walmart,54.00,Groceries\n"
        "2026-07-04,Netflix,15.99,Subscription\n"
        "2026-07-05,Chipotle,12.75,Lunch\n"
        "2026-07-06,Shell,48.00,Gas\n"
        "2026-07-07,Amazon,89.99,Electronics\n"
        "2026-07-08,Starbucks,7.25,Latte\n"
        "2026-07-09,Lyft,22.50,Ride\n"
        "2026-07-10,Target,67.30,Household\n"
        "2026-07-11,CVS,14.99,Medicine\n"
        "2026-07-12,Spotify,9.99,Subscription\n"
        "2026-07-13,Chipotle,11.50,Dinner\n"
        "2026-07-14,Uber,31.00,Airport ride\n"
        "2026-07-15,Hilton,189.00,Hotel stay\n"
        "2026-07-16,Starbucks,5.75,Espresso\n"
        "2026-07-17,Whole Foods,72.40,Groceries\n"
        "2026-07-18,AMC,24.00,Movie tickets\n"
        "2026-07-19,Coursera,49.00,Online course\n"
        "2026-07-20,Uber Eats,35.20,Dinner delivery\n"
        "2026-07-21,Walmart,43.60,Household\n"
        "2026-07-22,Shell,52.00,Gas\n"
        "2026-07-23,Starbucks,6.00,Cold brew\n"
        "2026-07-24,Amazon,124.00,Clothing\n"
        "2026-07-25,Chipotle,13.25,Burrito bowl\n"
    )
    st.download_button(
        "⬇️ Download sample CSV",
        data=sample,
        file_name="sample_expenses.csv",
        mime="text/csv",
    )

    if uploaded:
        with st.spinner("Parsing your expenses…"):
            raw = uploaded.read()
            df, errors = parse_expenses(raw)

        if errors:
            for err in errors:
                st.warning(err)

        if df.empty:
            st.error("No valid transactions found. Please check your CSV format.")
        else:
            summary = compute_summary(df)
            st.session_state["df"]      = df
            st.session_state["summary"] = summary
            st.session_state["parse_errors"] = errors
            # Reset downstream state
            for k in ("personality", "insights", "recs", "goal_plan", "snapshot", "tx_result"):
                st.session_state[k] = None

            st.success(f"✅ Loaded **{len(df)}** transactions. Navigate to **Dashboard** to continue.")
            st.dataframe(df[["Date","Merchant","Amount","Category","Description"]].head(15), use_container_width=True)


# ===========================================================================
# PAGE 2 — DASHBOARD
# ===========================================================================
elif page == "📊 Dashboard":
    st.markdown("# 📊 Expense Dashboard")

    if st.session_state["df"] is None:
        st.info("Upload a CSV first from the **Upload** page.")
        st.stop()

    df: pd.DataFrame = st.session_state["df"]
    summary = st.session_state["summary"]

    # KPI row
    c1, c2, c3, c4 = st.columns(4)
    kpis = [
        (c1, "Total Spending",      f"${summary['total_spend']:,.2f}"),
        (c2, "Transactions",        str(summary["total_txns"])),
        (c3, "Avg Transaction",     f"${summary['avg_txn']:,.2f}"),
        (c4, "Largest Expense",     f"${summary['largest_txn']['amount']:,.2f}"),
    ]
    for col, label, value in kpis:
        with col:
            st.markdown(
                f'<div class="kpi-card"><div class="kpi-label">{label}</div>'
                f'<div class="kpi-value">{value}</div></div>',
                unsafe_allow_html=True,
            )

    st.markdown("<br>", unsafe_allow_html=True)

    # Charts row 1
    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown("#### Spending by Category")
        fig_cat = px.pie(
            summary["by_category"],
            names="Category",
            values="Amount",
            hole=0.4,
            color_discrete_sequence=px.colors.qualitative.Set3,
        )
        fig_cat.update_layout(showlegend=True, margin=dict(t=20, b=20))
        st.plotly_chart(fig_cat, use_container_width=True)

    with col_b:
        st.markdown("#### Top 10 Merchants")
        fig_merch = px.bar(
            summary["by_merchant"].sort_values("Amount"),
            x="Amount",
            y="Merchant",
            orientation="h",
            color="Amount",
            color_continuous_scale="Blues",
        )
        fig_merch.update_layout(showlegend=False, margin=dict(t=20, b=20))
        st.plotly_chart(fig_merch, use_container_width=True)

    # Charts row 2
    col_c, col_d = st.columns(2)

    with col_c:
        st.markdown("#### Monthly Spending Trend")
        fig_month = px.bar(
            summary["monthly"],
            x="Month",
            y="Amount",
            color="Amount",
            color_continuous_scale="Purples",
            text_auto=".2s",
        )
        fig_month.update_layout(showlegend=False, margin=dict(t=20, b=20))
        st.plotly_chart(fig_month, use_container_width=True)

    with col_d:
        st.markdown("#### Weekend vs Weekday Spending")
        fig_ww = go.Figure(
            go.Bar(
                x=["Weekday", "Weekend"],
                y=[summary["weekday_spend"], summary["weekend_spend"]],
                marker_color=["#6366f1", "#f59e0b"],
                text=[f"${summary['weekday_spend']:,.0f}", f"${summary['weekend_spend']:,.0f}"],
                textposition="auto",
            )
        )
        fig_ww.update_layout(margin=dict(t=20, b=20))
        st.plotly_chart(fig_ww, use_container_width=True)

    # Daily spend scatter
    st.markdown("#### Daily Spending Pattern")
    fig_daily = px.scatter(
        df,
        x="Date",
        y="Amount",
        color="Category",
        size="Amount",
        hover_data=["Merchant", "Description"],
        color_discrete_sequence=px.colors.qualitative.Set2,
    )
    fig_daily.update_layout(margin=dict(t=20, b=20))
    st.plotly_chart(fig_daily, use_container_width=True)


# ===========================================================================
# PAGE 3 — AI INSIGHTS
# ===========================================================================
elif page == "🤖 AI Insights":
    st.markdown("# 🤖 AI Financial Insights")

    if st.session_state["df"] is None:
        st.info("Upload a CSV first from the **Upload** page.")
        st.stop()

    df      = st.session_state["df"]
    summary = st.session_state["summary"]

    if st.button("✨ Generate AI Insights", type="primary", use_container_width=True):
        with st.spinner("Analysing your spending patterns…"):
            personality = get_spending_personality(df, summary)
            insights    = get_spending_insights(df, summary)
            recs        = get_saving_recommendations(df, summary)

        st.session_state["personality"] = personality
        st.session_state["insights"]    = insights
        st.session_state["recs"]        = recs

    personality = st.session_state.get("personality")
    insights    = st.session_state.get("insights")
    recs        = st.session_state.get("recs")

    if personality:
        st.markdown("### 🧬 Spending Personality")
        st.info(personality)

    if insights:
        st.markdown("### 💡 Spending Insights")
        for item in insights:
            st.markdown(
                f'<div class="insight-item">• {item}</div>',
                unsafe_allow_html=True,
            )

    if recs:
        st.markdown("### 💰 Saving Recommendations")
        for item in recs:
            st.markdown(
                f'<div class="insight-item" style="border-left-color:#10b981;">• {item}</div>',
                unsafe_allow_html=True,
            )

    # Goal planner
    st.markdown("---")
    st.markdown("### 🎯 Goal Planner")
    goal_input = st.text_input(
        "Enter your savings goal",
        placeholder='e.g. "I want to save $500 in 3 months"',
        value=st.session_state.get("goal_text", ""),
    )
    st.session_state["goal_text"] = goal_input

    if st.button("📋 Generate Action Plan", use_container_width=True) and goal_input.strip():
        with st.spinner("Building your personalised plan…"):
            plan = get_goal_plan(goal_input, df, summary)
        st.session_state["goal_plan"] = plan

    if st.session_state.get("goal_plan"):
        st.markdown("#### Your Action Plan")
        st.markdown(st.session_state["goal_plan"])


# ===========================================================================
# PAGE 4 — FINANCIAL MEMORY
# ===========================================================================
elif page == "🔗 Financial Memory":
    st.markdown("# 🔗 Financial Memory")
    st.markdown("Generate an immutable snapshot of your financial journey and save it to the Monad Testnet.")

    if st.session_state["df"] is None:
        st.info("Upload a CSV first from the **Upload** page.")
        st.stop()

    df      = st.session_state["df"]
    summary = st.session_state["summary"]

    # Ensure AI insights exist (generate silently if missing)
    if not st.session_state.get("personality"):
        with st.spinner("Running AI analysis…"):
            st.session_state["personality"] = get_spending_personality(df, summary)
            st.session_state["insights"]    = get_spending_insights(df, summary)
            st.session_state["recs"]        = get_saving_recommendations(df, summary)

    goal_text = st.session_state.get("goal_text", "No goal set.")

    # Generate snapshot
    if st.button("🧠 Generate Financial Memory", type="primary", use_container_width=True):
        with st.spinner("Crafting your Financial Memory Snapshot…"):
            snapshot = generate_memory_snapshot(
                df,
                summary,
                st.session_state["personality"],
                st.session_state["insights"] or [],
                st.session_state["recs"] or [],
                goal_text,
            )
        st.session_state["snapshot"] = snapshot
        st.session_state["tx_result"] = None

    snapshot = st.session_state.get("snapshot")

    if snapshot:
        st.markdown("### 📄 Your Financial Memory Snapshot")
        st.markdown(
            f'<div class="snapshot-box">{snapshot}</div>',
            unsafe_allow_html=True,
        )

        # Download snapshot
        st.download_button(
            "⬇️ Save Snapshot (.txt)",
            data=snapshot,
            file_name="financial_memory.txt",
            mime="text/plain",
        )

        st.markdown("---")
        st.markdown("### 🔗 Save to Monad Testnet")

        month_label = df["Month"].mode()[0] if not df["Month"].mode().empty else "Unknown"

        # Show hash preview
        snap_hash = "0x" + hash_snapshot(snapshot).hex()
        st.markdown(f"**SHA-256 Hash:** `{snap_hash[:20]}…`")
        st.caption("Only this hash (not your financial data) is stored on-chain.")

        col_save, col_check = st.columns([1, 1])

        with col_save:
            if st.button("⛓️ Save to Monad", type="primary", use_container_width=True):
                if not is_connected():
                    st.error("❌ Cannot connect to Monad Testnet. Check your RPC URL.")
                else:
                    wallet = get_wallet_address()
                    if not wallet:
                        st.error("❌ WALLET_ADDRESS not configured in .env")
                    else:
                        with st.spinner("Sending transaction to Monad Testnet…"):
                            try:
                                result = save_snapshot_to_chain(snapshot, month_label)
                                st.session_state["tx_result"] = result
                            except Exception as exc:
                                st.session_state["tx_result"] = {"error": str(exc)}

        with col_check:
            if st.button("🔍 View My Timeline", use_container_width=True):
                snaps = get_on_chain_snapshots()
                if snaps:
                    st.session_state["chain_snaps"] = snaps
                else:
                    st.info("No snapshots found on-chain for this wallet yet.")

        # Transaction result
        tx = st.session_state.get("tx_result")
        if tx:
            if "error" in tx:
                st.error(f"❌ Transaction failed: {tx['error']}")
            elif tx.get("status") == 1:
                st.markdown(
                    f"""
                    <div class="success-box">
                    ✅ <strong>Financial Memory stored successfully.</strong><br><br>
                    <b>Transaction Hash:</b><br>
                    <code>{tx['tx_hash']}</code><br><br>
                    <b>Block:</b> {tx['block_number']}<br>
                    <b>Snapshot Hash:</b> <code>{tx['snapshot_hash_hex'][:20]}…</code>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                monad_explorer = f"https://testnet.monadexplorer.com/tx/{tx['tx_hash']}"
                st.markdown(f"[🔗 View on Monad Explorer]({monad_explorer})")
            else:
                st.warning("Transaction submitted but reverted. Check contract address and wallet balance.")

        # Timeline
        chain_snaps = st.session_state.get("chain_snaps")
        if chain_snaps:
            st.markdown("---")
            st.markdown("### 📅 On-Chain Memory Timeline")
            for snap in reversed(chain_snaps):
                ts = datetime.datetime.fromtimestamp(snap["timestamp"]).strftime("%Y-%m-%d %H:%M")
                short_hash = snap["hash"][:20] + "…" if len(snap["hash"]) > 20 else snap["hash"]
                st.markdown(
                    f'<div class="insight-item">'
                    f'<b>{snap["month"]}</b> &nbsp;·&nbsp; {ts} &nbsp;·&nbsp; '
                    f'<code>{short_hash}</code></div>',
                    unsafe_allow_html=True,
                )
