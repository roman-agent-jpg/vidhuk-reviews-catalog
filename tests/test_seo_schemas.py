"""
Comprehensive Test Suite for Milestone 3 (SEO Catalog & JSON-LD Schemas).

Tests:
1. Taxonomy classification, bilingual keyword patterns, and Schema.org mapping.
2. SERP-compliant titles, 140-155 character meta descriptions invariant, keywords, and slugs.
3. Google Rich Snippets Schema.org JSON-LD generator and script serialization.
4. Streaming catalog exporter (JSON, JSONL, gzip, categories index).
5. Real database validation on vidhuk_full.db in read-only mode.
"""

import gzip
import json
import os
import sqlite3
import tempfile
import unittest

from seo_catalog.taxonomy import (
    CLUSTERS,
    classify_company,
    get_cluster_info,
    list_all_clusters,
)
from seo_catalog.meta_generator import (
    clean_company_name,
    declension_reviews,
    generate_keywords,
    generate_meta,
    generate_meta_description,
    generate_titles,
    normalize_slug,
)
from seo_catalog.schema_generator import (
    clean_text,
    format_iso_date,
    generate_company_schema,
    generate_jsonld_script,
)
from seo_catalog.catalog_exporter import CatalogExporter

DB_PATH = "/root/новій отзовик/vidhuk_full.db"


class TestTaxonomy(unittest.TestCase):
    """Tests for seo_catalog.taxonomy."""

    def test_all_clusters_defined(self):
        """Verify all 12 commercial clusters + 'other' are defined with full metadata."""
        clusters = list_all_clusters()
        self.assertEqual(len(clusters), 13)

        cluster_ids = {c["id"] for c in clusters}
        expected_ids = {
            "ecommerce_shops",
            "auto_transport",
            "finance_crypto",
            "medicine_health",
            "it_web",
            "beauty_services",
            "education",
            "construction_repair",
            "furniture_home",
            "jobs_employment",
            "tourism_leisure",
            "legal_consulting",
            "other",
        }
        self.assertEqual(cluster_ids, expected_ids)

        for c in clusters:
            self.assertIn("id", c)
            self.assertIn("label_ru", c)
            self.assertIn("label_ua", c)
            self.assertIn("schema_type", c)
            self.assertIn("description_ru", c)
            self.assertIn("description_ua", c)
            self.assertIn("keywords_ru", c)
            self.assertIn("keywords_ua", c)
            self.assertTrue(len(c["label_ru"]) > 0)
            self.assertTrue(len(c["schema_type"]) > 0)

    def test_get_cluster_info(self):
        """Verify get_cluster_info returns valid metadata or falls back to 'other'."""
        info = get_cluster_info("finance_crypto")
        self.assertEqual(info["id"], "finance_crypto")
        self.assertEqual(info["schema_type"], "FinancialService")

        fallback = get_cluster_info("non_existent_cluster")
        self.assertEqual(fallback["id"], "other")
        self.assertEqual(fallback["schema_type"], "LocalBusiness")

    def test_classification_by_org_type(self):
        """Verify direct org_type mapping for specific Schema.org types."""
        cases = [
            ("AutoRepair", "auto_transport", "AutoRepair"),
            ("Dentist", "medicine_health", "Dentist"),
            ("MedicalClinic", "medicine_health", "MedicalClinic"),
            ("BankOrCreditUnion", "finance_crypto", "BankOrCreditUnion"),
            ("Hotel", "tourism_leisure", "Hotel"),
            ("Restaurant", "tourism_leisure", "Restaurant"),
            ("BeautySalon", "beauty_services", "BeautySalon"),
            ("EmploymentAgency", "jobs_employment", "EmploymentAgency"),
            ("FurnitureStore", "furniture_home", "FurnitureStore"),
        ]
        for org_type, expected_cid, expected_stype in cases:
            cid, stype = classify_company("Generic Business", org_type=org_type)
            self.assertEqual(cid, expected_cid, f"Failed for org_type {org_type}")
            self.assertEqual(stype, expected_stype, f"Failed for org_type {org_type}")

    def test_classification_by_description_tags(self):
        """Verify classification using category tags in description."""
        test_cases = [
            ("Smart Value", "Organization", "Интернет-магазины электроники и смартфонов", "ecommerce_shops"),
            ("BUSSONE", "Organization", "Международные пассажирские перевозки автобусом", "auto_transport"),
            ("ZeroTrace", "Organization", "Онлайн-сервис для обмена криптовалют bitcoin btc", "finance_crypto"),
            ("Profcomfort", "Organization", "Ворота роллеты монтаж и автоматика", "construction_repair"),
            ("Курс Бухгалтер", "Organization", "Бизнес-образование и курсы", "education"),
            ("Отель Днепр", "LocalBusiness", "Гостиница отель и отдых", "tourism_leisure"),
            ("Аптека Подорожник", "Store", "Аптека ліків та медичних препаратів", "medicine_health"),
            ("Мебель Люкс", "LocalBusiness", "Диваны кровати кухни на заказ", "furniture_home"),
            ("Work in Poland", "Organization", "Работа за границей и вакансии", "jobs_employment"),
            ("Юрист и Партнеры", "Organization", "Адвокаты судебные споры и аудит", "legal_consulting"),
            ("Barbershop Chop", "LocalBusiness", "Стрижка бород мужская парикмахерская", "beauty_services"),
            ("Web Dev Studio", "Organization", "Разработка сайтов и мобильных приложений", "it_web"),
        ]
        for name, org_type, desc, expected_cid in test_cases:
            cid, stype = classify_company(name, org_type=org_type, description=desc)
            self.assertEqual(cid, expected_cid, f"Failed for {name}: expected {expected_cid}, got {cid}")
            self.assertNotEqual(stype, "Organization", "Generic Organization must be upgraded")

    def test_classification_fallback(self):
        """Verify unclassifiable entities fall back gracefully to ('other', 'LocalBusiness')."""
        cid, stype = classify_company("ABC 123 Ltd", "Organization", "")
        self.assertEqual(cid, "other")
        self.assertEqual(stype, "LocalBusiness")

    def test_live_db_taxonomy_coverage(self):
        """Verify taxonomy performance on real records from vidhuk_full.db."""
        if not os.path.exists(DB_PATH):
            self.skipTest(f"Database not found at {DB_PATH}")

        conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
        cur = conn.cursor()
        cur.execute("SELECT name, org_type, description FROM companies LIMIT 500")
        rows = cur.fetchall()
        conn.close()

        observed_clusters = set()
        other_count = 0
        for name, org_type, desc in rows:
            cid, stype = classify_company(name, org_type, desc)
            observed_clusters.add(cid)
            if cid == "other":
                other_count += 1
            # Check schema upgrade
            self.assertNotEqual(stype, "Organization", f"Company {name} retained generic Organization")

        # Must have broad coverage across clusters
        self.assertGreaterEqual(len(observed_clusters), 8)
        # 'other' fallback proportion must be reasonable (<= 30%)
        other_pct = other_count / len(rows)
        self.assertLessEqual(other_pct, 0.30, f"'other' cluster proportion too high: {other_pct:.1%}")


