from __future__ import annotations

from app.memory_engine import MemoryStrategyEngine
from app.services.llm_service import llm_service

engine = MemoryStrategyEngine()


def run_memory_strategy(raw_text: str) -> dict:
    # LLM 优先：直接完成题型/挂钩/方法/画面/复述的全量规划
    parsed = engine.parse_user_input(raw_text)
    try:
        llm_draft = llm_service.plan_memory_strategy(
            question=parsed["question"],
            answer_lines=parsed["answerLines"],
            raw_text=raw_text,
        )
        return {
            **llm_draft,
            "question": parsed["question"],
            "answerLines": parsed["answerLines"],
        }
    except Exception:
        # 规则兜底
        return engine.build_draft(raw_text)


def revise_memory_strategy(draft: dict, feedback: str) -> dict:
    # LLM 优先修订完整策略草稿
    try:
        revised = llm_service.revise_memory_strategy(
            question=draft.get("question", ""),
            answer_lines=draft.get("answerLines", []),
            current_draft=draft,
            feedback=feedback,
        )
        # 固定任务上下文
        revised["question"] = draft.get("question", "")
        revised["answerLines"] = draft.get("answerLines", [])
        return revised
    except Exception:
        return engine.revise_draft(draft, feedback)


def build_memory_card_from_draft(draft: dict) -> dict:
    return engine.build_card(draft)
