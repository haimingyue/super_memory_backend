"""Deprecated compatibility layer for old template method."""

from __future__ import annotations

import warnings


def build_link_story(hook: str, keyword: str, next_keyword: str) -> str:
    """Deprecated: kept only for compatibility with old imports."""
    warnings.warn(
        "build_link_story 已废弃：核心生成逻辑已迁移到 LLM 结构化生成链路。",
        DeprecationWarning,
        stacklevel=2,
    )
    return f"{hook}{keyword}{next_keyword}（deprecated-fallback）"
