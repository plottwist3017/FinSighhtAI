"""
AI Resume Reviewer — Powered by IBM watsonx.ai & IBM Docling
A professional Streamlit application for AI-powered resume analysis.
"""

import os
import io
import json
import re
import tempfile
import datetime
import requests
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

# ──────────────────────────────────────────────
# Page configuration
# ──────────────────────────────────────────────
st.set_page_config(
    page_title="AI Resume Reviewer",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ──────────────────────────────────────────────
# Global CSS
# ──────────────────────────────────────────────
st.markdown("""
<style>
  /* Base */
  [data-testid="stAppViewContainer"] { background: #f0f4f8; }
  [data-testid="stHeader"] { background: transparent; }
  [data-testid="block-container"] { padding-top: 1rem; padding-bottom: 2rem; }

  /* Cards */
  .card {
    background: #ffffff;
    border-radius: 12px;
    padding: 1.4rem 1.6rem;
    box-shadow: 0 1px 4px rgba(0,0,0,.07);
    margin-bottom: 1rem;
  }
  .card-title {
    font-size: 0.78rem;
    font-weight: 600;
    color: #6b7280;
    text-transform: uppercase;
    letter-spacing: .06em;
    margin-bottom: .4rem;
  }
  .card-value {
    font-size: 2.2rem;
    font-weight: 700;
    color: #1e293b;
    line-height: 1;
  }
  .card-sub {
    font-size: 0.8rem;
    color: #9ca3af;
    margin-top: .3rem;
  }

  /* Hero */
  .hero {
    background: linear-gradient(135deg, #1e40af 0%, #3b82f6 60%, #60a5fa 100%);
    border-radius: 16px;
    padding: 2.4rem 2.8rem;
    color: white;
    margin-bottom: 1.6rem;
  }
  .hero h1 { font-size: 2.2rem; font-weight: 800; margin: 0 0 .4rem; }
  .hero p  { font-size: 1.05rem; opacity: .88; margin: 0 0 1rem; }
  .badge {
    display: inline-block;
    background: rgba(255,255,255,.18);
    border: 1px solid rgba(255,255,255,.35);
    border-radius: 20px;
    padding: .28rem .9rem;
    font-size: .78rem;
    font-weight: 600;
    letter-spacing: .04em;
    backdrop-filter: blur(4px);
  }

  /* Section headings */
  .section-heading {
    font-size: 1.1rem;
    font-weight: 700;
    color: #1e293b;
    margin: 1.2rem 0 .6rem;
    border-left: 4px solid #3b82f6;
    padding-left: .65rem;
  }

  /* Tags */
  .tag {
    display: inline-block;
    background: #eff6ff;
    color: #1d4ed8;
    border-radius: 6px;
    padding: .18rem .6rem;
    font-size: .77rem;
    font-weight: 600;
    margin: .2rem .2rem .2rem 0;
  }
  .tag-warn {
    background: #fff7ed;
    color: #c2410c;
  }
  .tag-ok {
    background: #f0fdf4;
    color: #15803d;
  }

  /* Recommendation banner */
  .rec-strong { background:#dcfce7; border-left:5px solid #16a34a; border-radius:10px; padding:1rem 1.2rem; }
  .rec-moderate { background:#fef9c3; border-left:5px solid #ca8a04; border-radius:10px; padding:1rem 1.2rem; }
  .rec-weak { background:#fee2e2; border-left:5px solid #dc2626; border-radius:10px; padding:1rem 1.2rem; }

  /* Divider */
  hr.light { border: none; border-top: 1px solid #e5e7eb; margin: .8rem 0; }

  /* Streamlit overrides */
  div[data-testid="stFileUploader"] > label { font-weight: 600; }
  div.stButton > button {
    background: #2563eb;
    color: white;
    border: none;
    border-radius: 8px;
    padding: .6rem 1.8rem;
    font-weight: 600;
    font-size: 1rem;
    width: 100%;
    transition: background .2s;
  }
  div.stButton > button:hover { background: #1d4ed8; }
</style>
""", unsafe_allow_html=True)


# ──────────────────────────────────────────────
# Configuration helpers
# ──────────────────────────────────────────────
WATSONX_URL      = os.getenv("WATSONX_URL", "https://ca-tor.ml.cloud.ibm.com")
WATSONX_API_KEY  = os.getenv("WATSONX_API_KEY", "")
WATSONX_PROJECT  = os.getenv("WATSONX_PROJECT_ID", "")
WATSONX_MODEL    = os.getenv("WATSONX_MODEL_ID", "meta-llama/llama-3-3-70b-instruct")
IAM_URL          = "https://iam.cloud.ibm.com/identity/token"


@st.cache_data(ttl=3000, show_spinner=False)
def get_iam_token(api_key: str) -> str:
    """Exchange an IBM Cloud API key for a short-lived IAM bearer token."""
    resp = requests.post(
        IAM_URL,
        data={"grant_type": "urn:ibm:params:oauth:grant-type:apikey", "apikey": api_key},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


# ──────────────────────────────────────────────
# PDF text extraction — IBM Docling
# ──────────────────────────────────────────────
def extract_text_docling(pdf_bytes: bytes) -> str:
    """Extract text from a PDF using IBM Docling."""
    try:
        from docling.document_converter import DocumentConverter
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import PdfPipelineOptions

        pipeline_options = PdfPipelineOptions()
        pipeline_options.do_ocr = False
        pipeline_options.do_table_structure = True

        converter = DocumentConverter()

        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(pdf_bytes)
            tmp_path = tmp.name

        result = converter.convert(tmp_path)
        os.unlink(tmp_path)

        text = result.document.export_to_markdown()
        return text.strip()

    except ImportError:
        st.warning("IBM Docling is not installed. Falling back to basic PDF text extraction.")
        return extract_text_fallback(pdf_bytes)
    except Exception as exc:
        st.warning(f"Docling extraction encountered an issue: {exc}. Using fallback extraction.")
        return extract_text_fallback(pdf_bytes)


def extract_text_fallback(pdf_bytes: bytes) -> str:
    """Fallback: extract text using pypdf if available."""
    try:
        import pypdf
        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        pages = [page.extract_text() or "" for page in reader.pages]
        return "\n".join(pages).strip()
    except ImportError:
        pass
    try:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            pages = [page.extract_text() or "" for page in pdf.pages]
        return "\n".join(pages).strip()
    except ImportError:
        pass
    return "[Could not extract text. Please ensure docling or pypdf is installed.]"


# ──────────────────────────────────────────────
# IBM watsonx.ai inference
# ──────────────────────────────────────────────
def build_analysis_prompt(resume_text: str, job_description: str) -> str:
    return f"""You are an expert resume reviewer and career coach with deep knowledge of ATS systems.

Analyze the following resume against the job description provided. Return ONLY valid JSON with no markdown, no code fences, no extra text.

Resume:
\"\"\"
{resume_text[:6000]}
\"\"\"

Job Description:
\"\"\"
{job_description[:3000]}
\"\"\"

Return this exact JSON structure:
{{
  "overall_score": <integer 0-100>,
  "ats_score": <integer 0-100>,
  "skills_match_percent": <integer 0-100>,
  "missing_keywords": [<list of strings>],
  "strengths": [<list of strings>],
  "weaknesses": [<list of strings>],
  "section_scores": {{
    "Summary": <integer 0-100>,
    "Experience": <integer 0-100>,
    "Education": <integer 0-100>,
    "Skills": <integer 0-100>,
    "Formatting": <integer 0-100>,
    "Keywords": <integer 0-100>
  }},
  "skills_by_category": {{
    "Technical Skills": <integer 0-100>,
    "Soft Skills": <integer 0-100>,
    "Domain Knowledge": <integer 0-100>,
    "Tools & Platforms": <integer 0-100>
  }},
  "keyword_coverage": {{
    "Present": <integer>,
    "Missing": <integer>
  }},
  "extracted_info": {{
    "technical_skills": [<list of strings>],
    "soft_skills": [<list of strings>],
    "experience": [<list of strings>],
    "education": [<list of strings>],
    "certifications": [<list of strings>],
    "projects": [<list of strings>]
  }},
  "resume_summary": "<2-3 sentence professional assessment>",
  "grammar_suggestions": [<list of strings>],
  "improvement_suggestions": [<list of strings>],
  "recommendation": "<one of: Strong Match, Moderate Match, Weak Match>",
  "recommendation_reason": "<1-2 sentences explaining the recommendation>"
}}"""


def call_watsonx(prompt: str, api_key: str, project_id: str, model_id: str, url: str) -> dict:
    """Call IBM watsonx.ai text generation endpoint and return parsed JSON."""
    token = get_iam_token(api_key)

    endpoint = f"{url.rstrip('/')}/ml/v1/text/generation?version=2023-05-29"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    payload = {
        "model_id": model_id,
        "project_id": project_id,
        "input": prompt,
        "parameters": {
            "decoding_method": "greedy",
            "max_new_tokens": 2000,
            "min_new_tokens": 200,
            "stop_sequences": [],
            "temperature": 0.2,
        },
    }

    resp = requests.post(endpoint, headers=headers, json=payload, timeout=120)
    resp.raise_for_status()

    raw_text = resp.json()["results"][0]["generated_text"].strip()
    return parse_json_response(raw_text)


def parse_json_response(raw: str) -> dict:
    """Extract and parse the JSON block from the model response."""
    # Strip markdown code fences if present
    raw = re.sub(r"```(?:json)?", "", raw).strip().rstrip("`").strip()

    # Try direct parse
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Try to extract the first {...} block
    match = re.search(r"\{[\s\S]*\}", raw)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    # Return a graceful fallback
    return {
        "overall_score": 0,
        "ats_score": 0,
        "skills_match_percent": 0,
        "missing_keywords": [],
        "strengths": ["Analysis could not be fully parsed — please retry."],
        "weaknesses": [],
        "section_scores": {"Summary": 0, "Experience": 0, "Education": 0, "Skills": 0, "Formatting": 0, "Keywords": 0},
        "skills_by_category": {"Technical Skills": 0, "Soft Skills": 0, "Domain Knowledge": 0, "Tools & Platforms": 0},
        "keyword_coverage": {"Present": 0, "Missing": 0},
        "extracted_info": {"technical_skills": [], "soft_skills": [], "experience": [], "education": [], "certifications": [], "projects": []},
        "resume_summary": raw[:500] if raw else "No summary available.",
        "grammar_suggestions": [],
        "improvement_suggestions": [],
        "recommendation": "Weak Match",
        "recommendation_reason": "Could not parse structured response from the model.",
    }


# ──────────────────────────────────────────────
# Plotly chart helpers
# ──────────────────────────────────────────────
CHART_CONFIG = {"displayModeBar": False}
COLORS_BLUE = ["#3b82f6", "#60a5fa", "#93c5fd", "#bfdbfe", "#1d4ed8", "#2563eb"]


def gauge_chart(value: int, title: str, color: str = "#3b82f6") -> go.Figure:
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=value,
        title={"text": title, "font": {"size": 14, "color": "#374151"}},
        number={"font": {"size": 32, "color": "#1e293b"}, "suffix": ""},
        gauge={
            "axis": {"range": [0, 100], "tickwidth": 1, "tickcolor": "#d1d5db"},
            "bar": {"color": color},
            "bgcolor": "#f3f4f6",
            "borderwidth": 0,
            "steps": [
                {"range": [0, 40],  "color": "#fee2e2"},
                {"range": [40, 70], "color": "#fef9c3"},
                {"range": [70, 100],"color": "#dcfce7"},
            ],
            "threshold": {"line": {"color": color, "width": 3}, "thickness": 0.8, "value": value},
        },
    ))
    fig.update_layout(height=220, margin=dict(t=40, b=10, l=20, r=20), paper_bgcolor="white", plot_bgcolor="white")
    return fig


