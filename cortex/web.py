"""
Cortex Web — fetch and extract text from URLs.

Used by the daemon to inject real web content into tasks.
"""

import re
import requests
from typing import Optional


def fetch_url(url: str, timeout: int = 15) -> Optional[str]:
    """Fetch a URL and return cleaned text content."""
    try:
        headers = {"User-Agent": "Cortex/1.0"}
        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()

        content_type = response.headers.get("content-type", "")

        if "text/html" in content_type:
            return _extract_text_from_html(response.text)
        elif "application/json" in content_type:
            return response.text[:5000]
        else:
            return response.text[:5000]
    except Exception as e:
        return f"[Error fetching {url}: {e}]"


def _extract_text_from_html(html_content: str) -> str:
    """Strip HTML tags and extract readable text."""
    # Remove script and style blocks
    text = re.sub(r'<script[^>]*>.*?</script>', '', html_content, flags=re.DOTALL)
    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', ' ', text)
    # Clean up whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    # Limit length
    return text[:5000]


def extract_urls(text: str) -> list:
    """Find all URLs in a text string."""
    return re.findall(r'https?://[^\s<>"\']+', text)
