import os
import json
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI
from docx import Document
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
import markdown2

from scraper import fetch_website_links, fetch_website_contents

# Load env
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

api_key = os.getenv("OPENROUTER_API_KEY")
if not api_key:
    raise ValueError("OPENROUTER_API_KEY is not set in .env")

# OpenRouter client
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=api_key,
)

LINK_MODEL = "tngtech/deepseek-r1t2-chimera:free"
BROCHURE_MODEL = "tngtech/deepseek-r1t2-chimera:free"

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

def select_relevant_links(url: str) -> dict:
    response = client.chat.completions.create(
        model=LINK_MODEL,
        messages=[
            {"role": "system", "content": link_system_prompt},
            {"role": "user", "content": get_links_user_prompt(url)},
        ],
        response_format={"type": "json_object"},
    )
    result = response.choices[0].message.content
    links = json.loads(result)
    return links

def fetch_page_and_all_relevant_links(url: str) -> str:
    contents = fetch_website_contents(url)
    relevant_links = select_relevant_links(url)
    result = f"## Landing Page:\n\n{contents}\n## Relevant Links:\n"
    for link in relevant_links["links"]:
        result += f"\n\n### Link: {link['type']}\n"
        result += fetch_website_contents(link["url"])
    return result

def get_brochure_user_prompt(company_name: str, url: str) -> str:
    user_prompt = f"""
You are looking at a company called: {company_name}
Here are the contents of its landing page and other relevant pages;
use this information to build a short brochure of the company in markdown without code blocks.\n\n
"""
    user_prompt += fetch_page_and_all_relevant_links(url)
    user_prompt = user_prompt[:5000]  # truncate
    return user_prompt

def create_brochure_text(company_name: str, url: str) -> str:
    response = client.chat.completions.create(
        model=BROCHURE_MODEL,
        messages=[
            {"role": "system", "content": brochure_system_prompt},
            {"role": "user", "content": get_brochure_user_prompt(company_name, url)},
        ],
    )
    return response.choices[0].message.content

# ---------- Export helpers ----------

def save_as_docx(text: str, filename: Path) -> Path:
    doc = Document()
    for line in text.split("\n"):
        doc.add_paragraph(line)
    doc.save(str(filename))
    return filename

def save_as_pdf(text: str, filename: Path) -> Path:
    c = canvas.Canvas(str(filename), pagesize=letter)
    width, height = letter
    y = height - 40

    for line in text.split("\n"):
        if y < 40:
            c.showPage()
            y = height - 40
        c.drawString(40, y, line[:120])
        y -= 18

    c.save()
    return filename

def save_as_html(text: str, filename: Path) -> Path:
    html = markdown2.markdown(text)
    with open(filename, "w", encoding="utf-8") as f:
        f.write(html)
    return filename

def generate_brochure(company_name: str, url: str, formats=None, output_dir: Path | None = None):
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

    text = create_brochure_text(company_name, url)

    file_paths = {}
    base = output_dir / company_name.lower().replace(" ", "_")

    if "pdf" in formats:
        file_paths["pdf"] = save_as_pdf(text, base.with_suffix(".pdf"))
    if "docx" in formats:
        file_paths["docx"] = save_as_docx(text, base.with_suffix(".docx"))
    if "html" in formats:
        file_paths["html"] = save_as_html(text, base.with_suffix(".html"))

    return text, file_paths