def radar_chart(categories: list, values: list) -> go.Figure:
    cats = categories + [categories[0]]
    vals = values + [values[0]]
    fig = go.Figure(go.Scatterpolar(
        r=vals, theta=cats,
        fill="toself",
        fillcolor="rgba(59,130,246,0.15)",
        line=dict(color="#3b82f6", width=2),
        marker=dict(color="#1d4ed8", size=6),
    ))
    fig.update_layout(
        polar=dict(
            radialaxis=dict(visible=True, range=[0, 100], tickfont=dict(size=10), gridcolor="#e5e7eb"),
            angularaxis=dict(tickfont=dict(size=11)),
            bgcolor="white",
        ),
        showlegend=False,
        height=320,
        margin=dict(t=20, b=20, l=40, r=40),
        paper_bgcolor="white",
    )
    return fig


def bar_chart(labels: list, values: list, title: str, color: str = "#3b82f6") -> go.Figure:
    fig = go.Figure(go.Bar(
        x=values, y=labels,
        orientation="h",
        marker=dict(color=color, line=dict(width=0)),
        text=[f"{v}" for v in values],
        textposition="outside",
        textfont=dict(size=12, color="#374151"),
    ))
    fig.update_layout(
        title=dict(text=title, font=dict(size=14, color="#1e293b"), x=0),
        xaxis=dict(range=[0, 110], showgrid=True, gridcolor="#f3f4f6", zeroline=False, tickfont=dict(size=11)),
        yaxis=dict(tickfont=dict(size=12), automargin=True),
        height=max(200, len(labels) * 48 + 60),
        margin=dict(t=40, b=20, l=10, r=60),
        paper_bgcolor="white",
        plot_bgcolor="white",
    )
    return fig


