#!/usr/bin/env python3
"""
verify_scraper_dataset.py
-------------------------
Comprehensive dataset integrity verification tool for Vidhuk scraper.
Validates SQLite DB integrity, WAL mode, sitemap coverage (55,350 URLs),
schema compliance, data quality, foreign key relationships, and Google Drive backups.
"""

import argparse
import json
import os
import re
import sqlite3
import subprocess
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

DEFAULT_DB_PATH = "/root/новій отзовик/vidhuk_full.db"
DEFAULT_SITEMAP_PATH = "/root/новій отзовик/OtzyvTut_Parser_Kit/vidhuk_sitemap_organizations_2026-10-20.xml"
DEFAULT_GDRIVE_DEST = "gdrive:Парсер для отзовика/vidhuk_full.db"
EXPECTED_SITEMAP_URLS = 55350


class ScraperVerifier:
    def __init__(
        self,
        db_path=DEFAULT_DB_PATH,
        sitemap_path=DEFAULT_SITEMAP_PATH,
        gdrive_dest=DEFAULT_GDRIVE_DEST,
        allow_in_progress=False,
        skip_gdrive=False,
        json_output=False,
    ):
        self.db_path = os.path.abspath(db_path)
        self.sitemap_path = os.path.abspath(sitemap_path)
        self.gdrive_dest = gdrive_dest
        self.allow_in_progress = allow_in_progress
        self.skip_gdrive = skip_gdrive
        self.json_output = json_output
        self.results = []
        self.failures = 0
        self.sitemap_urls = set()

    def record(self, gate_name, test_name, passed, details=""):
        self.results.append({
            "gate": gate_name,
            "test": test_name,
            "passed": bool(passed),
            "details": str(details),
        })
        if not passed:
            self.failures += 1
        if not self.json_output:
            mark = "✓" if passed else "✗"
            print(f"[{mark}] [{gate_name}] {test_name}: {details}")

    def get_db_connection(self):
        """Open a read-only SQLite connection to avoid locking active WAL writer."""
        uri = f"file:{self.db_path}?mode=ro"
        conn = sqlite3.connect(uri, uri=True, timeout=60.0)
        return conn

    def verify_all(self):
        if not self.json_output:
            print("=" * 75)
            print("VIDHUK SCRAPER DATASET INTEGRITY VERIFICATION (8 GATES)")
            print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
            print(f"Database:  {self.db_path}")
            print(f"Sitemap:   {self.sitemap_path}")
            print(f"Mode:      {'IN-PROGRESS (Partial)' if self.allow_in_progress else 'STRICT (100% Complete)'}")
            print("=" * 75)

        # Gate 1: Filesystem & File Sizes
        self.verify_gate1_filesystem()

        # Gate 2: SQLite Engine & WAL Mode
        self.verify_gate2_sqlite_engine()

        # Gate 3: Schema & Indexes
        self.verify_gate3_schema()

        # Gate 4: Sitemap Ingestion & Coverage
        self.verify_gate4_coverage()

        # Gate 5: Companies Table Invariants
        self.verify_gate5_companies()

        # Gate 6: Reviews Table Invariants
        self.verify_gate6_reviews()

        # Gate 7: Relational Consistency & Zero Orphans
        self.verify_gate7_relations()

        # Gate 8: Google Drive Backup Verification
        if not self.skip_gdrive:
            self.verify_gate8_gdrive()
        else:
            self.record("Gate 8: Google Drive", "Remote Backup Check", True, "Skipped by --skip-gdrive")

        passed_count = len(self.results) - self.failures
        success = (self.failures == 0)

        if self.json_output:
            summary = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "database": self.db_path,
                "sitemap": self.sitemap_path,
                "mode": "allow_in_progress" if self.allow_in_progress else "strict",
                "total_checks": len(self.results),
                "passed": passed_count,
                "failed": self.failures,
                "success": success,
                "checks": self.results,
            }
            print(json.dumps(summary, indent=2))
        else:
            print("=" * 75)
            status_text = "ALL CHECKS PASSED (CLEAN)" if success else f"{self.failures} CHECKS FAILED"
            print(f"SUMMARY: {passed_count}/{len(self.results)} Passed | Status: {status_text}")
            print("=" * 75)

        return success

    def verify_gate1_filesystem(self):
        # Database File
        db_exists = os.path.exists(self.db_path)
        db_size = os.path.getsize(self.db_path) if db_exists else 0
        min_db_size = 10_000_000  # 10 MB minimum
        self.record(
            "Gate 1: Filesystem",
            "Database File Presence & Size",
            db_exists and db_size >= min_db_size,
            f"Exists={db_exists}, Size={db_size:,} bytes (min {min_db_size:,} bytes)"
        )

        # Sitemap File
        s_exists = os.path.exists(self.sitemap_path)
        s_size = os.path.getsize(self.sitemap_path) if s_exists else 0
        min_s_size = 5_000_000  # 5 MB minimum
        self.record(
            "Gate 1: Filesystem",
            "Sitemap File Presence & Size",
            s_exists and s_size >= min_s_size,
            f"Exists={s_exists}, Size={s_size:,} bytes (min {min_s_size:,} bytes)"
        )

    def verify_gate2_sqlite_engine(self):
        try:
            conn = self.get_db_connection()
            cur = conn.cursor()

            # PRAGMA quick_check
            cur.execute("PRAGMA quick_check;")
            qc = cur.fetchall()
            is_qc_ok = (qc == [("ok",)])
            self.record(
                "Gate 2: SQLite Engine",
                "PRAGMA quick_check",
                is_qc_ok,
                f"Result={qc}"
            )

            # PRAGMA integrity_check
            cur.execute("PRAGMA integrity_check;")
            ic = cur.fetchall()
            is_ic_ok = (ic == [("ok",)])
            self.record(
                "Gate 2: SQLite Engine",
                "PRAGMA integrity_check",
                is_ic_ok,
                f"Result={ic}"
            )

            # PRAGMA journal_mode
            cur.execute("PRAGMA journal_mode;")
            jm = cur.fetchone()[0]
            is_wal = (jm.lower() == "wal")
            self.record(
                "Gate 2: SQLite Engine",
                "PRAGMA journal_mode (WAL)",
                is_wal,
                f"Journal mode={jm}"
            )

            conn.close()
        except Exception as e:
            self.record("Gate 2: SQLite Engine", "Engine Connection & Pragmas", False, f"Exception: {e}")

    def verify_gate3_schema(self):
        try:
            conn = self.get_db_connection()
            cur = conn.cursor()

            # Tables
            cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = set(r[0] for r in cur.fetchall())
            expected_tables = {"companies", "reviews", "progress"}
            tables_ok = expected_tables.issubset(tables)
            self.record(
                "Gate 3: Schema",
                "Required Tables Exist",
                tables_ok,
                f"Found={tables}, Required={expected_tables}"
            )

            # Columns in companies
            cur.execute("PRAGMA table_info(companies);")
            comp_cols = {r[1] for r in cur.fetchall()}
            expected_comp_cols = {"slug", "name", "org_type", "description", "rating", "review_count", "url", "scraped_at"}
            self.record(
                "Gate 3: Schema",
                "Companies Table Columns",
                expected_comp_cols.issubset(comp_cols),
                f"Columns={comp_cols}"
            )

            # Columns in reviews
            cur.execute("PRAGMA table_info(reviews);")
            rev_cols = {r[1] for r in cur.fetchall()}
            expected_rev_cols = {"id", "company_slug", "review_type", "author", "rating", "date", "title", "text", "url", "scraped_at"}
            self.record(
                "Gate 3: Schema",
                "Reviews Table Columns",
                expected_rev_cols.issubset(rev_cols),
                f"Columns={rev_cols}"
            )

            # Columns in progress
            cur.execute("PRAGMA table_info(progress);")
            prog_cols = {r[1] for r in cur.fetchall()}
            expected_prog_cols = {"url", "status", "reviews_count", "scraped_at", "error"}
            self.record(
                "Gate 3: Schema",
                "Progress Table Columns",
                expected_prog_cols.issubset(prog_cols),
                f"Columns={prog_cols}"
            )

            # Indexes
            cur.execute("SELECT name FROM sqlite_master WHERE type='index';")
            indexes = set(r[0] for r in cur.fetchall())
            expected_indexes = {"idx_rev_company", "idx_rev_rating", "idx_prog_status"}
            indexes_ok = expected_indexes.issubset(indexes)
            self.record(
                "Gate 3: Schema",
                "Required Indexes Exist",
                indexes_ok,
                f"Found={indexes}, Required={expected_indexes}"
            )

            conn.close()
        except Exception as e:
            self.record("Gate 3: Schema", "Schema Inspection", False, f"Exception: {e}")

    def verify_gate4_coverage(self):
        try:
            # Parse Sitemap
            tree = ET.parse(self.sitemap_path)
            root = tree.getroot()
            namespaces = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
            locs = root.findall('.//ns:loc', namespaces) or root.findall('.//loc')
            self.sitemap_urls = set(loc.text.strip() for loc in locs if loc.text)

            sitemap_count_ok = (len(self.sitemap_urls) == EXPECTED_SITEMAP_URLS)
            self.record(
                "Gate 4: Sitemap & Coverage",
                "Sitemap Target URL Count",
                sitemap_count_ok,
                f"Unique URLs={len(self.sitemap_urls):,} (expected {EXPECTED_SITEMAP_URLS:,})"
            )

            conn = self.get_db_connection()
            cur = conn.cursor()

            cur.execute("SELECT status, count(*) FROM progress GROUP BY status;")
            status_map = dict(cur.fetchall())
            total_progress = sum(status_map.values())
            done_count = status_map.get("done", 0)
            error_count = status_map.get("error", 0)

            if self.allow_in_progress:
                coverage_ok = (total_progress > 0)
                done_ratio = (done_count / total_progress) if total_progress > 0 else 0
                high_ratio_ok = (done_ratio >= 0.99)
                self.record(
                    "Gate 4: Sitemap & Coverage",
                    "Progress Tracking (In-Progress Mode)",
                    coverage_ok and high_ratio_ok,
                    f"Progress={total_progress:,}/{EXPECTED_SITEMAP_URLS:,} (Done={done_count:,}, Error={error_count}, Ratio={done_ratio:.4%})"
                )
            else:
                coverage_ok = (total_progress == EXPECTED_SITEMAP_URLS)
                self.record(
                    "Gate 4: Sitemap & Coverage",
                    "Full Sitemap Ingestion (100%)",
                    coverage_ok,
                    f"Tracked={total_progress:,} (expected {EXPECTED_SITEMAP_URLS:,})"
                )

                high_success_ok = (done_count >= 55200)  # >= 99.7% of 55,350
                self.record(
                    "Gate 4: Sitemap & Coverage",
                    "High Success Rate (>= 99.7%)",
                    high_success_ok,
                    f"Done={done_count:,}/55,350 ({(done_count / EXPECTED_SITEMAP_URLS):.2%})"
                )

            # Error rows documented check
            cur.execute("SELECT count(*) FROM progress WHERE status = 'error' AND (error IS NULL OR trim(error) = '');")
            unexplained_errors = cur.fetchone()[0]
            self.record(
                "Gate 4: Sitemap & Coverage",
                "Documented Errors Invariant",
                unexplained_errors == 0,
                f"Unexplained errors={unexplained_errors} (Total errors={error_count})"
            )

            conn.close()
        except Exception as e:
            self.record("Gate 4: Sitemap & Coverage", "Coverage Inspection", False, f"Exception: {e}")

    def verify_gate5_companies(self):
        try:
            conn = self.get_db_connection()
            cur = conn.cursor()

            # Row count
            cur.execute("SELECT count(*) FROM companies;")
            comp_count = cur.fetchone()[0]
            min_comp_count = 10000
            self.record(
                "Gate 5: Companies Data Quality",
                "Minimum Companies Ingested",
                comp_count >= min_comp_count,
                f"Total companies={comp_count:,} (min {min_comp_count:,})"
            )

            # Slugs
            cur.execute("SELECT count(*) FROM companies WHERE slug IS NULL OR trim(slug) = '';")
            empty_slugs = cur.fetchone()[0]
            self.record(
                "Gate 5: Companies Data Quality",
                "Zero Empty/NULL Slugs",
                empty_slugs == 0,
                f"Empty slugs={empty_slugs}"
            )

            # Names
            cur.execute("SELECT count(*) FROM companies WHERE name IS NULL OR trim(name) = '';")
            empty_names = cur.fetchone()[0]
            self.record(
                "Gate 5: Companies Data Quality",
                "Zero Empty/NULL Names",
                empty_names == 0,
                f"Empty names={empty_names}"
            )

            # URLs
            cur.execute("SELECT count(*) FROM companies WHERE url IS NULL OR url NOT LIKE 'https://www.vidhuk.ua/uk/%';")
            invalid_urls = cur.fetchone()[0]
            self.record(
                "Gate 5: Companies Data Quality",
                "Canonical Organization URLs",
                invalid_urls == 0,
                f"Invalid URLs={invalid_urls}"
            )

            # Ratings in range [1.0, 5.0]
            cur.execute("SELECT count(*) FROM companies WHERE rating IS NOT NULL AND (rating < 1.0 OR rating > 5.0);")
            invalid_ratings = cur.fetchone()[0]
            self.record(
                "Gate 5: Companies Data Quality",
                "Valid Rating Scale [1.0, 5.0]",
                invalid_ratings == 0,
                f"Invalid ratings={invalid_ratings}"
            )

            # Review counts non-negative
            cur.execute("SELECT count(*) FROM companies WHERE review_count < 0;")
            neg_counts = cur.fetchone()[0]
            self.record(
                "Gate 5: Companies Data Quality",
                "Non-Negative Review Counts",
                neg_counts == 0,
                f"Negative counts={neg_counts}"
            )

            conn.close()
        except Exception as e:
            self.record("Gate 5: Companies Data Quality", "Companies Inspection", False, f"Exception: {e}")

    def verify_gate6_reviews(self):
        try:
            conn = self.get_db_connection()
            cur = conn.cursor()

            # Row count
            cur.execute("SELECT count(*) FROM reviews;")
            rev_count = cur.fetchone()[0]
            min_rev_count = 50000
            self.record(
                "Gate 6: Reviews Data Quality",
                "Minimum Reviews Ingested",
                rev_count >= min_rev_count,
                f"Total reviews={rev_count:,} (min {min_rev_count:,})"
            )

            # Text not null / empty
            cur.execute("SELECT count(*) FROM reviews WHERE text IS NULL OR trim(text) = '';")
            empty_texts = cur.fetchone()[0]
            self.record(
                "Gate 6: Reviews Data Quality",
                "Zero Empty/NULL Texts",
                empty_texts == 0,
                f"Empty texts={empty_texts}"
            )

            # Text minimum length >= 1
            cur.execute("SELECT count(*) FROM reviews WHERE length(trim(text)) < 1;")
            blank_texts = cur.fetchone()[0]
            self.record(
                "Gate 6: Reviews Data Quality",
                "Authentic Review Text Length (>= 1 char)",
                blank_texts == 0,
                f"Blank texts={blank_texts}"
            )

            # Company slug present
            cur.execute("SELECT count(*) FROM reviews WHERE company_slug IS NULL OR trim(company_slug) = '';")
            empty_slugs = cur.fetchone()[0]
            self.record(
                "Gate 6: Reviews Data Quality",
                "Zero Empty/NULL Company Slugs",
                empty_slugs == 0,
                f"Empty company_slugs={empty_slugs}"
            )

            # Review type in ('klientov', 'sotrudnikov')
            cur.execute("SELECT count(*) FROM reviews WHERE review_type NOT IN ('klientov', 'sotrudnikov');")
            invalid_types = cur.fetchone()[0]
            self.record(
                "Gate 6: Reviews Data Quality",
                "Valid Review Types ('klientov' / 'sotrudnikov')",
                invalid_types == 0,
                f"Invalid review_types={invalid_types}"
            )

            # Rating in [1.0, 5.0]
            cur.execute("SELECT count(*) FROM reviews WHERE rating IS NULL OR rating < 1.0 OR rating > 5.0;")
            invalid_ratings = cur.fetchone()[0]
            self.record(
                "Gate 6: Reviews Data Quality",
                "Valid Review Rating Scale [1.0, 5.0]",
                invalid_ratings == 0,
                f"Invalid ratings={invalid_ratings}"
            )

            # Date format YYYY-MM-DD
            cur.execute("SELECT count(*) FROM reviews WHERE date NOT GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]';")
            invalid_dates = cur.fetchone()[0]
            self.record(
                "Gate 6: Reviews Data Quality",
                "Valid Date Format (YYYY-MM-DD)",
                invalid_dates == 0,
                f"Invalid dates={invalid_dates}"
            )

            # Composite Uniqueness Check
            cur.execute("""
                SELECT count(*) FROM (
                    SELECT company_slug, review_type, author, date, text, count(*)
                    FROM reviews
                    GROUP BY company_slug, review_type, author, date, text
                    HAVING count(*) > 1
                );
            """)
            dupes = cur.fetchone()[0]
            self.record(
                "Gate 6: Reviews Data Quality",
                "Review Uniqueness Constraint (0 Duplicates)",
                dupes == 0,
                f"Duplicate review groups={dupes}"
            )

            conn.close()
        except Exception as e:
            self.record("Gate 6: Reviews Data Quality", "Reviews Inspection", False, f"Exception: {e}")

    def verify_gate7_relations(self):
        try:
            conn = self.get_db_connection()
            cur = conn.cursor()

            # Zero Orphaned Reviews
            cur.execute("""
                SELECT count(*)
                FROM reviews r
                LEFT JOIN companies c ON r.company_slug = c.slug
                WHERE c.slug IS NULL;
            """)
            orphans = cur.fetchone()[0]
            self.record(
                "Gate 7: Relational Consistency",
                "Zero Orphaned Reviews",
                orphans == 0,
                f"Orphaned reviews without company={orphans}"
            )

            conn.close()
        except Exception as e:
            self.record("Gate 7: Relational Consistency", "Relations Inspection", False, f"Exception: {e}")

    def verify_gate8_gdrive(self):
        try:
            cmd = ["rclone", "lsl", self.gdrive_dest]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
            if res.returncode != 0:
                self.record(
                    "Gate 8: Google Drive",
                    "Remote Backup Verification",
                    False,
                    f"Rclone exit code {res.returncode}: {res.stderr.strip()}"
                )
                return

            lines = [l.strip() for l in res.stdout.strip().splitlines() if "vidhuk_full.db" in l]
            if not lines:
                self.record(
                    "Gate 8: Google Drive",
                    "Remote Backup Verification",
                    False,
                    f"File 'vidhuk_full.db' not found in rclone output: {res.stdout.strip()}"
                )
                return

            # Example output: "252497920 2026-11-18 09:51:02.665000000 vidhuk_full.db"
            parts = lines[0].split(None, 3)
            size = int(parts[0]) if parts and parts[0].isdigit() else 0
            size_mb = size / (1024 * 1024)

            passed = (size >= 50_000_000)
            self.record(
                "Gate 8: Google Drive",
                "Remote Backup Verification",
                passed,
                f"Remote file: {lines[0]} ({size_mb:.1f} MB)"
            )
        except Exception as e:
            self.record("Gate 8: Google Drive", "Remote Backup Verification", False, f"Exception: {e}")


def main():
    parser = argparse.ArgumentParser(description="Verify Vidhuk scraper dataset integrity across 8 quality gates.")
    parser.add_argument("--db-path", default=DEFAULT_DB_PATH, help="Path to SQLite database")
    parser.add_argument("--sitemap-path", default=DEFAULT_SITEMAP_PATH, help="Path to XML sitemap")
    parser.add_argument("--gdrive-dest", default=DEFAULT_GDRIVE_DEST, help="Google Drive destination for rclone")
    parser.add_argument("--allow-in-progress", action="store_true", help="Allow partial completion if scraper is active")
    parser.add_argument("--skip-gdrive", action="store_true", help="Skip Google Drive remote network check")
    parser.add_argument("--json", dest="json_output", action="store_true", help="Output results as JSON")

    args = parser.parse_args()

    verifier = ScraperVerifier(
        db_path=args.db_path,
        sitemap_path=args.sitemap_path,
        gdrive_dest=args.gdrive_dest,
        allow_in_progress=args.allow_in_progress,
        skip_gdrive=args.skip_gdrive,
        json_output=args.json_output,
    )
    success = verifier.verify_all()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
