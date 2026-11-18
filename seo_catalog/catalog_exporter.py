"""
SEO Catalog Exporter Module.

High-performance streaming exporter that connects to vidhuk_full.db in read-only mode,
processes companies in batches of 1,000, prefetches reviews in batched queries,
enriches each record with SEO metadata, taxonomy classification, and Schema.org JSON-LD,
and streams the results to JSON or JSONL (with transparent .gz support).
"""

from typing import Any, Dict, Iterator, List, Optional
from datetime import datetime, timezone
import argparse
import gzip
import json
import os
import sqlite3

from .meta_generator import generate_meta
from .schema_generator import generate_company_schema
from .taxonomy import classify_company, get_cluster_info, list_all_clusters


class CatalogExporter:
    """
    Streaming catalog exporter for SEO-ready company and review data.
    """

    def __init__(
        self,
        db_path: str = "/root/новій отзовик/vidhuk_full.db",
        chunk_size: int = 1000,
        base_url: str = "https://otzyvtut.com",
    ):
        self.db_path = os.path.abspath(db_path)
        self.chunk_size = chunk_size
        self.base_url = base_url

    def _get_db_connection(self) -> sqlite3.Connection:
        """Opens read-only SQLite connection using URI mode."""
        conn = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        return conn

    def stream_companies(self, limit: Optional[int] = None) -> Iterator[Dict[str, Any]]:
        """
        Yields enriched company records with taxonomy, SEO meta, and JSON-LD schema.
        Employs batch chunking and indexed review prefetching to maintain minimal RAM usage.
        """
        conn = self._get_db_connection()
        cur = conn.cursor()

        try:
            # Query companies cursor
            query = "SELECT slug, name, org_type, description, rating, review_count, url FROM companies"
            if limit is not None and limit > 0:
                query += f" LIMIT {int(limit)}"

            cur.execute(query)

            yielded_count = 0
            while True:
                chunk = cur.fetchmany(self.chunk_size)
                if not chunk:
                    break

                # Extract slugs in current chunk
                slugs = [row["slug"] for row in chunk if row["slug"]]

                # Batch prefetch reviews for slugs
                reviews_by_slug: Dict[str, List[Dict[str, Any]]] = {s: [] for s in slugs}
                if slugs:
                    placeholders = ",".join("?" for _ in slugs)
                    rev_query = f"""
                        SELECT company_slug, author, rating, date, title, text
                        FROM reviews
                        WHERE company_slug IN ({placeholders})
                        ORDER BY date DESC
                    """
                    rev_cur = conn.cursor()
                    rev_cur.execute(rev_query, slugs)
                    for r_row in rev_cur.fetchall():
                        c_slug = r_row["company_slug"]
                        # Cap at 10 reviews per company to avoid payload bloat
                        if len(reviews_by_slug[c_slug]) < 10:
                            reviews_by_slug[c_slug].append(
                                {
                                    "author": r_row["author"],
                                    "rating": r_row["rating"],
                                    "date": r_row["date"],
                                    "title": r_row["title"],
                                    "text": r_row["text"],
                                }
                            )
                    rev_cur.close()

                # Enrich and yield each company
                for row in chunk:
                    c_dict = dict(row)
                    c_slug = c_dict["slug"]
                    c_name = c_dict.get("name") or ""
                    c_org_type = c_dict.get("org_type")
                    c_desc = c_dict.get("description")

                    # 1. Classify taxonomy cluster and Schema.org type
                    cluster_id, schema_type = classify_company(c_name, c_org_type, c_desc)

                    # 2. Generate SEO metadata (titles, 140-155 description, keywords, slug)
                    meta = generate_meta(c_dict, cluster_id=cluster_id)

                    # 3. Generate Schema.org JSON-LD
                    company_reviews = reviews_by_slug.get(c_slug, [])
                    schema = generate_company_schema(
                        company=c_dict,
                        reviews=company_reviews,
                        schema_type=schema_type,
                        base_url=self.base_url,
                    )

                    enriched_record = {
                        "slug": c_slug,
                        "name": c_name,
                        "org_type": c_org_type,
                        "description": c_desc,
                        "rating": c_dict.get("rating"),
                        "review_count": c_dict.get("review_count") or 0,
                        "url": c_dict.get("url"),
                        "cluster_id": cluster_id,
                        "schema_type": schema_type,
                        "meta": meta,
                        "schema": schema,
                        "reviews_sample": company_reviews[:5],
                    }

                    yield enriched_record
                    yielded_count += 1
                    if limit is not None and yielded_count >= limit:
                        return
        finally:
            cur.close()
            conn.close()

    def export_json(self, output_path: str, limit: Optional[int] = None) -> int:
        """
        Streams enriched company catalog to a JSON array file.
        Returns the number of exported companies.
        """
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        count = 0
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("[\n")
            first = True
            for record in self.stream_companies(limit=limit):
                if not first:
                    f.write(",\n")
                first = False
                f.write("  " + json.dumps(record, ensure_ascii=False))
                count += 1
            f.write("\n]\n")
        return count

    def export_jsonl(self, output_path: str, limit: Optional[int] = None) -> int:
        """
        Streams enriched company catalog to a line-delimited JSON (JSONL) file.
        Automatically compresses with gzip if output_path ends with '.gz'.
        Returns the number of exported companies.
        """
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        count = 0
        if output_path.endswith(".gz"):
            file_handle = gzip.open(output_path, "wt", encoding="utf-8")
        else:
            file_handle = open(output_path, "w", encoding="utf-8")

        with file_handle as f:
            for record in self.stream_companies(limit=limit):
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
                count += 1
        return count

    def export_categories_index(self, output_path: str) -> Dict[str, Any]:
        """
        Generates and saves a category index summarizing all clusters,
        company counts, and sample slugs for directory navigation.
        """
        conn = self._get_db_connection()
        cur = conn.cursor()

        all_clusters_dict = {c["id"]: dict(c) for c in list_all_clusters()}
        for cid in all_clusters_dict:
            all_clusters_dict[cid]["company_count"] = 0
            all_clusters_dict[cid]["sample_slugs"] = []

        total_companies = 0
        try:
            cur.execute("SELECT slug, name, org_type, description FROM companies")
            while True:
                chunk = cur.fetchmany(self.chunk_size)
                if not chunk:
                    break
                for row in chunk:
                    cid, _ = classify_company(row["name"] or "", row["org_type"], row["description"])
                    if cid in all_clusters_dict:
                        all_clusters_dict[cid]["company_count"] += 1
                        if len(all_clusters_dict[cid]["sample_slugs"]) < 10:
                            all_clusters_dict[cid]["sample_slugs"].append(row["slug"])
                    total_companies += 1
        finally:
            cur.close()
            conn.close()

        index_payload = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_companies": total_companies,
            "clusters_count": len(all_clusters_dict),
            "clusters": list(all_clusters_dict.values()),
        }

        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(index_payload, f, ensure_ascii=False, indent=2)

        return index_payload


