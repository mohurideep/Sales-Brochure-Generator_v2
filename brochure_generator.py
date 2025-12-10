import os
import json
from pathlib import Path
import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI
from docx import Document
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
import markdown2
from groq import Groq

from scraper import fetch_website_links, fetch_website_contents,extract_logo_and_color

# Load env
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

# API KEYS
openrouter_key = os.getenv("OPENROUTER_API_KEY") or st.secrets.get("OPENROUTER_API_KEY")
if not openrouter_key:
    raise ValueError("OPENROUTER_API_KEY missing")

groq_key = os.getenv("GROQ_API_KEY") or st.secrets.get("GROQ_API_KEY")
if not groq_key:
    raise ValueError("GROQ_API_KEY missing")

# Clients
openrouter_client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=openrouter_key)
groq_client = Groq(api_key=groq_key)


# ---------------- AVAILABLE MODELS (with provider) ----------------
# (model_id, provider_used)
FREE_MODELS = {
    "DeepSeek R1-Chimera 🟢 Best Choice": ("tngtech/deepseek-r1t2-chimera:free", "openrouter"),
    "Qwen 3 A22B Large 🟡": ("qwen/qwen3-235b-a22b:free", "openrouter"),
    "Llama 3 Instruct ❗ Slow Free Tier": ("meta-llama/llama-3.3-70b-instruct:free", "openrouter"),
    "Mistral Instruct ⚡ Fast": ("mistralai/mistral-7b-instruct:free", "openrouter"),

    # GROQ MODELS
    "GPT-OSS ⚡ (Groq)": ("openai/gpt-oss-120b", "groq")
}
FALLBACK_MODEL = ("tngtech/deepseek-r1t2-chimera:free", "openrouter")

link_system_prompt = """
You are provided with a list of links found on a webpage.
You are able to decide which of the links would be most relevant to include in a brochure about the company,
such as links to an About page, or a Company page, or Careers/Jobs pages.
You should respond in JSON as in this example:

{
    "links": [
        {"type": "about page", "url": "https://full.url/goes/here/about"},
        {"type": "careers page", "url": "https://another.full.url/careers"}
    ]
}
"""

brochure_system_prompt = """
You are an assistant that analyzes the contents of several relevant pages from a company website
and creates a short brochure about the company for prospective customers, investors and recruits.
Respond in markdown without code blocks.
Include details of company culture, customers and careers/jobs if you have the information.
"""

def llm_stream(model_id, provider, messages):
    """Stream output token-by-token."""
    
    # ---- GROQ Streaming ----
    if provider == "groq":
        return groq_client.chat.completions.create(
            model=model_id,
            messages=messages,
            temperature=0.3,
            stream=True
        )

    # ---- OpenRouter Streaming ----
    return openrouter_client.chat.completions.create(
        model=model_id,
        messages=messages,
        stream=True
    )


def llm_chat(model_id, provider, messages, response_format=None):
    """Unified call → routes to Groq or OpenRouter automatically"""

    if provider == "groq":
        return groq_client.chat.completions.create(
            model=model_id,
            messages=messages,
            temperature=0.3
        )
    
    return openrouter_client.chat.completions.create(
        model=model_id,
        messages=messages,
        response_format=response_format   # only OpenRouter supports this currently
    )

def get_links_user_prompt(url: str) -> str:
    user_prompt = f"""
    Here is the list of links on the website {url} -
    Please decide which of these are relevant web links for a brochure about the company, 
    respond with the full https URL in JSON format.
    Do not include Terms of Service, Privacy, email links.

Links (some might be relative links):

"""
    links = fetch_website_links(url)
    user_prompt += "\n".join(links)
    return user_prompt

def select_relevant_links(url: str, model_pack):
    model_id, provider = model_pack
    response = llm_chat(
        model_id, provider,
        messages=[
            {"role": "system", "content": link_system_prompt},
            {"role": "user", "content": get_links_user_prompt(url)},
        ],
        response_format={"type": "json_object"} if provider!="groq" else None
    )
    return json.loads(response.choices[0].message.content)

def fetch_page_and_all_relevant_links(url: str, model_name: str) -> str:
    contents = fetch_website_contents(url)
    relevant_links = select_relevant_links(url,model_name)
    result = f"## Landing Page:\n\n{contents}\n## Relevant Links:\n"
    for link in relevant_links["links"]:
        result += f"\n\n### Link: {link['type']}\n"
        result += fetch_website_contents(link["url"])
    return result

def get_brochure_user_prompt(company_name: str, url: str,model_pack):
    user_prompt = f"""
You are looking at a company called: {company_name}
Here are the contents of its landing page and other relevant pages;
use this information to build a short brochure of the company in markdown without code blocks.\n\n
"""
    user_prompt += fetch_page_and_all_relevant_links(url,model_pack)
    user_prompt = user_prompt[:5_000] # Truncate if more than 5,000 characters
    return user_prompt

def create_brochure_text(company_name: str, url: str, model_pack) :
    model_id, provider = model_pack
    response = llm_chat(
        model_id, provider,
        messages=[
            {"role": "system", "content": brochure_system_prompt},
            {"role": "user", "content": get_brochure_user_prompt(company_name, url,model_pack)},
        ],
    )
    return response.choices[0].message.content

