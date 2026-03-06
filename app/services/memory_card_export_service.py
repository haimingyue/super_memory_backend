from __future__ import annotations

import json
import uuid


def _build_back(keywords: list[str], imagery: list[str], recap: str, contrast_matrix: dict | None = None) -> str:
    base = (
        "关键词：\n"
        + " → ".join(keywords)
        + "\n\n想象画面：\n"
        + "\n".join([f"{i + 1}. {line}" for i, line in enumerate(imagery)])
        + "\n\n快速复述：\n"
        + recap
    )
    if not contrast_matrix:
        return base
    a = contrast_matrix.get("a", []) or []
    b = contrast_matrix.get("b", []) or []
    common = contrast_matrix.get("common", []) or []
    compare_text = (
        "\n\n对比矩阵：\n"
        + "TCP列："
        + ("；".join([str(x).strip() for x in a if str(x).strip()]) or "-")
        + "\nUDP列："
        + ("；".join([str(x).strip() for x in b if str(x).strip()]) or "-")
        + "\n共同点："
        + ("；".join([str(x).strip() for x in common if str(x).strip()]) or "-")
    )
    return base + compare_text


def _build_strategy_summary(strategy_ir: dict | None) -> dict:
    strategy = (strategy_ir or {}).get("strategy", {}) or {}
    hook_policy = strategy.get("hookPolicy", {}) or {}
    quality = (strategy_ir or {}).get("quality", {}) or {}
    primary = str(strategy.get("primaryMethod", "link_method"))
    secondary = strategy.get("secondaryMethods", []) or []
    hook_system = str(hook_policy.get("hookSystem", "none_hooks"))
    quality_score = quality.get("qualityScore")
    summary_text = f"{primary} + {', '.join(secondary) if secondary else 'no_secondary'} @ {hook_system}"
    return {
        "primaryMethod": primary,
        "secondaryMethods": secondary,
        "hookSystem": hook_system,
        "qualityScore": quality_score if isinstance(quality_score, int) else None,
        "summaryText": summary_text,
    }


def build_exportable_memory_card(
    *,
    question: str,
    answer_lines: list[str],
    keywords: list[str],
    imagery: list[str],
    recap: str,
    strategy_ir: dict | None = None,
    contrast_matrix: dict | None = None,
) -> dict:
    front = question
    back = _build_back(keywords, imagery, recap, contrast_matrix=contrast_matrix)
    answer = "\n".join(answer_lines)
    strategy_summary = _build_strategy_summary(strategy_ir)
    anchors = (strategy_ir or {}).get("anchors", []) or []
    quality = (strategy_ir or {}).get("quality", {}) or {}
    structured = {
        "question": question,
        "answerLines": answer_lines,
        "keywords": keywords,
        "imagery": imagery,
        "recap": recap,
        "contrastMatrix": contrast_matrix,
        "strategySummary": strategy_summary,
        "quality": quality,
        "anchors": anchors,
    }
    anki_text = f"{front}\t{back}"

    return {
        "id": str(uuid.uuid4()),
        "front": front,
        "back": back,
        "question": question,
        "answer": answer,
        "keywords": keywords,
        "imagery": imagery,
        "recap": recap,
        "strategySummary": strategy_summary,
        "cardFormat": {
            "standard": {"front": front, "back": back},
            "ankiText": anki_text,
            "structured": structured,
        },
    }


def card_to_structured_json(card: dict) -> str:
    return json.dumps(card.get("cardFormat", {}).get("structured", card), ensure_ascii=False, indent=2)