class TestMetaGenerator(unittest.TestCase):
    """Tests for seo_catalog.meta_generator."""

    def test_normalize_slug(self):
        """Verify Cyrillic transliteration and ASCII normalization."""
        cases = [
            ('Курс "Бухгалтер ФОП" від "Кадри"', "kurs-bukhgalter-fop-vid-kadri"),
            ("Об'єкт №123 (Київ) — СТО", "ob-yekt-123-kiyiv-sto"),
            ("Smart Value / Магазин", "smart-value-magazin"),
            ("  --EVA--  ", "eva"),
            ("Щастя & Здоров'я ґудзик", "shchastya-zdorov-ya-gudzik"),
            ("100% Agency", "100-agency"),
        ]
        for raw, expected in cases:
            slug = normalize_slug(raw)
            self.assertEqual(slug, expected, f"Failed slug normalization for '{raw}'")
            self.assertTrue(slug.islower(), "Slug must be lowercase")
            self.assertFalse("--" in slug, "Slug must not contain double hyphens")
            self.assertFalse(slug.startswith("-") or slug.endswith("-"), "Slug must not have edge hyphens")

    def test_title_exact_formula(self):
        """Verify exact title required by ORIGINAL_REQUEST.md §3."""
        name = "Rozetka"
        titles = generate_titles(name)
        expected_exact = "Rozetka отзывы — рейтинг, реальный опыт клиентов и сотрудников"
        self.assertEqual(titles["title_exact"], expected_exact)

    def test_responsive_serp_titles(self):
        """Verify adaptive title tiers based on company name length."""
        # Tier 1: Short name <= 18 chars
        t1 = generate_titles("EVA")
        self.assertEqual(t1["title"], "EVA отзывы — рейтинг, реальный опыт клиентов и сотрудников")
        self.assertLessEqual(len(t1["title"]), 75)

        # Tier 2: Medium name 19-32 chars
        t2 = generate_titles("Интернет-магазин техники")
        self.assertEqual(t2["title"], "Интернет-магазин техники отзывы: рейтинг и реальный опыт")
        self.assertLessEqual(len(t2["title"]), 75)

        # Tier 3: Long name 33-45 chars
        t3 = generate_titles("Строительная компания Киевский Монолит")
        self.assertEqual(t3["title"], "Строительная компания Киевский Монолит — отзывы и честный рейтинг")
        self.assertLessEqual(len(t3["title"]), 75)

        # Tier 4: Extra long name > 45 chars
        t4 = generate_titles("Комунальне підприємство Полтавський обласний клінічний медичний кардіоваскулярний центр")
        self.assertTrue(t4["title"].endswith("... — отзывы и рейтинг"))
        self.assertLessEqual(len(t4["title"]), 65)

    def test_declension_reviews(self):
        """Verify Russian genitive declension logic."""
        self.assertEqual(declension_reviews(1), "отзыва")
        self.assertEqual(declension_reviews(2), "отзывов")
        self.assertEqual(declension_reviews(3), "отзывов")
        self.assertEqual(declension_reviews(4), "отзывов")
        self.assertEqual(declension_reviews(5), "отзывов")
        self.assertEqual(declension_reviews(11), "отзывов")
        self.assertEqual(declension_reviews(12), "отзывов")
        self.assertEqual(declension_reviews(21), "отзыва")
        self.assertEqual(declension_reviews(22), "отзывов")
        self.assertEqual(declension_reviews(101), "отзыва")
        self.assertEqual(declension_reviews(111), "отзывов")

    def test_meta_description_length_invariant(self):
        """Verify meta description strictly adheres to 140-155 characters across all cases."""
        test_inputs = [
            ("EVA", 5.0, 1),
            ("Smart Value", 4.7, 18),
            ("Rozetka", 4.2, 4373),
            ("BUSSONE", 3.2, 5),
            ("ZeroTrace", 1.5, 3),
            ("New Company", None, 0),
            ("Company with No Rating", 0.0, 0),
            ("A" * 10, 4.5, 21),
            ("A" * 50, 4.0, 100),
            ("Комунальне підприємство Полтавський обласний клінічний медичний кардіоваскулярний центр", 1.0, 2),
        ]
        for name, rating, count in test_inputs:
            desc = generate_meta_description(name, rating=rating, review_count=count)
            desc_len = len(desc)
            self.assertTrue(
                140 <= desc_len <= 155,
                f"Description length violation: {desc_len} chars for '{name}'. Text: '{desc}'",
            )

    def test_live_db_description_invariant(self):
        """Verify 140-155 character invariant on 200 real companies sampled from vidhuk_full.db."""
        if not os.path.exists(DB_PATH):
            self.skipTest(f"Database not found at {DB_PATH}")

        conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
        cur = conn.cursor()
        cur.execute("SELECT name, rating, review_count FROM companies LIMIT 200")
        rows = cur.fetchall()
        conn.close()

        for name, rating, count in rows:
            desc = generate_meta_description(name, rating=rating, review_count=count)
            self.assertTrue(
                140 <= len(desc) <= 155,
                f"Description violation ({len(desc)} chars) for '{name}': '{desc}'",
            )

    def test_keywords_generation(self):
        """Verify commercial reputation keywords generation."""
        keywords = generate_keywords("Smart Value", cluster_id="ecommerce_shops")
        self.assertGreaterEqual(len(keywords), 6)
        self.assertLessEqual(len(keywords), 8)
        self.assertIn("Smart Value отзывы", keywords)
        self.assertIn("Smart Value відгуки", keywords)
        self.assertIn("Smart Value рейтинг", keywords)
        for kw in keywords:
            self.assertTrue(len(kw.strip()) > 0)
            self.assertFalse("<" in kw or ">" in kw)

    def test_generate_meta_complete(self):
        """Verify unified generate_meta returns all required fields."""
        company = {
            "name": "Smart Value",
            "rating": 4.5,
            "review_count": 12,
            "slug": "smart-value",
        }
        meta = generate_meta(company, cluster_id="ecommerce_shops")
        self.assertIn("title", meta)
        self.assertIn("title_exact", meta)
        self.assertIn("description", meta)
        self.assertIn("keywords", meta)
        self.assertIn("slug", meta)
        self.assertIn("canonical_path", meta)
        self.assertEqual(meta["slug"], "smart-value")
        self.assertEqual(meta["canonical_path"], "/company/smart-value")
        self.assertTrue(140 <= len(meta["description"]) <= 155)


