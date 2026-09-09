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


class BookRecord(BaseModel):
    title: str
    product_url: HttpUrl
    price_text: str
    price_gbp: float
    availability_text: str
    rating_text: str
    rating_value: int
    description: str | None
    source_page: HttpUrl
    fetched_at: str


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



def extract_book(url: str, source_page: str):
    html, status = fetch(url)
    if html is None:
        return None, status

    soup = BeautifulSoup(html, "html.parser")
    product_main = soup.select_one("div.product_main")

    title = product_main.find("h1").get_text(strip=True)
    price_text = product_main.select_one("p.price_color").get_text(strip=True)

    availability_el = product_main.select_one("p.availability")
    availability_text = availability_el.get_text(strip=True) if availability_el else ""

    rating_el = product_main.select_one("p.star-rating")
    rating_text = "Zero"
    if rating_el and rating_el.get("class"):
        for c in rating_el.get("class"):
            if c in RATING_WORDS:
                rating_text = c
                break
    desc_heading = soup.select_one("#product_description")
    if desc_heading:
        desc_p = desc_heading.find_next_sibling("p")
        description = desc_p.get_text(strip=True) if desc_p else None
    else:
        description = None

    raw = {
        "title": title,
        "product_url": url,
        "price_text": price_text,
        "availability_text": availability_text,
        "rating_text": rating_text,
        "description": description,
        "source_page": source_page,       # provenance
        "fetched_at": datetime.now(timezone.utc).isoformat(),  # provenance
    }
    return raw, 200


def normalize_and_validate(raw: dict):
    try:
        price_match = re.search(r"[\d.]+", raw["price_text"])
        price_gbp = float(price_match.group()) if price_match else None
        if price_gbp is None:
            return None, "could not parse price_text into a number"

        rating_value = RATING_WORDS.get(raw["rating_text"], 0)

        record = BookRecord(
            title=raw["title"],
            product_url=raw["product_url"],
            price_text=raw["price_text"],
            price_gbp=price_gbp,
            availability_text=raw["availability_text"],
            rating_text=raw["rating_text"],
            rating_value=rating_value,
            description=raw["description"],
            source_page=raw["source_page"],
            fetched_at=raw["fetched_at"],
        )
        return record, None
    except ValidationError as e:
        return None, str(e)
    except Exception as e:
        return None, f"unexpected error: {e}"
