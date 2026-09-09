# The Polite Scraper
 
A small scraping pipeline that downloads the first 3 catalogue pages of
[Books to Scrape](https://books.toscrape.com), visits all 60 book pages,
and turns the messy HTML into clean, validated JSON records.
 
## Target classification
 
- **Site:** [books.toscrape.com](https://books.toscrape.com)
- **Why:** Books to Scrape is a public sandbox explicitly built for people to
  practice web scraping on. It exists for exactly this purpose.
- **Scope:** the first 3 catalogue pages only (60 books total) — no further
  pagination, no other sections of the site.
- **robots.txt result:** `https://books.toscrape.com/robots.txt` returns a
  404. No robots file was found. A missing file is not permission — it is
  simply the absence of a stated rule — so this project stays within the
  documented scope above regardless.
- **Data collected:** book title, price, availability, star rating,
  description, and product URL — all publicly rendered on each book's own
  page, nothing behind a login or paywall.
I will not reuse this code on another site without checking its rules and
terms first.
 
## Setup
 
```
pip install requests beautifulsoup4 pydantic
```
 
## Run
 
```
cd src
python main.py
```
 
Outputs are written to `../output/`:
- `books.json` — validated records
- `errors.json` — records that failed validation, with reasons
- `run-report.json` — counts and timing for the run
Running the script twice produces the same 60 records (no duplicates) and
mostly reads from `cache/` on the second run.
 
## Record schema
 
```json
{
  "title": "string",
  "product_url": "https url — canonical identity of the record",
  "price_text": "string, original e.g. '£51.77'",
  "price_gbp": "number, normalized from price_text",
  "availability_text": "string",
  "rating_text": "string, e.g. 'Three'",
  "rating_value": "integer 0-5, normalized from rating_text",
  "description": "string or null — null when the page has none",
  "source_page": "https url of the catalogue page this book was found on",
  "fetched_at": "ISO 8601 UTC timestamp"
}
```
 
## Politeness rules
 
- Every real request sends an identifying `User-Agent`:
  `FlyRankInternshipA9/1.0 (+link-to-repo)`.
- Every request has a 10-second timeout.
- At least 500ms delay between real (non-cached) requests.
- Every response's status code is checked before use — only `200` is parsed.
- `5xx` and timeouts are retried (twice, with backoff); `404`/`403` are never
  retried.
- All pages are cached to disk on first fetch; subsequent runs read from
  cache instead of re-requesting.
## Failure handling
 
One broken page does not take down the run. A deliberately fake URL is
included in each run to prove this: it's logged as a failed page, and the
other 60 valid records are still written to `books.json`. See the sample
`run-report.json` below.
 
## Sample run report
 
```json
{
  "started_at": "2026-09-08T12:00:00+00:00",
  "duration_seconds": 48.3,
  "catalogue_pages": 3,
  "book_urls_discovered": 61,
  "pages_fetched": 61,
  "cache_hits": 0,
  "valid_records": 60,
  "invalid_records": 0,
  "failed_pages": 1,
  "failed_page_details": [
    {
      "url": "https://books.toscrape.com/catalogue/this-book-does-not-exist_9999/index.html",
      "status": 404
    }
  ]
}
```
 
## Why no browser was needed
 
All the data used here — title, price, availability, rating, description —
is already present in the raw HTML the server sends back on first request.
Nothing is loaded client-side via JavaScript. Using a full browser (e.g.
Playwright) would only add startup cost and memory overhead with no benefit
for this particular site.
 
## Ethics note
 
This project only touches a site explicitly built for scraping practice.
In general: use an official API when one exists, never bypass logins,
paywalls, or explicit blocks, and only collect the data actually needed —
don't scrape more than the task requires.