class TestSchemaGenerator(unittest.TestCase):
    """Tests for seo_catalog.schema_generator."""

    def test_schema_with_reviews(self):
        """Verify full Google Rich Snippets compliant schema when reviews exist."""
        company = {
            "slug": "smart-value",
            "name": "Smart Value",
            "org_type": "Store",
            "rating": 4.7,
            "review_count": 15,
            "description": "Магазин техники",
        }
        reviews = [
            {
                "author": "Олександр",
                "rating": 5.0,
                "date": "2026-05-15",
                "title": "Отличный сервис",
                "text": "Быстро доставили смартфон, всё отлично работает.",
            },
            {
                "author": "",  # Empty author edge case
                "rating": 4.0,
                "date": "2026-04-10 12:34:56",  # Datetime string edge case
                "title": "",  # Empty title edge case
                "text": "Нормальный магазин.",
            },
        ]

        schema = generate_company_schema(company, reviews=reviews, schema_type="Store")
        self.assertEqual(schema["@context"], "https://schema.org")
        self.assertEqual(schema["@type"], "Store")
        self.assertEqual(schema["name"], "Smart Value")
        self.assertEqual(schema["url"], "https://otzyvtut.com/company/smart-value")

        # AggregateRating checks
        self.assertIn("aggregateRating", schema)
        agg = schema["aggregateRating"]
        self.assertEqual(agg["@type"], "AggregateRating")
        self.assertEqual(agg["ratingValue"], 4.7)
        self.assertEqual(agg["reviewCount"], 15)
        self.assertEqual(agg["bestRating"], 5)
        self.assertEqual(agg["worstRating"], 1)

        # Review array checks
        self.assertIn("review", schema)
        self.assertEqual(len(schema["review"]), 2)

        # First review
        r1 = schema["review"][0]
        self.assertEqual(r1["@type"], "Review")
        self.assertEqual(r1["author"]["@type"], "Person")
        self.assertEqual(r1["author"]["name"], "Олександр")
        self.assertEqual(r1["datePublished"], "2026-05-15")
        self.assertEqual(r1["reviewRating"]["ratingValue"], 5.0)
        self.assertNotIn("itemReviewed", r1, "itemReviewed must be omitted in nested reviews")

        # Second review (with empty author fallback and ISO date extraction)
        r2 = schema["review"][1]
        self.assertEqual(r2["author"]["@type"], "Person")
        self.assertEqual(r2["author"]["name"], "Користувач")
        self.assertEqual(r2["datePublished"], "2026-04-10")

    def test_schema_zero_reviews_omission(self):
        """Verify aggregateRating and review array are completely omitted when review_count == 0."""
        company = {
            "slug": "zero-review-shop",
            "name": "Zero Review Shop",
            "org_type": "Store",
            "rating": None,
            "review_count": 0,
            "description": "Новый магазин без отзывов",
        }
        schema = generate_company_schema(company, reviews=[])
        self.assertEqual(schema["@context"], "https://schema.org")
        self.assertEqual(schema["@type"], "Store")
        self.assertNotIn("aggregateRating", schema, "aggregateRating must be omitted when 0 reviews")
        self.assertNotIn("review", schema, "review array must be omitted when 0 reviews")

    def test_schema_organization_upgrade(self):
        """Verify generic Organization is upgraded to LocalBusiness."""
        company = {
            "slug": "generic-org",
            "name": "Generic Org",
            "org_type": "Organization",
            "rating": 4.0,
            "review_count": 2,
        }
        schema = generate_company_schema(company)
        self.assertEqual(schema["@type"], "LocalBusiness")

    def test_jsonld_script_escaping(self):
        """Verify script serialization escapes </script> tags and quotes safely."""
        company = {
            "slug": "quote-shop",
            "name": 'Магазин "Лидер" </script><script>alert(1)</script>',
            "org_type": "Store",
            "rating": 4.5,
            "review_count": 3,
        }
        schema = generate_company_schema(company)
        script_html = generate_jsonld_script(schema)

        self.assertTrue(script_html.startswith('<script type="application/ld+json">'))
        self.assertTrue(script_html.endswith("</script>"))
        # Must not contain unescaped internal closing script tags
        body = script_html[len('<script type="application/ld+json">\n') : -len("\n</script>")]
        self.assertNotIn("</script>", body)

        # Parse back JSON to verify valid format
        parsed = json.loads(body)
        self.assertEqual(parsed["@context"], "https://schema.org")


