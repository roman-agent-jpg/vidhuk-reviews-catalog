#!/usr/bin/env python3
"""
rewrite_engine/linter.py
Strict quality validator for Milestone 2 (AI Humanized Rewrite Engine).
Enforces:
- Gate 1: Non-emptiness and minimum length integrity.
- Gate 2: STRICT ZERO unicode dash check (em-dash, en-dash, horizontal bar, figure dash, minus).
- Gate 3: Multi-hyphen check (--+).
- Gate 4: Cliché blacklist scan (41 Russian + 43 Ukrainian patterns).
- Gate 5: Emotional sentiment polarity preservation (1-2 star negative, 4.5-5 star positive).
- Gate 6: Raw URL guard in title.
"""

import re
from dataclasses import dataclass
from typing import List, Tuple, Dict, Any, Optional

# Prohibited unicode dashes
FORBIDDEN_DASH_PATTERN = re.compile(r'[\u2013\u2014\u2015\u2012\u2212]')
MULTI_HYPHEN_PATTERN = re.compile(r'--+')
URL_PATTERN = re.compile(r'https?://', re.IGNORECASE)

# Russian Banned Clichés (41 regex patterns)
RU_BANNED_CLICHES: List[str] = [
    # Bureaucratic Demonstratives
    r'\bданн[а-яё]{2,4}\s+(сервис|компани|магазин|заведени|продукт|специалист|приложени|организаци|работодател|сайт|фирм)[а-яё]*\b',
    r'\bнастоящ[а-яё]{2,4}\s+(сервис|компани|магазин|заведени|организаци)[а-яё]*\b',
    # Introductory Meta-talk
    r'\bхотел[оась]*сь?\s+бы\s+отметить\b',
    r'\bхочу\s+поделиться\s+(своим\s+)?(опытом|впечатлени)[а-яё]*\b',
    r'\bне\s+могу\s+не\s+отметить\b',
    r'\bстоит\s+(отметить|подчеркнуть|сказать|обратить\s+внимание)\b',
    r'\bследует\s+(отметить|подчеркнуть|сказать|заметить)\b',
    r'\bв\s+первую\s+очередь\s+(хочется|хочу|стоит|следует)\b',
    r'\bпрежде\s+всего\s+(хочется|хочу|стоит|следует)\b',
    r'\bспешу\s+поделиться\b',
    # Concluding Meta-talk
    r'\bв\s+заключени[ие]\b',
    r'\bподводя\s+итог[и]*\b',
    r'\bподытоживая\b',
    r'\bв\s+качестве\s+(вывода|заключения|итога)\b',
    r'\bрезюмируя(\s+вышесказанное)?\b',
    r'\bисходя\s+из\s+выше(сказанного|изложенного)\b',
    r'\bкак\s+итог\b',
    r'\bв\s+сухом\s+остатке\b',
    r'\bделая\s+вывод\b',
    # Marketing Fluff
    r'\bявляется\s+(отличным|прекрасным|хорошим|лучшим|достойным)\s+выбором\b',
    r'\bстал[оа]?\s+настоящ[еий][йм]\s+(находкой|открытием)\b',
    r'\bсоотношени[ея]\s+цен[а-яё]*\s*[-и]\s*качеств[а-яё]*\b',
    r'\bнастоятельно\s+рекоменду[юе]\b',
    r'\bоднозначно\s+рекоменду[юе]\s+к\s+сотрудничеству\b',
    r'\bпрофессионал[ыа]*\s+своего\s+дела\b',
    r'\bмастер[а-яё]*\s+своего\s+дела\b',
    r'\bвысокий\s+уровень\s+сервиса\b',
    r'\bиндивидуальный\s+подход\s+к\s+каждому\b',
    r'\bклиентоориентированност[ья]\b',
    r'\bприятно\s+удивил[аои]?\b',
    r'\bработает\s+как\s+швейцарские\s+часы\b',
    # Robotic Negative
    r'\bоставляет\s+желать\s+лучшего\b',
    r'\bоставляет\s+(неприятный|негативный)\s+осадок\b',
    r'\bне\s+оправдал[оаи]?\s+(ожиданий|возложенных\s+надежд)\b',
    r'\bвпечатление\s+было\s+испорчено\b',
    r'\bне\s+выдерживает\s+никакой\s+критики\b',
    # Employee Clichés
    r'\bдружный(\s+и\s+сплоченный)?\s+коллектив\b',
    r'\bдинамично\s+развивающ[а-яё]{2,4}\s+компани[а-яё]*\b',
    r'\bвозможности\s+для\s+(карьерного|профессионального)\s+роста\b',
    r'\bкомфортные\s+условия\s+труда\b',
    r'\bлояльное\s+руководство\b',
]

