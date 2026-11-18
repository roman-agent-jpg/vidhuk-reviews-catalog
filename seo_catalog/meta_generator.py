"""
SEO Metadata Generation Module.

Generates SERP-compliant title tags (including adaptive variants to prevent SERP truncation),
strictly bounded meta descriptions (140-155 characters invariant), commercial reputation
keywords, and transliterated ASCII URL slugs.
"""

from typing import Any, Dict, List, Optional
import re

# Cyrillic to ASCII transliteration table (supporting Ukrainian and Russian)
TRANSLIT_TABLE: Dict[str, str] = {
    # Ukrainian specific
    "є": "ye", "Є": "Ye",
    "і": "i", "І": "I",
    "ї": "yi", "Ї": "Yi",
    "ґ": "g", "Ґ": "G",
    # Russian specific
    "ё": "yo", "Ё": "Yo",
    "ы": "y", "Ы": "Y",
    "э": "e", "Э": "E",
    "ъ": "", "Ъ": "",
    # Common Cyrillic
    "а": "a", "А": "A",
    "б": "b", "Б": "B",
    "в": "v", "В": "V",
    "г": "g", "Г": "G",
    "д": "d", "Д": "D",
    "е": "e", "Е": "E",
    "ж": "zh", "Ж": "Zh",
    "з": "z", "З": "Z",
    "и": "i", "И": "I",
    "й": "y", "Й": "Y",
    "к": "k", "К": "K",
    "л": "l", "Л": "L",
    "м": "m", "М": "M",
    "н": "n", "Н": "N",
    "о": "o", "О": "O",
    "п": "p", "П": "P",
    "р": "r", "Р": "R",
    "с": "s", "С": "S",
    "т": "t", "Т": "T",
    "у": "u", "У": "U",
    "ф": "f", "Ф": "F",
    "х": "kh", "Х": "Kh",
    "ц": "ts", "Ц": "Ts",
    "ч": "ch", "Ч": "Ch",
    "ш": "sh", "Ш": "Sh",
    "щ": "shch", "Щ": "Shch",
    "ь": "", "Ь": "",
    "ю": "yu", "Ю": "Yu",
    "я": "ya", "Я": "Ya",
}

# Cluster-specific keyword suffixes for high commercial intent
CLUSTER_KEYWORD_HINTS: Dict[str, str] = {
    "finance_crypto": "кредиты займы условия",
    "auto_transport": "автосервис перевозки цены",
    "medicine_health": "врачи цены запись",
    "education": "курсы обучение отзывы",
    "beauty_services": "салон прайс запись",
    "jobs_employment": "работа вакансии зарплата",
    "legal_consulting": "юрист консультация стоимость",
    "construction_repair": "ремонт цены каталог",
    "furniture_home": "каталог мебели цены",
    "it_web": "разработка софт портфолио",
    "tourism_leisure": "бронирование отдых цены",
    "ecommerce_shops": "доставка оплата гарантия",
    "other": "услуги цены контакты",
}

# Ranked pool of closing CTA phrases for strictly fitting into 140-155 chars
CTA_CANDIDATES: List[str] = [
    "Читайте честные мнения клиентов и сотрудников на сервисе ОтзывТут!",  # 66
    "Читайте подробные мнения клиентов и сотрудников на ОтзывТут!",       # 60
    "Читайте честные мнения клиентов и сотрудников на ОтзывТут!",          # 58
    "Читайте реальный опыт, все плюсы и минусы на ОтзывТут!",              # 54
    "Реальный опыт клиентов, плюсы и минусы на ОтзывТут!",                # 51
    "Читайте мнения клиентов и сотрудников на ОтзывТут!",                 # 50
    "Узнайте плюсы и минусы работы сервиса на ОтзывТут!",                 # 50
    "Узнайте честные мнения и подробности на ОтзывТут!",                  # 49
    "Реальные отзывы клиентов и оценки на ОтзывТут!",                     # 46
    "Читайте честные отзывы клиентов на ОтзывТут!",                       # 44
    "Честные мнения клиентов и оценки на ОтзывТут!",                      # 44
    "Узнайте все плюсы и минусы на ОтзывТут!",                            # 39
    "Читайте реальные отзывы на ОтзывТут!",                               # 36
    "Честный опыт клиентов на ОтзывТут!",                                 # 34
    "Подробные отзывы на ОтзывТут!",                                      # 29
    "Реальный опыт на ОтзывТут!",                                         # 26
    "Все мнения на ОтзывТут!",                                            # 23
    "Отзывы на ОтзывТут!",                                                # 19
    "На сайте ОтзывТут!",                                                 # 18
]


