"""Formatter for final memory card output."""

from __future__ import annotations

from app.schemas.memory_chat import MemoryCard, MemoryDraft


def format_memory_card(question: str, answer_lines: list[str], draft: MemoryDraft) -> MemoryCard:
    keywords_line = " → ".join(draft.keywords)
    imagery_text = "\n".join([f"{idx + 1}. {line}" for idx, line in enumerate(draft.imagery)])
    back = (
        "关键词：\n"
        f"{keywords_line}\n\n"
        "想象画面：\n"
        f"{imagery_text}\n\n"
        "快速复述：\n"
        f"{draft.recap}"
    )
    return MemoryCard(front=question, back=back)