# Ukrainian Banned Clichés (43 regex patterns)
UA_BANNED_CLICHES: List[str] = [
    # Bureaucratic Demonstratives
    r'\bдан[а-яіїєґ]{1,4}\s+(сервіс|компані|магазин|заклад|продукт|фахівець|додаток|організаці|роботодав|сайт|фірм)[а-яіїєґ]*\b',
    r'\bсправжн[ійяє]{2,4}\s+(сервіс|компані|магазин|заклад|організаці)[а-яіїєґ]*\b',
    # Introductory Meta-talk
    r'\bхотілос[яь]\s+б\s+відзначити\b',
    r'\bхочу\s+поділитися\s+(своїм\s+)?(досвідом|враженнями)\b',
    r'\bне\s+можу\s+не\s+відзначити\b',
    r'\bварто\s+(відзначити|підкреслити|сказати|звернути\s+увагу)\b',
    r'\bслід\s+(зазначити|підкреслити|сказати|зауважити)\b',
    r'\bнасамперед\s+(хочеться|хочу|варто|слід)\b',
    r'\bперш\s+за\s+все\s+(хочеться|хочу|варто|слід)\b',
    r'\bпоспішаю\s+поділитися\b',
    # Concluding Meta-talk
    r'\bна\s+закінчення\b',
    r'\bнаостанок\b',
    r'\bпідсумовуючи\b',
    r'\bпідбиваючи\s+підсумк[и]*\b',
    r'\bу\s+якості\s+(висновку|підсумку)\b',
    r'\bяк\s+висновок\b',
    r'\bяк\s+підсумок\b',
    r'\bрезюмуючи(\s+вищесказане)?\b',
    r'\bвиходячи\s+з\s+вище(сказаного|викладеного)\b',
    r'\bу\s+сухому\s+залишку\b',
    r'\bроблячи\s+висновок\b',
    # Marketing Fluff
    r'\bє\s+(чудовим|відмінним|гарним|найкращим|достойним)\s+вибором\b',
    r'\bстав[лао]?\s+справжнь[оеі][юяй]\s+(знахідкою|відкриттям)\b',
    r'\bспіввідношенн[яі]\s+цін[а-яіїєґ]*\s*[-таі]\s*якост[а-яіїєґ]*\b',
    r'\bнастійно\s+рекоменду[ює]\b',
    r'\bоднозначно\s+рекоменду[ює]\s+до\s+співпраці\b',
    r'\bпрофесіонал[иів]*\s+своєї\s+справи\b',
    r'\bмайстр[иів]*\s+своєї\s+справи\b',
    r'\bвисокий\s+рівень\s+сервісу\b',
    r'\bіндивідуальний\s+підхід\s+до\s+кожного\b',
    r'\bклієнтоорієнтованість\b',
    r'\bприємно\s+здивував[лаои]?\b',
    r'\bпрацює\s+як\s+швейцарський\s+годинник\b',
    # Robotic Negative
    r'\bзалишає\s+бажати\s+кращого\b',
    r'\bзалишає\s+(неприємний|негативний)\s+осад\b',
    r'\bне\s+виправдав[лаои]?\s+(очікувань|покладених\s+сподівань)\b',
    r'\bвраження\s+було\s+зіпсоване\b',
    r'\bне\s+витримує\s+жодної\s+критики\b',
    # Employee Clichés
    r'\bдружній(\s+і\s+згуртований)?\s+колектив\b',
    r'\bкомпанія,\s*що\s+динамічно\s+розвивається\b',
    r'\bможливості\s+для\s+(кар[\x27\u2019]єрного|професійного)\s+зростання\b',
    r'\bкомфортні\s+умови\s+праці\b',
    r'\bлояльне\s+керівництво\b',
]

ALL_CLICHES = RU_BANNED_CLICHES + UA_BANNED_CLICHES
COMPILED_ALL_CLICHES = [re.compile(p, re.IGNORECASE) for p in ALL_CLICHES]


@dataclass
class LintResult:
    is_valid: bool
    errors: List[str]