class TestCatalogExporter(unittest.TestCase):
    """Tests for seo_catalog.catalog_exporter."""

    def setUp(self):
        if not os.path.exists(DB_PATH):
            self.skipTest(f"Database not found at {DB_PATH}")
        self.exporter = CatalogExporter(db_path=DB_PATH, chunk_size=50)

    def test_stream_companies(self):
        """Verify streaming generator yields valid enriched records."""
        stream = self.exporter.stream_companies(limit=25)
        records = list(stream)
        self.assertEqual(len(records), 25)

        for rec in records:
            self.assertIn("slug", rec)
            self.assertIn("name", rec)
            self.assertIn("cluster_id", rec)
            self.assertIn("schema_type", rec)
            self.assertIn("meta", rec)
            self.assertIn("schema", rec)
            self.assertIn("reviews_sample", rec)
            self.assertTrue(140 <= len(rec["meta"]["description"]) <= 155)
            self.assertEqual(rec["schema"]["@context"], "https://schema.org")

    def test_export_json(self):
        """Verify export_json writes valid JSON array."""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            count = self.exporter.export_json(tmp_path, limit=20)
            self.assertEqual(count, 20)

            with open(tmp_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            self.assertIsInstance(data, list)
            self.assertEqual(len(data), 20)
            self.assertEqual(data[0]["schema"]["@context"], "https://schema.org")
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def test_export_jsonl_plain_and_gz(self):
        """Verify export_jsonl writes valid line-delimited JSON for both plain and gzip."""
        # Plain JSONL
        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as tmp:
            plain_path = tmp.name

        # Gzip JSONL
        with tempfile.NamedTemporaryFile(suffix=".jsonl.gz", delete=False) as tmp:
            gz_path = tmp.name

        try:
            # 1. Plain
            c1 = self.exporter.export_jsonl(plain_path, limit=15)
            self.assertEqual(c1, 15)
            with open(plain_path, "r", encoding="utf-8") as f:
                lines = [json.loads(line) for line in f if line.strip()]
            self.assertEqual(len(lines), 15)

            # 2. Gzip
            c2 = self.exporter.export_jsonl(gz_path, limit=15)
            self.assertEqual(c2, 15)
            with gzip.open(gz_path, "rt", encoding="utf-8") as f:
                gz_lines = [json.loads(line) for line in f if line.strip()]
            self.assertEqual(len(gz_lines), 15)
            self.assertEqual(gz_lines[0]["slug"], lines[0]["slug"])
        finally:
            if os.path.exists(plain_path):
                os.remove(plain_path)
            if os.path.exists(gz_path):
                os.remove(gz_path)

    def test_export_categories_index(self):
        """Verify export_categories_index produces comprehensive categories summary."""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            idx_path = tmp.name

        try:
            index_data = self.exporter.export_categories_index(idx_path)
            self.assertIn("total_companies", index_data)
            self.assertGreater(index_data["total_companies"], 0)
            self.assertEqual(index_data["clusters_count"], 13)
            self.assertEqual(len(index_data["clusters"]), 13)

            with open(idx_path, "r", encoding="utf-8") as f:
                saved = json.load(f)
            self.assertEqual(saved["clusters_count"], 13)
        finally:
            if os.path.exists(idx_path):
                os.remove(idx_path)


if __name__ == "__main__":
    unittest.main()
