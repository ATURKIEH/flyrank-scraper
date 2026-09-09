import json
import os
import re
import time
from datetime import datetime, timezone
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from pydantic import BaseModel, HttpUrl, ValidationError


BASE_URL = "https://books.toscrape.com/"
CATALOGUE_START = urljoin(BASE_URL, "catalogue/page-1.html")
USER_AGENT = "FlyRankInternshipA9/1.0 (+https://github.com/your-username/your-repo)"
TIMEOUT = 10
DELAY_BETWEEN_REQUESTS = 0.6
MAX_RETRIES = 2

CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "cache")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "output")

os.makedirs(CACHE_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

RATING_WORDS = {"One": 1, "Two": 2, "Three": 3, "Four": 4, "Five": 5}


def _cache_path_for(url: str) -> str:
    safe_name = re.sub(r"[^a-zA-Z0-9]+", "_", url).strip("_")
    return os.path.join(CACHE_DIR, f"{safe_name}.html")


def fetch(url: str, allow_retry: bool = True):
    cache_path = _cache_path_for(url)

    if os.path.exists(cache_path):
        with open(cache_path, "r", encoding="utf-8") as f:
            html = f.read()
        print(f"CACHE HIT  {url}  ({len(html)} bytes)")
        return html, 200

    attempts = 0
    while True:
        attempts += 1
        try:
            resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
        except requests.exceptions.RequestException as e:
            print(f"FETCH ERROR {url}: {e}")
            if allow_retry and attempts <= MAX_RETRIES:
                time.sleep(1.5 * attempts)
                continue
            return None, None

        if resp.status_code == 200:
            with open(cache_path, "w", encoding="utf-8") as f:
                f.write(resp.text)
            print(f"FETCH      {url}  ({len(resp.text)} bytes)")
            time.sleep(DELAY_BETWEEN_REQUESTS)
            return resp.text, 200

        if resp.status_code >= 500 and allow_retry and attempts <= MAX_RETRIES:
            print(f"FETCH {resp.status_code}, retrying: {url}")
            time.sleep(1.5 * attempts)
            continue

        print(f"FETCH FAILED {resp.status_code}: {url}")
        time.sleep(DELAY_BETWEEN_REQUESTS)
        return None, resp.status_code



def discover_book_urls():
    urls = []
    page_url = CATALOGUE_START
    pages_visited = 0

    while page_url and pages_visited < 3:
        html, status = fetch(page_url)
        pages_visited += 1
        if html is None:
            break

        soup = BeautifulSoup(html, "html.parser")

        for h3 in soup.select("article.product_pod h3 a"):
            href = h3.get("href")
            absolute = urljoin(page_url, href)
            urls.append(absolute)

        next_link = soup.select_one("li.next a")
        page_url = urljoin(page_url, next_link.get("href")) if next_link else None

    unique_urls = list(dict.fromkeys(urls))
    print(f"catalogue_pages={pages_visited} discovered={len(urls)} unique_urls={len(unique_urls)}")
    return unique_urls