def donut_chart(labels: list, values: list, title: str) -> go.Figure:
    fig = go.Figure(go.Pie(
        labels=labels, values=values,
        hole=0.55,
        marker=dict(colors=["#3b82f6", "#f87171"], line=dict(color="white", width=2)),
        textinfo="label+percent",
        textfont=dict(size=12),
    ))
    fig.update_layout(
        title=dict(text=title, font=dict(size=14, color="#1e293b"), x=0),
        showlegend=True,
        legend=dict(orientation="h", y=-0.1, font=dict(size=11)),
        height=280,
        margin=dict(t=40, b=30, l=10, r=10),
        paper_bgcolor="white",
    )
    return fig


def sw_bar_chart(strengths: list, weaknesses: list) -> go.Figure:
    cats = [f"S{i+1}: {s[:30]}" for i, s in enumerate(strengths[:5])]
    cats += [f"W{i+1}: {w[:30]}" for i, w in enumerate(weaknesses[:5])]
    vals = [80 + i * 2 for i in range(len(strengths[:5]))] + [-(30 + i * 5) for i in range(len(weaknesses[:5]))]
    colors = ["#3b82f6"] * len(strengths[:5]) + ["#f87171"] * len(weaknesses[:5])

    fig = go.Figure(go.Bar(
        x=vals, y=cats,
        orientation="h",
        marker=dict(color=colors),
    ))
    fig.add_vline(x=0, line=dict(color="#9ca3af", width=1))
    fig.update_layout(
        title=dict(text="Strengths vs. Weaknesses", font=dict(size=14, color="#1e293b"), x=0),
        xaxis=dict(showgrid=True, gridcolor="#f3f4f6", zeroline=False),
        yaxis=dict(automargin=True, tickfont=dict(size=11)),
        height=max(240, (len(strengths[:5]) + len(weaknesses[:5])) * 38 + 60),
        margin=dict(t=40, b=20, l=20, r=20),
        paper_bgcolor="white",
        plot_bgcolor="white",
    )
    return fig


