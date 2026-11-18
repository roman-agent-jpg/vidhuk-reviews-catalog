#!/usr/bin/env python3
"""
rewrite_engine/sanitizer.py
Deterministic regex sanitizer for Milestone 2 (AI Humanized Rewrite Engine).
Completely purges unicode em-dashes ('—') and en-dashes ('–'), fixes punctuation,
normalizes whitespace, strips smart quotes/markdown artifacts, and sanitizes review titles.
"""

import re
import json
from typing import Optional

# Unicode dash patterns
UNICODE_DASHES = r'[\u2013\u2014\u2015\u2012\u2212]'


def sanitize_review_text(text: Optional[str]) -> str:
    """
    Executes a deterministic sanitization pipeline:
    1. Extract plain text if wrapped in JSON / markdown fences
    2. Normalize unicode spaces (\u00a0, \u200b, \ufeff) and smart quotes (“ ” « »)
    3. Normalize newlines (\r\n, \r -> \n)
    4. Numeric intervals with en/em-dash -> ASCII hyphen (10–15 -> 10-15)
    5. List bullets at start of lines -> ASCII '- '
    6. Comma-adjacent dashes -> comma (, — -> , )
    7. Inter-word dashes with spaces -> standard spaced hyphen ' - '
    8. Any remaining unicode dashes -> ASCII hyphen '-'
    9. Multi-hyphen collapse (--+ -> -)
    10. Punctuation cleanup (duplicate commas, comma-hyphen collisions, spacing before punctuation)
    11. Spacing normalization (tabs/multiple spaces collapse, trailing/leading strip)
    """
    if not text:
        return ""

    s = text

    # Step 1: Handle Markdown / JSON wrappers (e.g. ```json {"title":..., "text":...} ```)
    m_code = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', s, re.DOTALL)
    if m_code:
        try:
            parsed = json.loads(m_code.group(1))
            if isinstance(parsed, dict) and ('text' in parsed or 'title' in parsed):
                s = parsed.get('text') or parsed.get('title') or s
            else:
                s = re.sub(r'```(?:json)?|```', '', s)
        except Exception:
            s = re.sub(r'```(?:json)?|```', '', s)
    else:
        s = re.sub(r'```(?:json)?|```', '', s)

    # Step 2: Normalize unicode spaces and quotes
    s = s.replace('\u00a0', ' ')
    s = s.replace('\u200b', '')
    s = s.replace('\ufeff', '')
    s = s.replace('“', '"').replace('”', '"').replace('„', '"')

    # Step 3: Normalize newlines
    s = s.replace("\r\n", "\n").replace("\r", "\n")

    # Step 4: Numeric intervals with en/em-dash: e.g. "2020–2021" -> "2020-2021", "10–15" -> "10-15"
    s = re.sub(rf'(\d+)\s*{UNICODE_DASHES}\s*(\d+)', r'\1-\2', s)

    # Step 5: List bullets at start of lines: e.g. "— Товар якісний" -> "- Товар якісний"
    s = re.sub(rf'(^|\n)\s*{UNICODE_DASHES}\s*', r'\1- ', s)

    # Step 6: Comma-adjacent dashes: "власники, — вкрай" -> "власники, вкрай"
    s = re.sub(rf',\s*{UNICODE_DASHES}\s*', ', ', s)
    s = re.sub(rf'{UNICODE_DASHES}\s*,', ', ', s)

    # Step 7: Inter-word clause dashes with spaces: "Сервіс — клас" -> "Сервіс - клас"
    s = re.sub(rf'\s+{UNICODE_DASHES}\s+', ' - ', s)

    # Step 8: Any remaining unicode dashes -> standard ASCII hyphen
    s = re.sub(UNICODE_DASHES, '-', s)

    # Step 9: Multi-hyphen collapse: "--", "---" -> "-"
    s = re.sub(r'-{2,}', '-', s)

    # Step 10: Punctuation cleanup
    s = re.sub(r',\s*-\s*', ', ', s)
    s = re.sub(r'-\s*,', ', ', s)
    s = re.sub(r',\s*,+', ', ', s)
    s = re.sub(r'\s+([,.:;!?])', r'\1', s)

    # Step 11: Spacing normalization
    s = re.sub(r'[ \t]+', ' ', s)
    s = re.sub(r'\n{3,}', '\n\n', s)

    return s.strip()


def sanitize_title(title: Optional[str]) -> str:
    """
    Specialized title sanitizer removing raw URLs and trailing/leading dashes or punctuation.
    """
    if not title:
        return ""

    t = sanitize_review_text(title)

    # Remove raw protocol URLs from titles if model or source repeated them
    t = re.sub(r'https?://\S+', '', t)

    # Remove leading/trailing hyphens, colons, or punctuation
    t = re.sub(r'^[\s\-,.:;]+', '', t)
    t = re.sub(r'[\s\-,.:;]+$', '', t)

    # Collapse any leftover spaces
    t = re.sub(r'\s+', ' ', t)

    return t.strip()


# Canonical alias for compatibility
sanitize_text = sanitize_review_text
