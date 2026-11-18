#!/usr/bin/env python3
"""
rewrite_engine/migrate_db.py
Idempotent, WAL-safe SQLite schema migration for Milestone 2 (AI Humanized Rewrite Engine).
Adds 9 rewrite columns and an index on rewrite_status to the reviews table without blocking concurrent scraper writes.
"""

import os
import sys
import sqlite3
import logging
from typing import List, Tuple, Dict, Any, Set

DEFAULT_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "vidhuk_full.db")

REWRITE_COLUMNS: List[Tuple[str, str]] = [
    ("rewritten_title", "TEXT"),
    ("rewritten_text", "TEXT"),
    ("rewritten_pros", "TEXT"),
    ("rewritten_cons", "TEXT"),
    ("rewrite_status", "TEXT DEFAULT 'pending'"),
    ("rewrite_lang", "TEXT"),
    ("rewritten_at", "TEXT"),
    ("rewrite_error", "TEXT"),
    ("rewrite_model", "TEXT"),
]

INDEXES: List[Tuple[str, str]] = [
    ("idx_reviews_rewrite_status", "CREATE INDEX IF NOT EXISTS idx_reviews_rewrite_status ON reviews(rewrite_status);"),
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [migrate_db] %(message)s"
)
logger = logging.getLogger("migrate_db")


def get_existing_columns(conn: sqlite3.Connection, table_name: str) -> Set[str]:
    """Retrieves existing column names from table."""
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table_name});")
    return {row[1] for row in cur.fetchall()}


def migrate_database(db_path: str = DEFAULT_DB_PATH) -> Dict[str, Any]:
    """
    Applies the schema migration to add rewrite columns and index idempotently.
    Safe for execution while the scraper is actively writing in WAL mode.
    """
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Database file not found: {db_path}")

    logger.info(f"Connecting to database: {db_path}")
    conn = sqlite3.connect(db_path, timeout=60.0)
    try:
        cur = conn.cursor()
        cur.execute("PRAGMA busy_timeout = 60000;")

        # Ensure journal mode is WAL
        cur.execute("PRAGMA journal_mode;")
        mode_row = cur.fetchone()
        current_mode = mode_row[0] if mode_row else "unknown"
        logger.info(f"Current journal_mode: {current_mode}")
        if current_mode.lower() != "wal":
            logger.info("Setting journal_mode to WAL...")
            cur.execute("PRAGMA journal_mode = WAL;")

        existing_cols = get_existing_columns(conn, "reviews")
        logger.info(f"Existing columns in 'reviews': {len(existing_cols)}")

        added_columns: List[str] = []
        for col_name, col_def in REWRITE_COLUMNS:
            if col_name not in existing_cols:
                logger.info(f"Adding column '{col_name} {col_def}' to 'reviews'...")
                cur.execute(f"ALTER TABLE reviews ADD COLUMN {col_name} {col_def};")
                added_columns.append(col_name)
            else:
                logger.debug(f"Column '{col_name}' already exists. Skipping.")

        # Ensure indexes
        created_indexes: List[str] = []
        for idx_name, idx_sql in INDEXES:
            logger.info(f"Ensuring index: {idx_name}...")
            cur.execute(idx_sql)
            created_indexes.append(idx_name)

        conn.commit()
        all_cols = get_existing_columns(conn, "reviews")
        logger.info(f"Migration completed successfully. Added {len(added_columns)} new columns. Total columns: {len(all_cols)}.")
        return {
            "status": "success",
            "added_columns": added_columns,
            "created_indexes": created_indexes,
            "total_columns": len(all_cols),
        }
    finally:
        conn.close()


if __name__ == "__main__":
    db_file = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_DB_PATH
    result = migrate_database(db_file)
    print(result)
