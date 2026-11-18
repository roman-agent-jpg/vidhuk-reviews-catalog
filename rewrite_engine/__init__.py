"""
AI Humanized Rewrite Engine package (Milestone 2).
Provides:
- In-place idempotent database migration for rewrite columns.
- Prompt templates and language detection enforcing zero em-dash and anti-cliché rules.
- Deterministic 9-stage regex sanitizer.
- Strict 6-gate quality linter.
- High-throughput asynchronous batch rewrite runner with rate limiting and checkpointing.
"""

from .migrate_db import migrate_database, REWRITE_COLUMNS
from .prompts import (
    detect_language,
    get_system_prompt,
    format_user_prompt,
    SYSTEM_PROMPT_UK,
    SYSTEM_PROMPT_RU,
)
from .sanitizer import (
    sanitize_review_text,
    sanitize_title,
    sanitize_text,
)
from .linter import (
    validate_rewritten_review,
    lint_review,
    LintResult,
    RU_BANNED_CLICHES,
    UA_BANNED_CLICHES,
    ALL_CLICHES,
)
from .rewrite_runner import (
    AsyncRewriteRunner,
    BaseLLMProvider,
    MockLLMProvider,
    OpenAICompatibleProvider,
    GeminiProvider,
    AsyncRateLimiter,
)

__all__ = [
    "migrate_database",
    "REWRITE_COLUMNS",
    "detect_language",
    "get_system_prompt",
    "format_user_prompt",
    "SYSTEM_PROMPT_UK",
    "SYSTEM_PROMPT_RU",
    "sanitize_review_text",
    "sanitize_title",
    "sanitize_text",
    "validate_rewritten_review",
    "lint_review",
    "LintResult",
    "RU_BANNED_CLICHES",
    "UA_BANNED_CLICHES",
    "ALL_CLICHES",
    "AsyncRewriteRunner",
    "BaseLLMProvider",
    "MockLLMProvider",
    "OpenAICompatibleProvider",
    "GeminiProvider",
    "AsyncRateLimiter",
]
