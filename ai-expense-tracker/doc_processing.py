import hashlib
import json
import os
import re
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import plotly.graph_objects as go
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption

from model_gateway import invoke_llm

# ---------------------------------------------------------------------------
# Module-level singletons
# ---------------------------------------------------------------------------

_pipeline_options = PdfPipelineOptions()
_pipeline_options.do_ocr = True
_pipeline_options.do_table_structure = True

_converter = DocumentConverter(
    format_options={
        InputFormat.PDF: PdfFormatOption(pipeline_options=_pipeline_options)
    }
)

_file_cache: dict = {}

# ---------------------------------------------------------------------------
# Cache management
# ---------------------------------------------------------------------------

def clear_cache():
    global _file_cache
    _file_cache = {}

# ---------------------------------------------------------------------------
# PDF parsing
# ---------------------------------------------------------------------------

def _pdf_to_markdown(pdf_bytes: bytes) -> str:
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(pdf_bytes)
            tmp_path = tmp.name
        result = _converter.convert(tmp_path)
        return result.document.export_to_markdown()
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)

# ---------------------------------------------------------------------------
# Document type detection
# ---------------------------------------------------------------------------

_TYPE_KEYWORDS = {
    "office_supplies": [
        "office", "supplies", "paper", "pens", "folders", "stationery",
        "toner", "ink", "printer", "desk", "chair", "filing",
    ],
    "equipment": [
        "equipment", "computer", "laptop", "monitor", "keyboard", "mouse",
        "hardware", "software", "technology", "device", "machinery",
    ],
    "services": [
        "services", "consulting", "maintenance", "repair", "cleaning",
        "security", "professional", "contractor", "vendor", "support",
    ],
    "utilities": [
        "utilities", "electricity", "water", "gas", "internet", "phone",
        "telecommunications", "energy", "power", "heating", "cooling",
    ],
}


def _detect_doc_type(filename: str, text: str) -> str:
    filename_lower = filename.lower()
    text_lower = text.lower()

    scores = {doc_type: 0 for doc_type in _TYPE_KEYWORDS}
    for doc_type, keywords in _TYPE_KEYWORDS.items():
        for kw in keywords:
            if kw in filename_lower:
                scores[doc_type] += 3
            if kw in text_lower:
                scores[doc_type] += 1

    best_type = max(scores, key=lambda k: scores[k])
    if scores[best_type] == 0:
        return "generic"
    return best_type

# ---------------------------------------------------------------------------
# LLM prompts
# ---------------------------------------------------------------------------

def _get_extraction_prompt(doc_type: str, text: str) -> str:
    if doc_type == "office_supplies":
        categories = "Paper Products, Writing Instruments, Filing & Storage, Desk Accessories, Printer Supplies, Technology Accessories, Furniture, Taxes & Fees, Shipping, Miscellaneous"
        label = "office supplies invoice"
    elif doc_type == "equipment":
        categories = "Computer Hardware, Software Licenses, Peripherals, Networking Equipment, Maintenance, Installation, Taxes & Fees, Miscellaneous"
        label = "equipment invoice"
    elif doc_type == "services":
        categories = "Consulting, Maintenance, Repair, Cleaning, Security, Professional Services, Contractor Fees, Taxes & Fees, Miscellaneous"
        label = "services invoice"
    elif doc_type == "utilities":
        categories = "Electricity, Water, Gas, Internet, Telephone, Telecommunications, Energy, Taxes & Fees, Service Charges, Miscellaneous"
        label = "utilities invoice"
    else:
        categories = "Office Supplies, Equipment, Services, Utilities, Maintenance, Professional Services, Technology, Taxes & Fees, Miscellaneous"
        label = "invoice"

    item_label = "item/charge" if doc_type == "services" else "charge"

    prompt = (
        "Analyze this " + label + " and extract all charges. Ignore any [image] tags.\n"
        "\n"
        "STEP 1: Create a table with these columns separated by | (pipe):\n"
        "Date | Vendor | Category | Description | Currency | Amount\n"
        "\n"
        "Categories: " + categories + "\n"
        "\n"
        "Rules:\n"
        "- One line per " + item_label + "\n"
        "- Date format: YYYY-MM-DD (or leave empty if not found)\n"
        "- Amount: numeric only (no currency symbols)\n"
        "- Include header row\n"
        "- Use | to separate columns\n"
        "\n"
        "Document:\n"
        + text +
        "\n"
        "\n"
        "Table:\n"
        "\n"
        "STEP 2: Now convert the table above into a JSON array. Each row becomes a JSON object with these fields:\n"
        "- date (from Date column)\n"
        "- vendor (from Vendor column)\n"
        "- doc_type (leave as empty string)\n"
        "- category (from Category column)\n"
        "- description (from Description column)\n"
        "- currency (from Currency column)\n"
        "- amount (from Amount column)\n"
        "- confidence (set to 0.9)\n"
        "\n"
        "Return ONLY the JSON array with no markdown, no code fences, no explanation:\n"
        "[\""
    )
    return prompt

