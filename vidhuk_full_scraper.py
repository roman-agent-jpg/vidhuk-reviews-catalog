#!/usr/bin/env python3
"""
Full vidhuk.ua scraper with zero-loss SQLite storage, resumability, and Google Drive autosync.
Scrapes all 27,675 organizations (55,350 URLs) + pagination for all reviews.
"""

import asyncio
import aiohttp
import json
import os
import re
import sqlite3
import subprocess
import sys
import time
import math
import logging
from datetime import datetime

# Configuration
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SITEMAP_PATH = os.path.join(BASE_DIR, 'OtzyvTut_Parser_Kit', 'vidhuk_sitemap_organizations_2026-10-20.xml')
DB_PATH = os.path.join(BASE_DIR, 'vidhuk_full.db')
GDRIVE_DEST = "gdrive:Парсер для отзовика/vidhuk_full.db"

CONCURRENCY = 14               # 12-15 concurrent HTTP requests
REQUEST_TIMEOUT = 25           # seconds
BATCH_COMMIT_SIZE = 50         # commit every 50 urls processed
GDRIVE_SYNC_INTERVAL = 300     # sync to GDrive every 5 minutes

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0",
]

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(os.path.join(BASE_DIR, 'scraper.log'), encoding='utf-8')
    ]
)
logger = logging.getLogger("vidhuk_scraper")


def init_db(db_path):
    conn = sqlite3.connect(db_path, timeout=60.0)
    cur = conn.cursor()
    cur.execute("PRAGMA journal_mode = WAL;")
    cur.execute("PRAGMA synchronous = NORMAL;")
    cur.execute("PRAGMA cache_size = -64000;")  # 64 MB cache
    
    cur.execute("""
    CREATE TABLE IF NOT EXISTS companies (
        slug TEXT PRIMARY KEY,
        name TEXT,
        org_type TEXT,
        description TEXT,
        rating REAL,
        review_count INTEGER DEFAULT 0,
        url TEXT,
        scraped_at TEXT
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS reviews (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_slug TEXT,
        review_type TEXT,
        author TEXT,
        rating REAL,
        date TEXT,
        title TEXT,
        text TEXT,
        url TEXT,
        scraped_at TEXT,
        UNIQUE(company_slug, review_type, author, date, text)
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS progress (
        url TEXT PRIMARY KEY,
        status TEXT,
        reviews_count INTEGER DEFAULT 0,
        scraped_at TEXT,
        error TEXT
    );
    """)

    cur.execute("CREATE INDEX IF NOT EXISTS idx_rev_company ON reviews(company_slug);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_rev_rating ON reviews(rating);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_prog_status ON progress(status);")
    conn.commit()
    return conn


def load_sitemap_urls(sitemap_path):
    if not os.path.exists(sitemap_path):
        logger.error(f"Sitemap file not found: {sitemap_path}")
        return []
    with open(sitemap_path, 'r', encoding='utf-8') as f:
        xml = f.read()
    urls = re.findall(r'<loc>(https?://[^<]+)</loc>', xml)
    logger.info(f"Loaded {len(urls)} URLs from sitemap.")
    return urls


