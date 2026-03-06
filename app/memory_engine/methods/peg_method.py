"""Deprecated compatibility layer for old template method."""

from __future__ import annotations

import warnings


def build_peg_sentence(index: int, hook: str, keyword: str) -> str:
    """Deprecated: kept only for compatibility with old imports."""
    warnings.warn(
        "build_peg_sentence 已废弃：核心生成逻辑已迁移到 LLM 结构化生成链路。",
        DeprecationWarning,
        stacklevel=2,
    )
    return f"第{index}钩子{hook}绑定{keyword}（deprecated-fallback）"
