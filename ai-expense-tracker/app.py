import hashlib

import pandas as pd
import streamlit as st

from doc_processing import analyze_invoices, clear_cache, process_invoices
from model_gateway import invoke_llm

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="AI Expense Tracker",
    page_icon="🏛️",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Custom CSS
# ---------------------------------------------------------------------------

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    .stApp {
        background-color: #F1F5F9;
    }

    .card {
        background: #ffffff;
        border-radius: 12px;
        border: 1px solid #E2E8F0;
        box-shadow: 0 1px 4px rgba(0,0,0,0.06);
        padding: 1.25rem 1.5rem;
        margin-bottom: 1rem;
    }

    .metric-card {
        background: #ffffff;
        border-radius: 12px;
        border: 1px solid #E2E8F0;
        box-shadow: 0 1px 4px rgba(0,0,0,0.06);
        padding: 1rem 1.5rem;
        text-align: center;
    }

    .metric-label {
        font-size: 0.78rem;
        font-weight: 600;
        color: #64748B;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 0.25rem;
    }

    .metric-value {
        font-size: 1.75rem;
        font-weight: 700;
        color: #0F172A;
    }

    .hero-banner {
        background: linear-gradient(135deg, #0F172A 0%, #1D4ED8 100%);
        border-radius: 16px;
        padding: 2.5rem 2.5rem;
        margin-bottom: 1.75rem;
        color: #ffffff;
    }

    .hero-title {
        font-size: 2rem;
        font-weight: 700;
        color: #ffffff;
        margin: 0 0 0.4rem 0;
    }

    .hero-subtitle {
        font-size: 1rem;
        color: #CBD5E1;
        margin: 0 0 1rem 0;
    }

    .hero-badge {
        display: inline-block;
        background: rgba(255,255,255,0.12);
        border: 1px solid rgba(255,255,255,0.25);
        border-radius: 999px;
        padding: 0.25rem 0.85rem;
        font-size: 0.78rem;
        font-weight: 600;
        color: #E0E7FF;
        letter-spacing: 0.03em;
    }

    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Session state initialisation
# ---------------------------------------------------------------------------

if "df" not in st.session_state:
    st.session_state.df = None
if "summary" not in st.session_state:
    st.session_state.summary = None
if "processed_hashes" not in st.session_state:
    st.session_state.processed_hashes = set()

# ---------------------------------------------------------------------------
# Helper: generate_summary
# ---------------------------------------------------------------------------

def generate_summary(df: pd.DataFrame) -> str:
    total_amount = df["Amount"].sum()
    num_items = len(df)

    category_breakdown = (
        df.groupby("Category")["Amount"]
        .sum()
        .sort_values(ascending=False)
    )
    category_lines = ", ".join(
        cat + ": $" + "{:.2f}".format(amt)
        for cat, amt in category_breakdown.items()
    )

    vendor_totals = df.groupby("Vendor")["Amount"].sum().sort_values(ascending=False)
    top_vendor = vendor_totals.index[0] if not vendor_totals.empty else "Unknown"
    top_vendor_amount = float(vendor_totals.iloc[0]) if not vendor_totals.empty else 0.0

    doc_type_totals = df.groupby("Doc Type")["Amount"].sum().sort_values(ascending=False)
    doc_type_lines = ", ".join(
        dt + ": $" + "{:.2f}".format(amt)
        for dt, amt in doc_type_totals.items()
    )

    date_range_str = "unknown date range"
    avg_daily_str = ""
    try:
        dates = pd.to_datetime(df["Date"], errors="coerce").dropna()
        if not dates.empty:
            min_date = dates.min().strftime("%Y-%m-%d")
            max_date = dates.max().strftime("%Y-%m-%d")
            date_range_str = min_date + " to " + max_date
            num_days = max((dates.max() - dates.min()).days, 1)
            avg_daily = total_amount / num_days
            avg_daily_str = " Average daily spend: $" + "{:.2f}".format(avg_daily) + "."
    except Exception:
        pass

    prompt = (
        "You are a professional expense analyst.\n"
        "\n"
        "Write exactly 3 short sentences. Cover only:\n"
        "1. Total spend and date range.\n"
        "2. Largest spending category and top vendor.\n"
        "3. One specific actionable recommendation to reduce costs.\n"
        "\n"
        "Do not restate every number. Do not use markdown. Do not use bullet points.\n"
        "Do not use headers. Do not use bold text. Do not add preamble, commentary,\n"
        "self-evaluation, or revision notes. Return plain text only.\n"
        "\n"
        "Expense data:\n"
        "- Total amount: $" + "{:.2f}".format(total_amount) + "\n"
        "- Line items: " + str(num_items) + "\n"
        "- Date range: " + date_range_str + "\n"
        "- Category breakdown: " + category_lines + "\n"
        "- Top vendor: " + top_vendor + " ($" + "{:.2f}".format(top_vendor_amount) + ")\n"
        "- Document types: " + doc_type_lines + "\n"
        + avg_daily_str
    )

    raw = invoke_llm(prompt, max_new_tokens=300)

    # Strip markdown remnants
    cleaned_lines = []
    for line in raw.splitlines():
        line = line.strip()
        line = line.lstrip("-").strip()
        line = line.replace("**", "").replace("##", "").replace("*", "")
        if line:
            cleaned_lines.append(line)

    summary = " ".join(cleaned_lines)
    return summary

# ---------------------------------------------------------------------------
# Hero banner
# ---------------------------------------------------------------------------

st.markdown(
    """
    <div class="hero-banner">
        <div class="hero-title">🏛️ AI Expense Tracker</div>
        <div class="hero-subtitle">
            Upload expense receipts and invoices — AI extracts, categorises, and analyses your spend automatically.
        </div>
        <span class="hero-badge">⚡ Powered by IBM watsonx.ai</span>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# File uploader
# ---------------------------------------------------------------------------

uploaded_files = st.file_uploader(
    "Upload PDF receipts or invoices (max 10 files)",
    type=["pdf"],
    accept_multiple_files=True,
    help="Supported format: PDF. Up to 10 files at once.",
)

if uploaded_files and len(uploaded_files) > 10:
    st.error("Maximum 10 files allowed. Only the first 10 will be processed.")
    uploaded_files = uploaded_files[:10]

# ---------------------------------------------------------------------------
# Action buttons
# ---------------------------------------------------------------------------

col_submit, col_analyze, col_summary, col_export, col_clear = st.columns(
    [1, 1, 1.4, 1.4, 1]
)

with col_submit:
    submit_clicked = st.button("Submit", type="primary", use_container_width=True)

with col_analyze:
    analyze_clicked = st.button("Analyze", type="secondary", use_container_width=True)

with col_summary:
    summary_clicked = st.button("Generate Summary", type="secondary", use_container_width=True)

with col_export:
    if st.session_state.df is not None and not st.session_state.df.empty:
        csv_data = st.session_state.df.to_csv(index=False)
        st.download_button(
            label="Export CSV",
            data=csv_data,
            file_name="expenses.csv",
            mime="text/csv",
            use_container_width=True,
        )

with col_clear:
    if st.button("Clear All", type="secondary", use_container_width=True):
        st.session_state.df = None
        st.session_state.summary = None
        st.session_state.processed_hashes = set()
        clear_cache()
        st.rerun()

st.markdown("<div style='margin-bottom:1rem'></div>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Submit logic
# ---------------------------------------------------------------------------

if submit_clicked:
    if not uploaded_files:
        st.warning("Please upload at least one PDF file before submitting.")
    else:
        new_files = []
        for f in uploaded_files:
            file_hash = hashlib.md5(f.getvalue()).hexdigest()
            if file_hash not in st.session_state.processed_hashes:
                new_files.append(f)

        if not new_files:
            st.warning("All uploaded files have already been processed. Upload new files or click Clear All to reset.")
        else:
            progress_bar = st.progress(0)
            status_text = st.empty()

            def progress_callback(completed, total, filename):
                progress_bar.progress(int(completed / total * 100))
                status_text.text(
                    "Processing file " + str(completed) + " of " + str(total) + ": " + filename + "..."
                )

            df_new, debug_info = process_invoices(
                new_files,
                max_workers=2,
                progress_callback=progress_callback,
            )

            progress_bar.empty()
            status_text.empty()

            if st.session_state.df is None or st.session_state.df.empty:
                st.session_state.df = df_new
            else:
                st.session_state.df = pd.concat(
                    [st.session_state.df, df_new], ignore_index=True
                )

            failed_files = []
            for f in new_files:
                file_hash = hashlib.md5(f.getvalue()).hexdigest()
                dbg = debug_info.get(f.name, "")
                if dbg.startswith("ERROR"):
                    failed_files.append(f.name)
                else:
                    st.session_state.processed_hashes.add(file_hash)

            st.session_state.summary = None

            success_count = len(new_files) - len(failed_files)
            if success_count > 0:
                st.success(
                    str(success_count)
                    + " file(s) processed successfully."
                )
            if failed_files:
                st.warning(
                    "The following file(s) could not be processed: "
                    + ", ".join(failed_files)
                )

# ---------------------------------------------------------------------------
# Results section
# ---------------------------------------------------------------------------

if st.session_state.df is not None and not st.session_state.df.empty:
    df = st.session_state.df

    # Metric cards
    total_amount = df["Amount"].sum()
    mc1, mc2, mc3 = st.columns(3)

    with mc1:
        st.markdown(
            "<div class='metric-card'>"
            "<div class='metric-label'>Files Processed</div>"
            "<div class='metric-value'>" + str(len(st.session_state.processed_hashes)) + "</div>"
            "</div>",
            unsafe_allow_html=True,
        )

    with mc2:
        st.markdown(
            "<div class='metric-card'>"
            "<div class='metric-label'>Line Items</div>"
            "<div class='metric-value'>" + str(len(df)) + "</div>"
            "</div>",
            unsafe_allow_html=True,
        )

    with mc3:
        st.markdown(
            "<div class='metric-card'>"
            "<div class='metric-label'>Total Amount</div>"
            "<div class='metric-value'>$" + "{:,.2f}".format(total_amount) + "</div>"
            "</div>",
            unsafe_allow_html=True,
        )

    st.markdown("<div style='margin-bottom:1rem'></div>", unsafe_allow_html=True)

    # Ensure required columns exist
    required_columns = ["Date", "Vendor", "Doc Type", "Category", "Description", "Currency", "Amount"]
    for col in required_columns:
        if col not in df.columns:
            df[col] = ""

    display_df = df[required_columns].copy()
    display_df.columns = [
        "📅 Date",
        "🏢 Vendor",
        "📄 Doc Type",
        "🏷️ Category",
        "📝 Description",
        "💱 Currency",
        "💵 Amount",
    ]

    st.dataframe(display_df, use_container_width=True, hide_index=True)

# ---------------------------------------------------------------------------
# Analyze logic
# ---------------------------------------------------------------------------

if analyze_clicked:
    if st.session_state.df is None or st.session_state.df.empty:
        st.warning("Please upload and submit receipts first.")
    else:
        vendor_chart, category_chart, doc_type_chart, _ = analyze_invoices(
            st.session_state.df
        )
        ch1, ch2 = st.columns(2)
        with ch1:
            st.plotly_chart(vendor_chart, use_container_width=True)
        with ch2:
            st.plotly_chart(category_chart, use_container_width=True)
        st.plotly_chart(doc_type_chart, use_container_width=True)

# ---------------------------------------------------------------------------
# Generate Summary logic
# ---------------------------------------------------------------------------

if summary_clicked:
    if st.session_state.df is None or st.session_state.df.empty:
        st.warning("Please upload and submit receipts first.")
    else:
        with st.spinner("Generating AI summary..."):
            st.session_state.summary = generate_summary(st.session_state.df)

if st.session_state.summary:
    st.info(st.session_state.summary)