# ---------------------------------------------------------------------------
# Vendor extraction
# ---------------------------------------------------------------------------

_HEADER_KEYWORDS = {
    "invoice", "folio", "date", "page", "guest", "number",
    "charges", "credits", "description",
}


def _extract_vendor_from_text(text: str) -> str:
    lines = text.splitlines()[:10]
    for line in lines:
        stripped = line.strip()
        lower = stripped.lower()
        if any(kw in lower for kw in _HEADER_KEYWORDS):
            continue
        if len(stripped) >= 3 and re.search(r"[a-zA-Z]", stripped):
            return stripped

    # Fallback: first sequence of capitalized words in top lines
    top_text = " ".join(lines)
    match = re.search(r"([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)", top_text)
    if match:
        return match.group(1)

    return "Unknown"


def _normalize_expenses(rows: list, filename: str, text: str) -> list:
    doc_type_raw = _detect_doc_type(filename, text)
    doc_type_map = {
        "office_supplies": "Office Supplies",
        "equipment": "Equipment",
        "services": "Services",
        "utilities": "Utilities",
        "generic": "",
    }
    doc_type_display = doc_type_map.get(doc_type_raw, "")

    normalized = []
    for row in rows:
        if not isinstance(row, dict):
            continue

        vendor = str(row.get("vendor", "")).strip()
        if not vendor or vendor.lower() == "unknown":
            vendor = _extract_vendor_from_text(text)

        raw_amount = row.get("amount", 0)
        amount = _parse_amount(raw_amount) if isinstance(raw_amount, str) else abs(float(raw_amount)) if raw_amount else 0.0

        confidence = row.get("confidence", 0.9)
        try:
            confidence = float(confidence)
        except (TypeError, ValueError):
            confidence = 0.0

        normalized.append({
            "date": str(row.get("date", "")).strip(),
            "vendor": vendor,
            "doc_type": doc_type_display,
            "category": str(row.get("category", "")).strip(),
            "description": str(row.get("description", "")).strip(),
            "currency": str(row.get("currency", "")).strip(),
            "amount": amount,
            "confidence": confidence,
        })

    return normalized

# ---------------------------------------------------------------------------
# Amount parsing
# ---------------------------------------------------------------------------

def _parse_amount(amount_str) -> float:
    if amount_str is None:
        return 0.0
    s = str(amount_str).strip()
    # Remove currency symbols
    s = re.sub(r"[$€£¥₹]", "", s).strip()
    if not s:
        return 0.0
    try:
        # European format: 1.234,56 or 1,5 (comma as decimal, dot as thousands)
        if re.match(r"^\d{1,3}(\.\d{3})+(,\d+)$", s):
            s = s.replace(".", "").replace(",", ".")
        elif re.match(r"^\d+(,\d+)$", s):
            s = s.replace(",", ".")
        else:
            # Standard: remove thousands commas
            s = s.replace(",", "")
        return abs(float(s))
    except (ValueError, TypeError):
        return 0.0

