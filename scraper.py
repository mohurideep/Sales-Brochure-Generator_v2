from bs4 import BeautifulSoup
import requests
from urllib.parse import urljoin


# Standard headers to fetch a website
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36"
}


def fetch_website_contents(url):
    """
    Return the title and contents of the website at the given url;
    truncate to 2,000 characters as a sensible limit
    """
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.content, "html.parser")
    title = soup.title.string if soup.title else "No title found"
    if soup.body:
        for irrelevant in soup.body(["script", "style", "img", "input"]):
            irrelevant.decompose()
        text = soup.body.get_text(separator="\n", strip=True)
    else:
        text = ""
    return (title + "\n\n" + text)[:2_000]


def fetch_website_links(url):
    """
    Return the links on the webiste at the given url
    I realize this is inefficient as we're parsing twice! This is to keep the code in the lab simple.
    Feel free to use a class and optimize it!
    """
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.content, "html.parser")
    links = [link.get("href") for link in soup.find_all("a")]
    return [link for link in links if link]


def extract_logo_and_color(url):
    """Extracts logo URL + dominant brand color"""
    try:
        html = requests.get(url, timeout=10).text
        soup = BeautifulSoup(html, "html.parser")

        # Try common logo selectors
        logo = None
        for tag in soup.find_all(["img", "link"]):
            src = tag.get("src") or tag.get("href")
            if src and ("logo" in src.lower() or "icon" in src.lower()):
                logo = urljoin(url, src)
                break

        # Extract main color
        style_tags = soup.find_all("style")
        colors = []
        import re
        for t in style_tags:
            found = re.findall(r'#[0-9A-Fa-f]{6}', t.text)
            colors.extend(found)
        primary_color = colors[0] if colors else "#000000"

        return logo, primary_color

    except:
        return None, "#000000"