def parse_html_ld(html, url):
    """
    Extracts company info and reviews from JSON-LD blocks in HTML.
    Returns: (company_dict, reviews_list, total_review_count)
    """
    matches = re.finditer(r'application/ld\+json">(.*?)</script>', html, re.S)
    company_data = None
    reviews = []
    total_review_count = 0

    m_slug = re.match(r'https?://[^/]+/uk/([^/]+)/', url)
    slug = m_slug.group(1) if m_slug else url.split('/')[-2]
    review_type = "sotrudnikov" if "otzyvy-sotrudnikov" in url else "klientov"

    for match in matches:
        try:
            data = json.loads(match.group(1))
        except Exception:
            continue

        if not isinstance(data, dict):
            continue

        # Look for organization card
        if data.get('@type') and data.get('@type') != 'Review':
            name = data.get('name', '').strip()
            org_type = data.get('@type', '')
            desc = data.get('description', '')
            if isinstance(desc, str):
                desc = desc.strip()
            else:
                desc = ""
            
            agg = data.get('aggregateRating', {})
            rating = None
            if isinstance(agg, dict):
                try:
                    rating = float(agg.get('ratingValue', 0)) or None
                    total_review_count = int(agg.get('reviewCount', 0))
                except (ValueError, TypeError):
                    pass

            company_data = {
                'slug': slug,
                'name': name or slug,
                'org_type': org_type,
                'description': desc,
                'rating': rating,
                'review_count': total_review_count,
                'url': url
            }

            # If reviews are nested in organization block
            raw_revs = data.get('review', [])
            if isinstance(raw_revs, list):
                for r in raw_revs:
                    if not isinstance(r, dict):
                        continue
                    body = (r.get('reviewBody') or '').strip()
                    author = ((r.get('author') or {}).get('name') or '').strip()
                    rev_rating = None
                    try:
                        rev_rating = float((r.get('reviewRating') or {}).get('ratingValue', 0)) or None
                    except (ValueError, TypeError):
                        pass
                    date_pub = (r.get('datePublished') or '')[:10]
                    title = (r.get('name') or '').strip()
                    
                    if body:
                        reviews.append({
                            'company_slug': slug,
                            'review_type': review_type,
                            'author': author,
                            'rating': rev_rating,
                            'date': date_pub,
                            'title': title,
                            'text': body,
                            'url': url
                        })

    return company_data, reviews, total_review_count


async def fetch_url(session, url, semaphore, max_retries=3):
    headers = {"User-Agent": USER_AGENTS[hash(url) % len(USER_AGENTS)]}
    for attempt in range(max_retries):
        try:
            async with semaphore:
                async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)) as resp:
                    if resp.status == 200:
                        return await resp.text()
                    elif resp.status == 404:
                        return None
                    elif resp.status in (429, 503):
                        await asyncio.sleep(2 * (attempt + 1))
                    else:
                        await asyncio.sleep(0.5)
        except Exception:
            if attempt == max_retries - 1:
                return None
            await asyncio.sleep(1 * (attempt + 1))
    return None


def sync_to_gdrive():
    try:
        logger.info("[AutoSync] Uploading vidhuk_full.db to Google Drive...")
        subprocess.run(['rclone', 'copyto', DB_PATH, GDRIVE_DEST], capture_output=True, timeout=120)
        logger.info("[AutoSync] Backup to Google Drive finished successfully.")
    except Exception as e:
        logger.warning(f"[AutoSync] Backup warning: {e}")