# ---------------------------------------------------------------------------
# JSON parsing
# ---------------------------------------------------------------------------

def _parse_json_from_llm(llm_output: str) -> list:
    # Prepend "[" because prompt ends with [" to prime LLM
    text = "[" + llm_output

    # Strip markdown code fences
    text = re.sub(r"```(?:json)?", "", text).strip()

    # Strategy 1: brace-depth scanning to find [...] boundary
    try:
        start = text.find("[")
        if start != -1:
            depth = 0
            for i, ch in enumerate(text[start:], start):
                if ch == "[":
                    depth += 1
                elif ch == "]":
                    depth -= 1
                    if depth == 0:
                        candidate = text[start: i + 1]
                        parsed = json.loads(candidate)
                        if isinstance(parsed, list):
                            return parsed
                        break
    except (json.JSONDecodeError, ValueError):
        pass

    # Strategy 2: extract top-level {...} objects using brace counting
    try:
        objects = []
        depth = 0
        start = None
        for i, ch in enumerate(text):
            if ch == "{":
                if depth == 0:
                    start = i
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0 and start is not None:
                    try:
                        obj = json.loads(text[start: i + 1])
                        objects.append(obj)
                    except json.JSONDecodeError:
                        pass
                    start = None
        if objects:
            return objects
    except Exception:
        pass

    # Strategy 3: full json.loads fallback
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return parsed
    except (json.JSONDecodeError, ValueError):
        pass

    return []

# ---------------------------------------------------------------------------
# Single-file processing
# ---------------------------------------------------------------------------

def _process_single_file(uploaded_file) -> tuple:
    filename = uploaded_file.name
    pdf_bytes = uploaded_file.read()

    file_hash = hashlib.md5(pdf_bytes).hexdigest()
    if file_hash in _file_cache:
        return filename, _file_cache[file_hash], "cached"

    markdown_text = _pdf_to_markdown(pdf_bytes)
    doc_type = _detect_doc_type(filename, markdown_text)
    prompt = _get_extraction_prompt(doc_type, markdown_text)

    llm_output = invoke_llm(prompt, max_new_tokens=4096)
    raw_rows = _parse_json_from_llm(llm_output)
    rows = _normalize_expenses(raw_rows, filename, markdown_text)

    debug_info = (
        "doc_type=" + doc_type
        + " | markdown_chars=" + str(len(markdown_text))
        + " | raw_rows=" + str(len(raw_rows))
        + " | normalized=" + str(len(rows))
    )

    _file_cache[file_hash] = rows
    return filename, rows, debug_info

# ---------------------------------------------------------------------------
# Public: process_invoices
# ---------------------------------------------------------------------------

def process_invoices(uploaded_files, max_workers: int = 2, progress_callback=None):
    all_rows = []
    debug_info = {}
    total = len(uploaded_files)
    completed = 0

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_map = {
            executor.submit(_process_single_file, f): f.name
            for f in uploaded_files
        }
        for future in as_completed(future_map):
            fname = future_map[future]
            try:
                filename, rows, dbg = future.result()
                if len(rows) == 0:
                    debug_info[filename] = "ERROR: 0 rows extracted — " + dbg
                else:
                    debug_info[filename] = dbg
                    all_rows.extend(rows)
            except Exception as exc:
                debug_info[fname] = "ERROR: " + str(exc)

            completed += 1
            if progress_callback:
                progress_callback(completed, total, fname)

    if not all_rows:
        empty_df = pd.DataFrame(
            columns=["Date", "Vendor", "Doc Type", "Category", "Description", "Currency", "Amount", "Confidence"]
        )
        return empty_df, debug_info

    df = pd.DataFrame(all_rows)
    df = df.rename(columns={
        "date": "Date",
        "vendor": "Vendor",
        "doc_type": "Doc Type",
        "category": "Category",
        "description": "Description",
        "currency": "Currency",
        "amount": "Amount",
        "confidence": "Confidence",
    })
    df = df[["Date", "Vendor", "Doc Type", "Category", "Description", "Currency", "Amount", "Confidence"]]
    return df, debug_info

