# 📄 AI Resume Reviewer

A production-ready Streamlit web application that uses **IBM watsonx.ai** and **IBM Docling** to
give candidates an instant, AI-powered review of their resume against a target job description.

> Think of it as a lightweight [Jobscan](https://jobscan.co) / [Resume Worded](https://resumeworded.com)
> — upload a PDF, paste a job description, and get a full ATS analysis in seconds.

---

## ✨ Features

| Feature | Details |
|---|---|
| **PDF Extraction** | IBM Docling converts any text-based PDF into clean text (markdown-level fidelity) |
| **AI Analysis** | IBM watsonx.ai (Granite / Llama models) produces a structured JSON evaluation |
| **ATS Scoring** | Overall Score (0–100), ATS Score (0–100), Skills Match (%) |
| **Keyword Gap** | Identifies missing keywords from the job description |
| **Section Scores** | Individual scores for Summary, Experience, Education, Skills, Formatting, Keywords |
| **Visualisations** | Gauge charts, radar chart, bar chart, donut chart, strengths-vs-weaknesses chart (Plotly) |
| **Extracted Info** | Technical skills, soft skills, experience, education, certifications, projects |
| **Recommendations** | Strengths, weaknesses, grammar tips, actionable improvement list |
| **Final Verdict** | Strong Match / Moderate Match / Weak Match with rationale |
| **Export** | Download as PDF report, CSV spreadsheet, or raw JSON |

---

## 🚀 Quick Start

### 1 — Clone / copy the project

```bash
git clone <your-repo-url>
cd ai-resume-reviewer
```

### 2 — Create and activate a virtual environment

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate
```

### 3 — Install dependencies

```bash
pip install -r requirements.txt
```

> **Note:** IBM Docling downloads ML model weights on first run (~1–2 GB).
> An internet connection is required the first time.

### 4 — Configure credentials

```bash
cp .env.example .env
```

Edit `.env` and fill in your values:

```env
WATSONX_API_KEY=<your IBM Cloud API key>
WATSONX_PROJECT_ID=<your watsonx.ai project ID>
WATSONX_URL=https://us-south.ml.cloud.ibm.com
WATSONX_MODEL_ID=ibm/granite-13b-instruct-v2
```

### 5 — Run the application

```bash
streamlit run app.py
```

Open `http://localhost:8501` in your browser.

---

## 🔑 Getting IBM watsonx.ai Credentials

1. Create a free IBM Cloud account at [cloud.ibm.com](https://cloud.ibm.com)
2. Provision the **watsonx.ai** service
3. Create a **Project** in [watsonx.ai](https://dataplatform.cloud.ibm.com/wx)
4. Go to **Manage → General** and copy the **Project ID**
5. In IBM Cloud → **Manage → Access (IAM) → API Keys**, create an API key

---

## 🗂 Project Structure

```
ai-resume-reviewer/
├── app.py              # Main Streamlit application (single-file)
├── requirements.txt    # Python dependencies
├── .env.example        # Environment variable template
└── README.md           # This file
```

---

## 🧠 AI Prompt Design

The application sends a structured prompt to watsonx.ai requesting a JSON-only response with:

- Numeric scores (0–100) for overall quality, ATS compatibility, and skills match
- Categorised skill coverage scores
- Keyword presence / absence analysis
- Section-by-section scores with labels
- Lists of strengths, weaknesses, missing keywords, and improvement actions
- Grammar suggestions
- A final recommendation (`Strong Match` / `Moderate Match` / `Weak Match`)

The response is parsed with a robust JSON extractor that strips markdown code fences and falls
back gracefully if the model produces partial output.

---

## 📦 Dependencies

| Package | Purpose |
|---|---|
| `streamlit` | Web UI framework |
| `docling` | IBM PDF-to-text extraction |
| `requests` | IBM watsonx.ai REST API calls |
| `python-dotenv` | `.env` credential loading |
| `pandas` | Data manipulation for CSV export |
| `plotly` | Interactive dashboard charts |
| `fpdf2` | PDF report generation |

---

## ⚠️ Notes

- Resume text is **not stored** anywhere — all processing is in-memory for the session.
- The application does not use a database or authentication.
- AI-generated feedback is guidance only — always review suggestions critically.
- For scanned (image-based) PDFs, Docling's OCR pipeline may produce lower-quality extraction.
  Set `do_ocr=True` in `extract_text_docling()` to enable OCR (slower).

---

## 📄 License

MIT — free to use, modify, and distribute.
