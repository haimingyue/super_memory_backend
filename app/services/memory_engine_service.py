"""Memory Engine service (rule + template MVP)."""

from __future__ import annotations

from app.utils.classifier_util import (
    TYPE_LABEL_MAP,
    classify_memory_type,
    select_memory_method,
)
from app.utils.generator_util import generate_memory_blocks
from app.utils.parse_util import parse_user_input
from app.services.llm_service import llm_service


def build_memory_draft(question: str, answer_lines: list[str], raw_text: str | None = None) -> dict:
    answer_text = "\n".join(answer_lines).strip()
    full_raw = raw_text or f"题目：{question}\n答案：\n{answer_text}"
    memory_type = classify_memory_type(question, answer_lines, full_raw)
    type_label = TYPE_LABEL_MAP.get(memory_type, TYPE_LABEL_MAP["general"])
    method, method_label = select_memory_method(memory_type)
    result_blocks = None
    result_text = ""

    # 优先使用大模型生成；失败时回退到规则模板，保证接口稳定可用
    try:
        llm_blocks = llm_service.generate_memory_blocks(
            question=question,
            answer_text=answer_text,
            memory_type=memory_type,
            type_label=type_label,
            method=method,
            method_label=method_label,
        )
        result_blocks = {
            "meta": {
                "typeLabel": type_label,
                "methodLabel": method_label,
            },
            "keywords": llm_blocks["keywords"],
            "imagery": llm_blocks["imagery"],
            "recap": llm_blocks["recap"],
        }
        result_text = (
            f"题型：{type_label}\n"
            f"方法：{method_label}\n"
            f"关键词：{' / '.join(result_blocks['keywords'])}\n"
            "想象画面：\n"
            + "\n".join([f"{i + 1}. {line}" for i, line in enumerate(result_blocks["imagery"])])
            + f"\n快速复述：{result_blocks['recap']}"
        )
    except Exception:
        result_blocks, result_text = generate_memory_blocks(
            memory_type=memory_type,
            type_label=type_label,
            method=method,
            method_label=method_label,
            question=question,
            answer_lines=answer_lines,
        )

    return {
        "type": memory_type,
        "typeLabel": type_label,
        "method": method,
        "methodLabel": method_label,
        "resultBlocks": result_blocks,
        "resultText": result_text,
    }


def run_memory_engine(raw_text: str) -> dict:
    parsed = parse_user_input(raw_text)
    draft_data = build_memory_draft(
        question=parsed["question"],
        answer_lines=parsed["answerLines"],
        raw_text=parsed["raw"],
    )

    return {
        "parsed": parsed,
        "type": draft_data["type"],
        "typeLabel": draft_data["typeLabel"],
        "method": draft_data["method"],
        "methodLabel": draft_data["methodLabel"],
        "resultBlocks": draft_data["resultBlocks"],
        "resultText": draft_data["resultText"],
    }