# ---------------------------------------------------------------------------
# Public: analyze_invoices
# ---------------------------------------------------------------------------

_CATEGORY_COLORS = {
    "Office Supplies": "#3B82F6",
    "Equipment": "#A855F7",
    "Services": "#10B981",
    "Utilities": "#F59E0B",
}

_TRANSPARENT = "rgba(0,0,0,0)"
_FONT = dict(family="Inter, sans-serif", color="#1f2328")


def analyze_invoices(df, budgets: dict = None):
    if budgets is None:
        budgets = {"Office Supplies": 0, "Equipment": 0, "Services": 0, "Utilities": 0}

    base_layout = dict(
        font=_FONT,
        plot_bgcolor=_TRANSPARENT,
        paper_bgcolor=_TRANSPARENT,
    )

    # --- Figure 1: Horizontal bar chart — total by vendor ---
    vendor_totals = df.groupby("Vendor")["Amount"].sum().sort_values(ascending=True)
    fig1 = go.Figure(
        go.Bar(
            x=vendor_totals.values,
            y=vendor_totals.index.tolist(),
            orientation="h",
            marker_color="#3B82F6",
        )
    )
    fig1.update_layout(
        **base_layout,
        xaxis=dict(title="Total Amount"),
        yaxis=dict(title="Vendor"),
        title="Total Expenses by Vendor",
    )

    # --- Figure 2: Donut chart — expenses by category ---
    category_totals = df.groupby("Category")["Amount"].sum()
    fig2 = go.Figure(
        go.Pie(
            labels=category_totals.index.tolist(),
            values=category_totals.values,
            hole=0.4,
        )
    )
    fig2.update_layout(
        **base_layout,
        title="Expenses by Category",
    )

    # --- Figure 3: Bar chart — expenses by document type ---
    doc_type_totals = df.groupby("Doc Type")["Amount"].sum()
    bar_colors = [_CATEGORY_COLORS.get(dt, "#3B82F6") for dt in doc_type_totals.index]
    fig3 = go.Figure(
        go.Bar(
            x=doc_type_totals.index.tolist(),
            y=doc_type_totals.values,
            marker_color=bar_colors,
        )
    )
    fig3.update_layout(
        **base_layout,
        xaxis=dict(title="Document Type"),
        yaxis=dict(title="Total Amount"),
        title="Expenses by Document Type",
    )

    # --- Figure 4: Grouped bar chart — Budget vs Actual ---
    categories = ["Office Supplies", "Equipment", "Services", "Utilities"]
    actuals = []
    budget_vals = []
    actual_colors = []
    border_colors = []

    for cat in categories:
        actual = float(df[df["Doc Type"] == cat]["Amount"].sum()) if "Doc Type" in df.columns else 0.0
        actuals.append(actual)
        budget_vals.append(float(budgets.get(cat, 0)))
        actual_colors.append(_CATEGORY_COLORS.get(cat, "#3B82F6"))
        border_colors.append(_CATEGORY_COLORS.get(cat, "#3B82F6"))

    fig4 = go.Figure()
    fig4.add_trace(go.Bar(
        name="Actual",
        x=categories,
        y=actuals,
        marker_color=actual_colors,
        offsetgroup=0,
    ))
    fig4.add_trace(go.Bar(
        name="Budget",
        x=categories,
        y=budget_vals,
        marker=dict(
            color="rgba(0,0,0,0.15)",
            line=dict(color=border_colors, width=2),
        ),
        offsetgroup=0,
    ))
    fig4.update_layout(
        **base_layout,
        barmode="overlay",
        xaxis=dict(title="Category"),
        yaxis=dict(title="Amount"),
        title="Budget vs Actual by Category",
        legend=dict(
            orientation="h",
            y=1.1,
        ),
    )

    return fig1, fig2, fig3, fig4