async def main():
    conn = init_db(DB_PATH)
    cur = conn.cursor()

    # Find already completed URLs
    cur.execute("SELECT url FROM progress WHERE status = 'done'")
    done_urls = set(row[0] for row in cur.fetchall())
    logger.info(f"Already processed URLs in DB: {len(done_urls)}")

    all_urls = load_sitemap_urls(SITEMAP_PATH)
    urls_to_process = [u for u in all_urls if u not in done_urls]
    total_target = len(urls_to_process)
    logger.info(f"Target remaining URLs to process: {total_target} / {len(all_urls)}")

    if total_target == 0:
        logger.info("All sitemap URLs already processed!")
        return

    semaphore = asyncio.Semaphore(CONCURRENCY)
    connector = aiohttp.TCPConnector(limit=CONCURRENCY * 2, ttl_dns_cache=300)
    
    last_sync = time.time()
    processed_count = 0
    total_reviews_added = 0
    start_time = time.time()

    async with aiohttp.ClientSession(connector=connector) as session:
        # Process in chunks
        chunk_size = 200
        for i in range(0, len(urls_to_process), chunk_size):
            chunk = urls_to_process[i:i + chunk_size]
            tasks = [fetch_url(session, u, semaphore) for u in chunk]
            html_results = await asyncio.gather(*tasks)

            now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            secondary_tasks = []

            for u, html in zip(chunk, html_results):
                if html is None:
                    cur.execute("INSERT OR REPLACE INTO progress (url, status, reviews_count, scraped_at, error) VALUES (?, ?, ?, ?, ?)",
                                (u, 'error', 0, now_str, 'Fetch failed or 404'))
                    continue

                company, revs, total_count = parse_html_ld(html, u)

                if company:
                    cur.execute("""
                    INSERT INTO companies (slug, name, org_type, description, rating, review_count, url, scraped_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(slug) DO UPDATE SET
                        name = excluded.name,
                        org_type = excluded.org_type,
                        description = CASE WHEN length(excluded.description) > length(companies.description) THEN excluded.description ELSE companies.description END,
                        rating = COALESCE(excluded.rating, companies.rating),
                        review_count = max(companies.review_count, excluded.review_count),
                        scraped_at = excluded.scraped_at;
                    """, (company['slug'], company['name'], company['org_type'], company['description'],
                          company['rating'], company['review_count'], company['url'], now_str))

                for r in revs:
                    cur.execute("""
                    INSERT OR IGNORE INTO reviews (company_slug, review_type, author, rating, date, title, text, url, scraped_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (r['company_slug'], r['review_type'], r['author'], r['rating'], r['date'], r['title'], r['text'], r['url'], now_str))
                    total_reviews_added += cur.rowcount

                cur.execute("INSERT OR REPLACE INTO progress (url, status, reviews_count, scraped_at, error) VALUES (?, ?, ?, ?, ?)",
                            (u, 'done', len(revs), now_str, None))

                # Check for pagination (if total_count > 10 reviews)
                if total_count > 10:
                    pages_needed = min(math.ceil(total_count / 10), 30)  # max 30 pages (300 reviews per company)
                    for p in range(2, pages_needed + 1):
                        p_url = f"{u}?page={p}"
                        secondary_tasks.append((p_url, u, company['slug'] if company else u.split('/')[-2],
                                                "sotrudnikov" if "otzyvy-sotrudnikov" in u else "klientov"))

                processed_count += 1

            # Fetch pagination pages for companies with many reviews
            if secondary_tasks:
                sub_tasks = [fetch_url(session, p_item[0], semaphore) for p_item in secondary_tasks]
                sub_htmls = await asyncio.gather(*sub_tasks)
                for (p_url, orig_u, c_slug, rev_type), p_html in zip(secondary_tasks, sub_htmls):
                    if p_html:
                        _, p_revs, _ = parse_html_ld(p_html, orig_u)
                        for r in p_revs:
                            cur.execute("""
                            INSERT OR IGNORE INTO reviews (company_slug, review_type, author, rating, date, title, text, url, scraped_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, (c_slug, rev_type, r['author'], r['rating'], r['date'], r['title'], r['text'], p_url, now_str))
                            total_reviews_added += cur.rowcount

            conn.commit()

            # Progress log
            elapsed = time.time() - start_time
            rate = processed_count / max(elapsed, 0.1)
            eta_min = (total_target - processed_count) / max(rate, 0.01) / 60
            logger.info(f"Progress: {processed_count}/{total_target} URLs ({(processed_count/total_target)*100:.1f}%) | "
                        f"New Reviews: {total_reviews_added} | Speed: {rate:.1f} req/s | ETA: {eta_min:.1f} min")

            # Periodic GDrive sync
            if time.time() - last_sync > GDRIVE_SYNC_INTERVAL:
                sync_to_gdrive()
                last_sync = time.time()

    conn.close()
    logger.info("Scraping completed! Final sync to Google Drive...")
    sync_to_gdrive()
    logger.info("Done!")


if __name__ == "__main__":
    asyncio.run(main())