# ──────────────────────────────────────────────
# Export helpers
# ──────────────────────────────────────────────
def build_csv(data: dict) -> bytes:
    rows = []
    rows.append({"Category": "Overall Score",   "Value": data.get("overall_score", 0)})
    rows.append({"Category": "ATS Score",        "Value": data.get("ats_score", 0)})
    rows.append({"Category": "Skills Match (%)", "Value": data.get("skills_match_percent", 0)})
    rows.append({"Category": "Missing Keywords", "Value": len(data.get("missing_keywords", []))})

    for k, v in data.get("section_scores", {}).items():
        rows.append({"Category": f"Section: {k}", "Value": v})

    for item in data.get("strengths", []):
        rows.append({"Category": "Strength", "Value": item})
    for item in data.get("weaknesses", []):
        rows.append({"Category": "Weakness", "Value": item})
    for item in data.get("missing_keywords", []):
        rows.append({"Category": "Missing Keyword", "Value": item})
    for item in data.get("improvement_suggestions", []):
        rows.append({"Category": "Improvement", "Value": item})

    df = pd.DataFrame(rows)
    return df.to_csv(index=False).encode("utf-8")


def build_pdf_report(data: dict, resume_name: str) -> bytes:
    """Generate a PDF report using fpdf2."""
    try:
        from fpdf import FPDF

        class PDF(FPDF):
            def header(self):
                self.set_fill_color(30, 64, 175)
                self.rect(0, 0, 210, 18, "F")
                self.set_font("Helvetica", "B", 13)
                self.set_text_color(255, 255, 255)
                self.set_y(4)
                self.cell(0, 10, "AI Resume Reviewer — Analysis Report", align="C")
                self.ln(14)
                self.set_text_color(0, 0, 0)

            def footer(self):
                self.set_y(-12)
                self.set_font("Helvetica", "", 8)
                self.set_text_color(150, 150, 150)
                self.cell(0, 6, f"Generated {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}  |  Powered by IBM watsonx.ai", align="C")

        pdf = PDF()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()
        pdf.set_margins(18, 22, 18)

        def section(title):
            pdf.set_font("Helvetica", "B", 11)
            pdf.set_fill_color(239, 246, 255)
            pdf.set_draw_color(59, 130, 246)
            pdf.set_text_color(30, 64, 175)
            pdf.cell(0, 8, f"  {title}", border="L", fill=True, ln=True)
            pdf.set_text_color(0, 0, 0)
            pdf.ln(2)

        def body(text):
            pdf.set_font("Helvetica", "", 10)
            pdf.set_text_color(31, 35, 40)
            pdf.multi_cell(0, 6, text)
            pdf.ln(1)

        def bullet_list(items):
            pdf.set_font("Helvetica", "", 10)
            pdf.set_text_color(31, 35, 40)
            for item in items:
                pdf.cell(6)
                pdf.multi_cell(0, 6, f"\u2022  {item}")
            pdf.ln(1)

        # Meta
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(90, 90, 90)
        pdf.cell(0, 6, f"Resume: {resume_name}    |    Date: {datetime.datetime.now().strftime('%B %d, %Y')}", ln=True)
        pdf.ln(3)

        # Scores
        section("Scores")
        scores_text = (
            f"Overall Resume Score: {data.get('overall_score', 'N/A')}/100\n"
            f"ATS Compatibility Score: {data.get('ats_score', 'N/A')}/100\n"
            f"Skills Match: {data.get('skills_match_percent', 'N/A')}%\n"
            f"Missing Keywords: {len(data.get('missing_keywords', []))}"
        )
        body(scores_text)

        # Recommendation
        section("Recommendation")
        body(f"{data.get('recommendation', 'N/A')} — {data.get('recommendation_reason', '')}")

        # Summary
        section("Resume Summary")
        body(data.get("resume_summary", ""))

        # Section scores
        section("Section Scores")
        for k, v in data.get("section_scores", {}).items():
            body(f"{k}: {v}/100")

        # Strengths
        section("Strengths")
        bullet_list(data.get("strengths", []))

        # Weaknesses
        section("Areas for Improvement")
        bullet_list(data.get("weaknesses", []))

        # Missing keywords
        section("Missing Keywords")
        body(", ".join(data.get("missing_keywords", [])) or "None identified.")

        # Suggestions
        section("Actionable Improvement Suggestions")
        bullet_list(data.get("improvement_suggestions", []))

        # Grammar suggestions
        if data.get("grammar_suggestions"):
            section("Grammar & Wording Suggestions")
            bullet_list(data.get("grammar_suggestions", []))

        return bytes(pdf.output())

    except ImportError:
        # Plain-text fallback encoded as bytes
        lines = [
            "AI Resume Reviewer — Analysis Report",
            "=" * 50,
            f"Overall Score: {data.get('overall_score')}/100",
            f"ATS Score:     {data.get('ats_score')}/100",
            f"Skills Match:  {data.get('skills_match_percent')}%",
            f"Recommendation: {data.get('recommendation')}",
            "",
            "Strengths:",
            *[f"  • {s}" for s in data.get("strengths", [])],
            "",
            "Weaknesses:",
            *[f"  • {w}" for w in data.get("weaknesses", [])],
            "",
            "Missing Keywords:",
            "  " + ", ".join(data.get("missing_keywords", [])),
            "",
            "Improvements:",
            *[f"  • {i}" for i in data.get("improvement_suggestions", [])],
        ]
        return "\n".join(lines).encode("utf-8")


