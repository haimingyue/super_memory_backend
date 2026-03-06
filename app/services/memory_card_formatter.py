"""Formatter for final memory card output."""

from __future__ import annotations

from app.schemas.memory_chat import MemoryCard, MemoryDraft
from app.services.memory_card_export_service import build_exportable_memory_card


def format_memory_card(question: str, answer_lines: list[str], draft: MemoryDraft) -> MemoryCard:
    payload = build_exportable_memory_card(
        question=question,
        answer_lines=answer_lines,
        keywords=draft.keywords,
        imagery=draft.imagery,
        recap=draft.recap,
        strategy_ir=None,
    )
    return MemoryCard.model_validate(payload)