def clean_company_name(name: Optional[str]) -> str:
    """Strips quotes, chevrons, HTML brackets, and collapses whitespace."""
    if not name:
        return ""
    text = re.sub(r"<[^>]+>", "", str(name))
    text = re.sub(r'[\"\'\`\«\»\“\”]', "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def normalize_slug(text: str) -> str:
    """
    Normalizes any string or company name into a clean lowercase ASCII URL slug.
    Transliterates Cyrillic characters, replaces non-alphanumeric with hyphens,
    and removes multiple consecutive or outer hyphens.
    """
    if not text:
        return "company"

    # Transliterate Cyrillic characters
    res = []
    for char in text:
        res.append(TRANSLIT_TABLE.get(char, char))
    transliterated = "".join(res)

    # Convert to lowercase
    lowered = transliterated.lower()

    # Replace non-alphanumeric characters with hyphens
    slug = re.sub(r"[^a-z0-9]+", "-", lowered)

    # Collapse consecutive hyphens and strip from edges
    slug = re.sub(r"-+", "-", slug).strip("-")

    return slug or "company"


def generate_titles(company_name: str) -> Dict[str, str]:
    """
    Generates exact canonical title and adaptive SERP title based on name length:
    - Exact: {Company} отзывы — рейтинг, реальный опыт клиентов и сотрудников
    - Adaptive SERP: responsive length optimization keeping target within 55-65 chars.
    """
    clean_name = clean_company_name(company_name) or "Компания"

    # Exact required title
    title_exact = f"{clean_name} отзывы — рейтинг, реальный опыт клиентов и сотрудников"

    # Adaptive SERP title
    name_len = len(clean_name)
    if name_len <= 18:
        # Full title fits comfortably in SERP (55–74 chars)
        title_adaptive = title_exact
    elif 19 <= name_len <= 32:
        # Suffix is 36 chars; total is 55-68 chars
        title_adaptive = f"{clean_name} отзывы: рейтинг и реальный опыт"
    elif 33 <= name_len <= 45:
        # Suffix is 26 chars; total is 59-71 chars
        title_adaptive = f"{clean_name} — отзывы и честный рейтинг"
    else:
        # Name is very long (> 45 chars); truncate name at word boundary to <= 35 chars
        truncated_name = clean_name[:35].rsplit(" ", 1)[0].rstrip(",.- ")
        if not truncated_name:
            truncated_name = clean_name[:32]
        title_adaptive = f"{truncated_name}... — отзывы и рейтинг"

    return {
        "title": title_adaptive,
        "title_exact": title_exact,
    }


def declension_reviews(count: int) -> str:
    """Returns grammatically correct Russian genitive declension after 'на основе X'."""
    abs_count = abs(int(count))
    if abs_count % 10 == 1 and abs_count % 100 != 11:
        return "отзыва"
    return "отзывов"


def generate_meta_description(
    company_name: str,
    rating: Optional[float] = None,
    review_count: Optional[int] = None,
) -> str:
    """
    Generates a meta description strictly bounded between 140 and 155 characters.
    Incorporates authentic rating, review count with accurate declension,
    and sentiment summary.
    """
    clean_name = clean_company_name(company_name) or "Компания"
    count = int(review_count or 0)
    rate = float(rating) if (rating is not None and rating > 0) else None
    has_reviews = count > 0 and rate is not None

    # Multi-pass search over name-length budgets to find optimal fit
    for max_name_len in (30, 25, 20, 35, 15, 10):
        if len(clean_name) > max_name_len:
            short_name = clean_name[: max_name_len - 3].rsplit(" ", 1)[0].rstrip(",.- ")
            if not short_name:
                short_name = clean_name[: max_name_len - 3]
            short_name += "..."
        else:
            short_name = clean_name

        if has_reviews:
            decl = declension_reviews(count)
            if rate >= 4.0:
                sentiment = "Высокие оценки сервиса и надежности."
            elif rate >= 2.5:
                sentiment = "Смешанные оценки реальных клиентов."
            else:
                sentiment = "Преобладают критические отзывы и жалобы."
            base = f"Отзывы о {short_name}: рейтинг {rate:.1f}/5 на основе {count} {decl}. {sentiment}"
        else:
            base = f"Компания {short_name}: честные отзывы, рейтинг и условия сотрудничества. Пока нет подтвержденных оценок."

        for cta in CTA_CANDIDATES:
            candidate = f"{base} {cta}"
            if 140 <= len(candidate) <= 155:
                return candidate

    # Deterministic fallback guaranteed to produce 140-155 chars
    target_len = 148
    if has_reviews:
        decl = declension_reviews(count)
        lead = f"Отзывы о {clean_name[:20]}: рейтинг {rate:.1f}/5 ({count} {decl})."
    else:
        lead = f"Отзывы о {clean_name[:20]}: условия сотрудничества."

    tail = " Реальный опыт клиентов, актуальные оценки, плюсы и минусы на ОтзывТут!"
    combined = lead + tail
    if len(combined) > 155:
        # Cut at word boundary before 152 and append '...'
        cut = combined[:151].rsplit(" ", 1)[0]
        return f"{cut}..."
    elif len(combined) < 140:
        padding = " Читайте честные отзывы онлайн."
        combined += padding
        if len(combined) > 155:
            return combined[:152] + "..."
        return combined

    return combined


def generate_keywords(company_name: str, cluster_id: Optional[str] = None) -> List[str]:
    """
    Generates 6-8 high-intent commercial reputation search queries.
    """
    clean_name = clean_company_name(company_name) or "Компания"
    cid = cluster_id or "other"
    cluster_hint = CLUSTER_KEYWORD_HINTS.get(cid, "услуги цены отзывы")

    keywords = [
        f"{clean_name} отзывы",
        f"{clean_name} відгуки",
        f"{clean_name} рейтинг",
        f"{clean_name} отзывы клиентов",
        f"{clean_name} отзывы сотрудников",
        f"честный обзор {clean_name}",
        f"{clean_name} {cluster_hint}",
        f"{clean_name} официальный сайт",
    ]
    return keywords


def generate_meta(
    company: Dict[str, Any],
    cluster_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Generates complete SEO metadata dictionary for a company:
    {
        'title': str,           # Adaptive SERP title
        'title_exact': str,     # Exact required title
        'description': str,     # Strictly 140-155 characters
        'keywords': List[str],  # 6-8 high-intent queries
        'slug': str,            # Transliterated ASCII slug
        'canonical_path': str   # Canonical relative path /company/{slug}
    }
    """
    name = company.get("name") or ""
    rating = company.get("rating")
    review_count = company.get("review_count")
    slug = company.get("slug") or normalize_slug(name)

    titles = generate_titles(name)
    description = generate_meta_description(name, rating=rating, review_count=review_count)
    keywords = generate_keywords(name, cluster_id=cluster_id)

    return {
        "title": titles["title"],
        "title_exact": titles["title_exact"],
        "description": description,
        "keywords": keywords,
        "slug": slug,
        "canonical_path": f"/company/{slug}",
    }