def stream_brochure_text(company_name: str, url: str, model_pack):
    """
    Streams brochure text from the LLM.
    Yields the *full* text so far on every token chunk.
    """
    model_id, provider = model_pack

    messages = [
        {"role": "system", "content": brochure_system_prompt},
        {"role": "user", "content": get_brochure_user_prompt(company_name, url, model_pack)},
    ]

    stream = llm_stream(model_id, provider, messages)

    full_text = ""
    for chunk in stream:
        # Both Groq and OpenRouter are OpenAI-compatible here
        delta = chunk.choices[0].delta
        part = delta.content or ""
        if part:
            full_text += part
            yield full_text  # progressively larger text

# ---------- Export helpers ----------

def save_as_docx(text: str, filename: Path) -> Path:
    doc = Document()
    for line in text.split("\n"):
        doc.add_paragraph(line)
    doc.save(str(filename))
    return filename

def save_as_pdf(text: str, filename: Path, logo_url=None, brand_color="#000000") -> Path:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.utils import ImageReader
    import requests
    from io import BytesIO

    c = canvas.Canvas(str(filename), pagesize=letter)
    width, height = letter

    # --- Brand Header Banner ---
    c.setFillColor(brand_color)
    c.rect(0, height - 80, width, 80, fill=1, stroke=0)

    # --- Logo on top banner ---
    if logo_url:
        try:
            img = ImageReader(BytesIO(requests.get(logo_url).content))
            c.drawImage(img, 30, height - 70, width=70, preserveAspectRatio=True, mask='auto')
        except:
            pass

    # Title
    c.setFillColor("white")
    c.setFont("Helvetica-Bold", 22)
    c.drawString(120, height - 50, "Company Brochure")

    # Write content below
    c.setFillColor("black")
    c.setFont("Helvetica", 10)

    y = height - 120
    for line in text.split("\n"):
        if y < 50:
            c.showPage()
            y = height - 60
        c.drawString(40, y, line[:120])
        y -= 16

    c.save()
    return filename

def save_as_html(text: str, filename: Path, logo_url=None, brand_color="#000000") -> Path:
    html = f"""
    <html>
    <head>
        <style>
            body {{ font-family: Arial; margin: 40px; }}
            h1 {{ color: {brand_color}; }}
            h2, h3 {{ color: {brand_color}; }}
            .header {{
                background: {brand_color};
                padding: 20px;
                color: white;
                display:flex;
                align-items:center;
            }}
            .header img {{ height:60px; margin-right:20px; }}
        </style>
    </head>
    <body>
        <div class="header">
            {'<img src="'+logo_url+'">' if logo_url else ""}
            <h1>Company Brochure</h1>
        </div>
        <div>{markdown2.markdown(text)}</div>
    </body>
    </html>
    """

    with open(filename, "w", encoding="utf-8") as f:
        f.write(html)
    return filename


def generate_brochure(company_name: str, url: str, model_pack, formats=None, output_dir: Path | None = None,precomputed_text: str | None = None):
    """
    End-to-end pipeline:
      - scrapes + selects links
      - generates brochure text
      - saves to requested formats
    Returns: (brochure_text, dict of {format: file_path})
    """
    if formats is None:
        formats = ["pdf", "docx", "html"]

    if output_dir is None:
        output_dir = BASE_DIR / "output"
    output_dir.mkdir(exist_ok=True)

    # try:
    #     text = create_brochure_text(company_name, url, model_pack)
    # except Exception as e:
    #     # Auto fallback if model rate-limited or fails
    #     st.warning(f"{model_pack} failed due to: {e}\nSwitching to fallback model.")
    #     text = create_brochure_text(company_name, url, FALLBACK_MODEL)
    if precomputed_text is not None:
        # We already streamed the text in the UI – reuse it
        text = precomputed_text
    else:
        try:
            text = create_brochure_text(company_name, url, model_pack)
        except Exception as e:
            # Auto fallback if model rate-limited or fails
            st.warning(f"{model_pack} failed due to: {e}\nSwitching to fallback model.")
            text = create_brochure_text(company_name, url, FALLBACK_MODEL)

    # ------- Extract branding visual elements -------
    logo_url, brand_color = extract_logo_and_color(url)
    st.write(f"🎨 Brand Color Detected: {brand_color}")
    if logo_url:
        st.image(logo_url, caption="Company Logo", width=200)
    else:
        st.warning("No company logo detected — continuing without logo")
    # ------- Save to requested formats -------
    file_paths = {}
    base = output_dir / company_name.lower().replace(" ", "_")

    if "pdf" in formats:
        file_paths["pdf"] = save_as_pdf(text, base.with_suffix(".pdf"), logo_url, brand_color)
    if "docx" in formats:
        file_paths["docx"] = save_as_docx(text, base.with_suffix(".docx"))  # DOCX plain for now
    if "html" in formats:
        file_paths["html"] = save_as_html(text, base.with_suffix(".html"), logo_url, brand_color)

    return text, file_paths
