"""
OtzyvTut SEO Catalog & JSON-LD Schemas Package.

This package provides:
- 12-cluster commercial business taxonomy and Schema.org mapping (taxonomy.py).
- SERP-compliant titles, 140-155 char meta descriptions, keywords, and slugs (meta_generator.py).
- Google Rich Snippets compliant Schema.org JSON-LD generation (schema_generator.py).
- High-performance streaming catalog exporter to JSON and JSONL (catalog_exporter.py).
"""

from .taxonomy import (
    CLUSTERS,
    classify_company,
    get_cluster_info,
    list_all_clusters,
)
from .meta_generator import (
    generate_meta,
    normalize_slug,
    generate_titles,
    generate_meta_description,
    generate_keywords,
)
from .schema_generator import (
    generate_company_schema,
    generate_jsonld_script,
)
from .catalog_exporter import (
    CatalogExporter,
)

__version__ = "1.0.0"
__all__ = [
    "CLUSTERS",
    "classify_company",
    "get_cluster_info",
    "list_all_clusters",
    "generate_meta",
    "normalize_slug",
    "generate_titles",
    "generate_meta_description",
    "generate_keywords",
    "generate_company_schema",
    "generate_jsonld_script",
    "CatalogExporter",
]