def validate_rewritten_review(rewritten: Dict[str, Any], original: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Validates a rewritten review against all quality invariants.
    Returns (is_valid, errors_list).
    """
    errors: List[str] = []

    title = (rewritten.get("title") or rewritten.get("rewritten_title") or "").strip()
    text = (rewritten.get("text") or rewritten.get("rewritten_text") or "").strip()
    pros = (rewritten.get("pros") or rewritten.get("rewritten_pros") or "").strip()
    cons = (rewritten.get("cons") or rewritten.get("rewritten_cons") or "").strip()

    orig_text = (original.get("text") or "").strip()
    try:
        rating = float(original.get("rating", 3.0))
    except (ValueError, TypeError):
        rating = 3.0

    # Gate 1: Non-emptiness and basic length
    if not text:
        errors.append("L01_EMPTY_TEXT: Rewritten text cannot be empty.")
    elif len(text) < 20 and len(orig_text) >= 40:
        errors.append(f"L01_TOO_SHORT: Text length reduced excessively below threshold ({len(text)} vs {len(orig_text)}).")

    if not title or len(title) < 3:
        errors.append(f"L01_INVALID_TITLE: Title must be at least 3 characters (got '{title}').")

    # Gate 2: Strict Zero Unicode Dash
    fields_to_check = [("title", title), ("text", text), ("pros", pros), ("cons", cons)]
    for field_name, val in fields_to_check:
        m = FORBIDDEN_DASH_PATTERN.search(val)
        if m:
            char_hex = f"U+{ord(m.group()):04X}"
            errors.append(f"L02_FORBIDDEN_DASH: Prohibited unicode dash {char_hex} in {field_name}: '{m.group()}'.")

    # Gate 3: Multi-Hyphen Detection
    for field_name, val in [("title", title), ("text", text)]:
        if MULTI_HYPHEN_PATTERN.search(val):
            errors.append(f"L03_MULTI_HYPHEN: Prohibited sequence of multiple hyphens in {field_name}.")

    # Gate 4: Banned Clichés
    combined_text = f"{title} {text} {pros} {cons}"
    for pat in COMPILED_ALL_CLICHES:
        m = pat.search(combined_text)
        if m:
            errors.append(f"L04_BANNED_CLICHE: AI cliché pattern matched: '{m.group()}'.")
            break  # Flag first matching cliché

    # Gate 5: Sentiment Polarity Integrity
    lowered = combined_text.lower()
    if rating <= 2.0:
        praise_markers = [
            "дуже задоволен", "чудовий магазин", "прекрасный сервис", "все супер",
            "отличная компания", "відмінний сервіс", "прекрасна якість"
        ]
        for p in praise_markers:
            if p in lowered:
                # Check if it's negated like "зовсім не дуже задоволений"
                negated = re.search(rf"\b(не|зовсім\s+не|аж\s+ніяк\s+не|далеко\s+не)\s+{re.escape(p)}", lowered)
                if not negated:
                    errors.append(f"L05_POLARITY_INVERSION: Strong positive praise '{p}' found in negative ({rating}-star) review.")
                    break
    elif rating >= 4.5:
        scam_markers = [
            "шахраї", "мошенники", "жахлива фірма", "ужасная компания", "развод на деньги",
            "кидалово", "обманщики", "аферисти"
        ]
        for s in scam_markers:
            if s in lowered:
                negated = re.search(rf"\b(не|ніякі\s+не|зовсім\s+не)\s+{re.escape(s)}", lowered)
                if not negated:
                    errors.append(f"L05_POLARITY_INVERSION: Accusation '{s}' found in highly rated ({rating}-star) review.")
                    break

    # Gate 6: Raw URL Contamination in Title
    if URL_PATTERN.search(title):
        errors.append("L06_URL_IN_TITLE: Raw URL string detected in title.")

    return len(errors) == 0, errors


def lint_review(
    rewritten_title: str,
    rewritten_text: str,
    rewritten_pros: str,
    rewritten_cons: str,
    original_review: Dict[str, Any],
    lang: str = "uk"
) -> LintResult:
    """
    Convenience wrapper returning a LintResult object.
    """
    rewritten_dict = {
        "title": rewritten_title,
        "text": rewritten_text,
        "pros": rewritten_pros,
        "cons": rewritten_cons,
        "lang": lang
    }
    is_valid, errors = validate_rewritten_review(rewritten_dict, original_review)
    return LintResult(is_valid=is_valid, errors=errors)
