#!/usr/bin/env python3
"""
Exports scraped reviews and companies from vidhuk_full.db to JSONL or CSV.
"""
import sqlite3
import json
import csv
import sys
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'vidhuk_full.db')

def export_jsonl(output_path='vidhuk_reviews_export.jsonl'):
    if not os.path.exists(DB_PATH):
        print("Database not found:", DB_PATH)
        return
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
    SELECT r.id, c.name, r.company_slug, r.review_type, r.author, r.rating, r.date, r.title, r.text, r.url
    FROM reviews r
    LEFT JOIN companies c ON r.company_slug = c.slug
    ORDER BY r.id
    """)
    count = 0
    with open(output_path, 'w', encoding='utf-8') as f:
        for row in cur:
            item = {
                'id': row[0],
                'company_name': row[1] or row[2],
                'company_slug': row[2],
                'type': row[3],
                'author': row[4],
                'rating': row[5],
                'date': row[6],
                'title': row[7],
                'text': row[8],
                'url': row[9]
            }
            f.write(json.dumps(item, ensure_ascii=False) + '\n')
            count += 1
    conn.close()
    print(f"Exported {count} reviews to {output_path}")

def status():
    if not os.path.exists(DB_PATH):
        print("Database does not exist yet.")
        return
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT count(*) FROM companies")
    comps = cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM reviews")
    revs = cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM progress WHERE status = 'done'")
    done = cur.fetchone()[0]
    conn.close()
    print(f"Status: {comps} companies, {revs} reviews collected, {done} URLs processed.")

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'status':
        status()
    else:
        export_jsonl()
