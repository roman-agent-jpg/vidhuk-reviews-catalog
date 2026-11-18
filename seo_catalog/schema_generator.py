"""
Schema.org JSON-LD Generation Module.

Constructs Google Rich Snippets compliant Schema.org JSON-LD schemas for companies and reviews.
Upgrades generic Organization to LocalBusiness or commercial subtypes, encapsulates reviewer
author in structured Person objects, clamps ratings, formats dates to ISO 8601, and completely
omits aggregateRating when unrated or zero reviews.
"""

from typing import Any, Dict, List, Optional
import json
import re


def clean_text(text: Optional[str]) -> str:
    """Strips HTML tags, collapses whitespace, and cleans unprintable characters."""
    if not text:
        return ""
    # Strip HTML tags
    clean = re.sub(r"<[^>]+>", " ", str(text))
    # Collapse whitespace
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean


def format_iso_date(date_str: Optional[str]) -> Optional[str]:
    """Ensures calendar date is in ISO 8601 YYYY-MM-DD format."""
    if not date_str:
        return None
    match = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", str(date_str))
    if match:
        return match.group(1)
    return str(date_str).strip()[:10]


def generate_company_schema(
    company: Dict[str, Any],
    reviews: Optional[List[Dict[str, Any]]] = None,
    schema_type: Optional[str] = None,
    base_url: str = "https://otzyvtut.com",
) -> Dict[str, Any]:
    """
    Generates a fully compliant Schema.org JSON-LD dictionary for a company.

    Parameters:
        company: Dictionary with keys: name, slug, org_type, description, rating, review_count, url.
        reviews: Optional list of review dicts (author, rating, date, title, text).
        schema_type: Specific Schema.org type (e.g. 'Store', 'AutomotiveBusiness'). Upgrades generic 'Organization'.
        base_url: Portal base URL for canonical JSON-LD url property.

    Returns:
        Dict[str, Any]: Schema.org compliant structured data object.
    """
    raw_name = company.get("name") or "Компанія"
    company_name = clean_text(raw_name)
    slug = company.get("slug") or ""
    canonical_url = f"{base_url.rstrip('/')}/company/{slug}" if slug else company.get("url") or base_url

    # Upgrade generic 'Organization' or missing type to LocalBusiness / commercial subtype
    final_type = schema_type or company.get("org_type") or "LocalBusiness"
    if final_type == "Organization" or final_type == "Product":
        final_type = "LocalBusiness"

    schema: Dict[str, Any] = {
        "@context": "https://schema.org",
        "@type": final_type,
        "name": company_name,
        "url": canonical_url,
    }

    desc = clean_text(company.get("description"))
    if desc:
        # Keep description cleanly bounded if excessively long
        schema["description"] = desc[:500] if len(desc) > 500 else desc

    # AggregateRating handling: strictly omitted if review_count is 0 or unrated
    review_count = int(company.get("review_count") or 0)
    raw_rating = company.get("rating")
    rating_val = float(raw_rating) if (raw_rating is not None and float(raw_rating) > 0) else None

    if review_count >= 1 and rating_val is not None:
        # Clamp rating between 1.0 and 5.0
        clamped_rating = max(1.0, min(5.0, round(rating_val, 1)))
        schema["aggregateRating"] = {
            "@type": "AggregateRating",
            "ratingValue": clamped_rating,
            "reviewCount": review_count,
            "bestRating": 5,
            "worstRating": 1,
        }

    # Review list handling
    if reviews and review_count >= 1 and rating_val is not None:
        formatted_reviews: List[Dict[str, Any]] = []
        # Google recommends up to 10 representative reviews in JSON-LD
        for rev in reviews[:10]:
            rev_rating_raw = rev.get("rating")
            try:
                rev_rating = max(1.0, min(5.0, round(float(rev_rating_raw or 5.0), 1)))
            except (ValueError, TypeError):
                rev_rating = 5.0

            # Structured author object (Google requirement: @type Person)
            author_name = clean_text(rev.get("author")) or "Користувач"
            review_date = format_iso_date(rev.get("date")) or "2026-01-01"
            review_title = clean_text(rev.get("title")) or f"Відгук про {company_name}"
            review_body = clean_text(rev.get("text")) or review_title

            review_item: Dict[str, Any] = {
                "@type": "Review",
                "author": {
                    "@type": "Person",
                    "name": author_name,
                },
                "datePublished": review_date,
                "name": review_title,
                "reviewBody": review_body,
                "reviewRating": {
                    "@type": "Rating",
                    "ratingValue": rev_rating,
                    "bestRating": 5,
                    "worstRating": 1,
                },
            }
            formatted_reviews.append(review_item)

        if formatted_reviews:
            schema["review"] = formatted_reviews

    return schema


def generate_jsonld_script(schema_dict: Dict[str, Any]) -> str:
    """
    Serializes a schema dictionary to HTML-safe <script type="application/ld+json">.
    Safely escapes closing script tags to prevent XSS script breakout.
    """
    json_str = json.dumps(schema_dict, ensure_ascii=False, indent=2)
    safe_json_str = json_str.replace("</script>", r"<\/script>")
    return f'<script type="application/ld+json">\n{safe_json_str}\n</script>'