# ──────────────────────────────────────────────
# Score colour helper
# ──────────────────────────────────────────────
def score_color(score: int) -> str:
    if score >= 70:
        return "#16a34a"
    elif score >= 40:
        return "#ca8a04"
    return "#dc2626"


def score_label(score: int) -> str:
    if score >= 70:
        return "Good"
    elif score >= 40:
        return "Fair"
    return "Needs Work"


# ──────────────────────────────────────────────
# Main UI
# ──────────────────────────────────────────────
def main():
    # ── Hero ──────────────────────────────────
    st.markdown("""
    <div class="hero">
      <h1>📄 AI Resume Reviewer</h1>
      <p>Upload your resume and paste a job description to receive an AI-powered ATS analysis,
         resume score, keyword gap report, and personalised improvement suggestions.</p>
      <span class="badge">⚡ Powered by IBM watsonx.ai &nbsp;|&nbsp; IBM Docling</span>
    </div>
    """, unsafe_allow_html=True)

    # ── Sidebar — credentials ─────────────────
    with st.sidebar:
        st.markdown("### ⚙️ Configuration")
        st.caption("Credentials are loaded from `.env` by default. Override here for this session.")

        api_key   = st.text_input("IBM Cloud API Key",    value=WATSONX_API_KEY,  type="password", key="api_key")
        proj_id   = st.text_input("watsonx.ai Project ID", value=WATSONX_PROJECT, type="password", key="proj_id")
        model_id  = st.selectbox("Model", [
            "meta-llama/llama-3-3-70b-instruct",
            "meta-llama/llama-3-8b-instruct",
            "ibm/granite-13b-instruct-v2",
            "ibm/granite-20b-multilingual",
            "ibm/granite-3-8b-instruct",
        ], index=0)
        wx_url    = st.text_input("watsonx.ai URL", value=WATSONX_URL)

        st.markdown("---")
        st.markdown("""
        **How to get credentials:**
        1. Sign up at [ibm.com/watsonx](https://ibm.com/watsonx)
        2. Create a Project in watsonx.ai
        3. Generate an API Key in IBM Cloud IAM
        4. Copy the Project ID from project settings
        """)

    # ── Upload + JD ───────────────────────────
    col_up, col_jd = st.columns([1, 1], gap="large")

    with col_up:
        st.markdown('<div class="section-heading">Resume Upload</div>', unsafe_allow_html=True)
        with st.container():
            st.markdown('<div class="card">', unsafe_allow_html=True)
            uploaded_file = st.file_uploader(
                "Upload Resume (PDF)",
                type=["pdf"],
                help="Upload a single PDF resume. IBM Docling will extract all text.",
            )
            if uploaded_file:
                st.success(f"✅ **{uploaded_file.name}** — {uploaded_file.size / 1024:.1f} KB")
            st.markdown('</div>', unsafe_allow_html=True)

    with col_jd:
        st.markdown('<div class="section-heading">Job Description</div>', unsafe_allow_html=True)
        with st.container():
            st.markdown('<div class="card">', unsafe_allow_html=True)
            job_desc = st.text_area(
                "Paste the Job Description",
                height=180,
                placeholder="Paste the full job description here including required skills, responsibilities, and qualifications...",
            )
            jd_word_count = len(job_desc.split()) if job_desc else 0
            st.caption(f"{jd_word_count} words")
            st.markdown('</div>', unsafe_allow_html=True)

    # ── Analyze button ─────────────────────────
    st.markdown("")
    btn_col, _ = st.columns([1, 3])
    with btn_col:
        analyze_clicked = st.button("🔍 Analyze Resume", use_container_width=True)

    # ── Validation ────────────────────────────
    if analyze_clicked:
        errors = []
        if not uploaded_file:
            errors.append("Please upload a PDF resume.")
        if not job_desc.strip():
            errors.append("Please paste a job description.")
        if not api_key:
            errors.append("IBM Cloud API Key is missing — add it in the sidebar or `.env`.")
        if not proj_id:
            errors.append("watsonx.ai Project ID is missing — add it in the sidebar or `.env`.")

        if errors:
            for e in errors:
                st.error(e)
            st.stop()

        # ── Extraction ────────────────────────
        with st.status("🔬 Extracting resume text with IBM Docling…", expanded=True) as status:
            pdf_bytes = uploaded_file.read()
            st.write("Reading PDF…")
            resume_text = extract_text_docling(pdf_bytes)
            word_count = len(resume_text.split())
            st.write(f"✅ Extracted **{word_count}** words from **{len(resume_text)}** characters.")
            status.update(label="✅ Text extraction complete", state="complete")

        if not resume_text.strip() or word_count < 20:
            st.error("Could not extract meaningful text from the PDF. Please ensure it is a text-based PDF, not a scanned image.")
            st.stop()

        # ── Watsonx inference ─────────────────
        with st.status("🤖 Analyzing with IBM watsonx.ai…", expanded=True) as status:
            st.write(f"Sending to model `{model_id}`…")
            try:
                prompt = build_analysis_prompt(resume_text, job_desc)
                result = call_watsonx(prompt, api_key, proj_id, model_id, wx_url)
                st.write("✅ AI analysis complete.")
                status.update(label="✅ watsonx.ai analysis complete", state="complete")
            except requests.HTTPError as exc:
                status.update(label="❌ API Error", state="error")
                st.error(f"watsonx.ai API error: {exc.response.status_code} — {exc.response.text[:400]}")
                st.stop()
            except Exception as exc:
                status.update(label="❌ Error", state="error")
                st.error(f"Unexpected error: {exc}")
                st.stop()

        st.session_state["result"]      = result
        st.session_state["resume_text"] = resume_text
        st.session_state["resume_name"] = uploaded_file.name
        st.session_state["job_desc"]    = job_desc

    # ── Dashboard (only when result is available) ──
    result = st.session_state.get("result")
    if not result:
        st.markdown("---")
        st.info("👆 Upload your resume and paste a job description, then click **Analyze Resume** to get started.")
        return

    resume_name = st.session_state.get("resume_name", "resume.pdf")

    st.markdown("---")
    st.markdown('<div class="section-heading">📊 Analysis Dashboard</div>', unsafe_allow_html=True)

    # ── Metric cards ──────────────────────────
    m1, m2, m3, m4 = st.columns(4, gap="medium")

    overall = result.get("overall_score", 0)
    ats     = result.get("ats_score", 0)
    skills  = result.get("skills_match_percent", 0)
    missing = len(result.get("missing_keywords", []))

    with m1:
        st.markdown(f"""
        <div class="card" style="border-top:4px solid {score_color(overall)}">
          <div class="card-title">Resume Score</div>
          <div class="card-value" style="color:{score_color(overall)}">{overall}<span style="font-size:1rem;color:#9ca3af">/100</span></div>
          <div class="card-sub">{score_label(overall)}</div>
        </div>""", unsafe_allow_html=True)

    with m2:
        st.markdown(f"""
        <div class="card" style="border-top:4px solid {score_color(ats)}">
          <div class="card-title">ATS Score</div>
          <div class="card-value" style="color:{score_color(ats)}">{ats}<span style="font-size:1rem;color:#9ca3af">/100</span></div>
          <div class="card-sub">ATS Compatibility</div>
        </div>""", unsafe_allow_html=True)

    with m3:
        st.markdown(f"""
        <div class="card" style="border-top:4px solid {score_color(skills)}">
          <div class="card-title">Skills Match</div>
          <div class="card-value" style="color:{score_color(skills)}">{skills}<span style="font-size:1rem;color:#9ca3af">%</span></div>
          <div class="card-sub">vs. Job Requirements</div>
        </div>""", unsafe_allow_html=True)

    with m4:
        mk_color = "#dc2626" if missing > 5 else "#ca8a04" if missing > 2 else "#16a34a"
        st.markdown(f"""
        <div class="card" style="border-top:4px solid {mk_color}">
          <div class="card-title">Missing Keywords</div>
          <div class="card-value" style="color:{mk_color}">{missing}</div>
          <div class="card-sub">Keywords to add</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("")

    # ── Charts row 1: Gauges ──────────────────
    st.markdown('<div class="section-heading">📈 Score Visualizations</div>', unsafe_allow_html=True)
    gc1, gc2, gc3 = st.columns(3, gap="medium")

    with gc1:
        with st.container():
            st.markdown('<div class="card" style="padding:.8rem">', unsafe_allow_html=True)
            st.plotly_chart(gauge_chart(overall, "Overall Score", score_color(overall)), use_container_width=True, config=CHART_CONFIG)
            st.markdown('</div>', unsafe_allow_html=True)

    with gc2:
        with st.container():
            st.markdown('<div class="card" style="padding:.8rem">', unsafe_allow_html=True)
            st.plotly_chart(gauge_chart(ats, "ATS Score", score_color(ats)), use_container_width=True, config=CHART_CONFIG)
            st.markdown('</div>', unsafe_allow_html=True)

    with gc3:
        with st.container():
            st.markdown('<div class="card" style="padding:.8rem">', unsafe_allow_html=True)
            st.plotly_chart(gauge_chart(skills, "Skills Match %", score_color(skills)), use_container_width=True, config=CHART_CONFIG)
            st.markdown('</div>', unsafe_allow_html=True)

    # ── Charts row 2 ──────────────────────────
    ch1, ch2 = st.columns(2, gap="medium")

    section_scores = result.get("section_scores", {})
    skills_by_cat  = result.get("skills_by_category", {})
    kw_coverage    = result.get("keyword_coverage", {"Present": 0, "Missing": 0})

    with ch1:
        st.markdown('<div class="card" style="padding:.8rem">', unsafe_allow_html=True)
        if section_scores:
            fig = bar_chart(
                list(section_scores.keys()),
                list(section_scores.values()),
                "Resume Section Scores",
                color=COLORS_BLUE[0],
            )
            st.plotly_chart(fig, use_container_width=True, config=CHART_CONFIG)
        st.markdown('</div>', unsafe_allow_html=True)

    with ch2:
        st.markdown('<div class="card" style="padding:.8rem">', unsafe_allow_html=True)
        if skills_by_cat:
            fig = radar_chart(list(skills_by_cat.keys()), list(skills_by_cat.values()))
            st.plotly_chart(fig, use_container_width=True, config=CHART_CONFIG)
        st.markdown('</div>', unsafe_allow_html=True)

    # ── Charts row 3 ──────────────────────────
    ch3, ch4 = st.columns(2, gap="medium")

    with ch3:
        st.markdown('<div class="card" style="padding:.8rem">', unsafe_allow_html=True)
        if kw_coverage:
            fig = donut_chart(
                list(kw_coverage.keys()),
                list(kw_coverage.values()),
                "Keyword Coverage",
            )
            st.plotly_chart(fig, use_container_width=True, config=CHART_CONFIG)
        st.markdown('</div>', unsafe_allow_html=True)

    with ch4:
        st.markdown('<div class="card" style="padding:.8rem">', unsafe_allow_html=True)
        strengths  = result.get("strengths", [])
        weaknesses = result.get("weaknesses", [])
        if strengths or weaknesses:
            fig = sw_bar_chart(strengths, weaknesses)
            st.plotly_chart(fig, use_container_width=True, config=CHART_CONFIG)
        st.markdown('</div>', unsafe_allow_html=True)

    # ── Extracted info table ───────────────────
    st.markdown('<div class="section-heading">📋 Extracted Resume Information</div>', unsafe_allow_html=True)
    extracted = result.get("extracted_info", {})

    ei_cols = st.columns(3, gap="medium")
    ei_fields = [
        ("Technical Skills",  "technical_skills",  "🔧"),
        ("Soft Skills",       "soft_skills",        "🤝"),
        ("Experience",        "experience",         "💼"),
        ("Education",         "education",          "🎓"),
        ("Certifications",    "certifications",     "🏆"),
        ("Projects",          "projects",           "🚀"),
    ]

    for i, (label, key, icon) in enumerate(ei_fields):
        with ei_cols[i % 3]:
            items = extracted.get(key, [])
            st.markdown(f'<div class="card">', unsafe_allow_html=True)
            st.markdown(f"**{icon} {label}**")
            if items:
                tags_html = " ".join(f'<span class="tag">{t}</span>' for t in items[:12])
                st.markdown(tags_html, unsafe_allow_html=True)
            else:
                st.caption("None identified.")
            st.markdown('</div>', unsafe_allow_html=True)

    # ── AI Feedback sections ───────────────────
    st.markdown('<div class="section-heading">🧠 AI Feedback</div>', unsafe_allow_html=True)

    fb1, fb2 = st.columns([1, 1], gap="large")

    with fb1:
        # Summary
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("**📝 Resume Summary**")
        st.write(result.get("resume_summary", ""))
        st.markdown('</div>', unsafe_allow_html=True)

        # Strengths
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("**✅ Resume Strengths**")
        for s in strengths:
            st.markdown(f'<span class="tag tag-ok">✓</span> {s}', unsafe_allow_html=True)
            st.markdown("")
        st.markdown('</div>', unsafe_allow_html=True)

        # Grammar
        grammar = result.get("grammar_suggestions", [])
        if grammar:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.markdown("**✍️ Grammar & Wording Suggestions**")
            for g in grammar:
                st.markdown(f"- {g}")
            st.markdown('</div>', unsafe_allow_html=True)

    with fb2:
        # Weaknesses
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("**⚠️ Areas for Improvement**")
        for w in weaknesses:
            st.markdown(f'<span class="tag tag-warn">!</span> {w}', unsafe_allow_html=True)
            st.markdown("")
        st.markdown('</div>', unsafe_allow_html=True)

        # Missing keywords
        mk = result.get("missing_keywords", [])
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("**🔑 Missing Keywords**")
        if mk:
            tags_html = " ".join(f'<span class="tag tag-warn">{kw}</span>' for kw in mk)
            st.markdown(tags_html, unsafe_allow_html=True)
        else:
            st.markdown('<span class="tag tag-ok">None missing — great keyword coverage!</span>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        # Improvements
        improvements = result.get("improvement_suggestions", [])
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("**💡 Actionable Improvements**")
        for idx_i, imp in enumerate(improvements, 1):
            st.markdown(f"**{idx_i}.** {imp}")
        st.markdown('</div>', unsafe_allow_html=True)

    # ── Section-by-section scores detail ──────
    st.markdown('<div class="section-heading">📂 Section-by-Section Breakdown</div>', unsafe_allow_html=True)
    if section_scores:
        cols = st.columns(len(section_scores), gap="small")
        for i, (sec, score) in enumerate(section_scores.items()):
            with cols[i]:
                sc = score_color(score)
                st.markdown(f"""
                <div class="card" style="text-align:center;border-top:3px solid {sc}">
                  <div class="card-title">{sec}</div>
                  <div class="card-value" style="color:{sc};font-size:1.8rem">{score}</div>
                  <div class="card-sub">/100 · {score_label(score)}</div>
                </div>""", unsafe_allow_html=True)

    # ── Final recommendation ───────────────────
    st.markdown('<div class="section-heading">🎯 Final Recommendation</div>', unsafe_allow_html=True)
    rec = result.get("recommendation", "Moderate Match")
    rec_reason = result.get("recommendation_reason", "")

    if "Strong" in rec:
        cls = "rec-strong"
        icon = "🟢"
    elif "Moderate" in rec:
        cls = "rec-moderate"
        icon = "🟡"
    else:
        cls = "rec-weak"
        icon = "🔴"

    st.markdown(f"""
    <div class="{cls}">
      <h3 style="margin:0 0 .4rem">{icon} {rec}</h3>
      <p style="margin:0">{rec_reason}</p>
    </div>
    """, unsafe_allow_html=True)

    # ── Raw extracted text expander ────────────
    with st.expander("🔍 View Extracted Resume Text (from IBM Docling)"):
        st.text_area("Raw Text", st.session_state.get("resume_text", ""), height=280, disabled=True)

    # ── Export ────────────────────────────────
    st.markdown('<div class="section-heading">📥 Export Results</div>', unsafe_allow_html=True)
    export_cols = st.columns(3, gap="medium")

    with export_cols[0]:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("**📄 PDF Report**")
        st.caption("Full analysis report with scores, feedback, and recommendations.")
        pdf_bytes = build_pdf_report(result, resume_name)
        st.download_button(
            "⬇ Download PDF",
            data=pdf_bytes,
            file_name=f"resume_review_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
            mime="application/pdf",
            use_container_width=True,
        )
        st.markdown('</div>', unsafe_allow_html=True)

    with export_cols[1]:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("**📊 CSV Export**")
        st.caption("Scores, keywords, strengths, and suggestions as a spreadsheet.")
        csv_bytes = build_csv(result)
        st.download_button(
            "⬇ Download CSV",
            data=csv_bytes,
            file_name=f"resume_analysis_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv",
            use_container_width=True,
        )
        st.markdown('</div>', unsafe_allow_html=True)

    with export_cols[2]:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("**🗂 JSON Export**")
        st.caption("Full structured AI response — ideal for integrations and pipelines.")
        json_str = json.dumps(result, indent=2)
        st.download_button(
            "⬇ Download JSON",
            data=json_str.encode("utf-8"),
            file_name=f"resume_analysis_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.json",
            mime="application/json",
            use_container_width=True,
        )
        st.markdown('</div>', unsafe_allow_html=True)

    # ── Footer ────────────────────────────────
    st.markdown("""
    <hr style="border:none;border-top:1px solid #e5e7eb;margin:2rem 0 .8rem">
    <p style="text-align:center;color:#9ca3af;font-size:.78rem">
      AI Resume Reviewer &nbsp;|&nbsp; Built with IBM watsonx.ai &amp; IBM Docling &nbsp;|&nbsp;
      Results are AI-generated and should be used as guidance, not as definitive assessments.
    </p>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