def main():
    """CLI runner for catalog export."""
    parser = argparse.ArgumentParser(description="OtzyvTut SEO Catalog Exporter")
    parser.add_argument("--db-path", default="/root/новій отзовик/vidhuk_full.db", help="Path to SQLite database")
    parser.add_argument("--format", choices=["json", "jsonl", "all"], default="jsonl", help="Export format")
    parser.add_argument("--output", default="catalog_export.jsonl", help="Output file path")
    parser.add_argument("--limit", type=int, default=None, help="Max records to export")
    parser.add_argument("--chunk-size", type=int, default=1000, help="Batch chunk size")
    parser.add_argument("--categories-index", default=None, help="Optional output path for categories index JSON")

    args = parser.parse_args()
    exporter = CatalogExporter(db_path=args.db_path, chunk_size=args.chunk_size)

    if args.categories_index:
        print(f"Exporting categories index to {args.categories_index}...")
        idx = exporter.export_categories_index(args.categories_index)
        print(f"Categories index exported. Total companies: {idx['total_companies']}.")

    if args.format == "json":
        print(f"Exporting JSON to {args.output} (limit={args.limit})...")
        count = exporter.export_json(args.output, limit=args.limit)
        print(f"Exported {count} records to {args.output}.")
    elif args.format == "jsonl":
        print(f"Exporting JSONL to {args.output} (limit={args.limit})...")
        count = exporter.export_jsonl(args.output, limit=args.limit)
        print(f"Exported {count} records to {args.output}.")
    elif args.format == "all":
        json_out = args.output if args.output.endswith(".json") else args.output + ".json"
        jsonl_out = args.output if args.output.endswith(".jsonl") else args.output + ".jsonl"
        print(f"Exporting JSON to {json_out} and JSONL to {jsonl_out} (limit={args.limit})...")
        c1 = exporter.export_json(json_out, limit=args.limit)
        c2 = exporter.export_jsonl(jsonl_out, limit=args.limit)
        print(f"Exported {c1} records to JSON and {c2} records to JSONL.")


if __name__ == "__main__":
    main()
