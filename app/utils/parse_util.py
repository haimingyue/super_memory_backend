"""Input parsing helpers for Memory Engine."""

from __future__ import annotations

import re


def _clean_lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def parse_user_input(raw_text: str) -> dict:
    raw = (raw_text or "").strip()
    if not raw:
        raise ValueError("rawText 不能为空")

    lines = _clean_lines(raw)
    if not lines:
        raise ValueError("输入内容不能为空")

    question = ""
    answer_text = ""

    question_match = re.search(r"(?:^|\n)\s*题目\s*[:：]\s*(.+)", raw, flags=re.IGNORECASE)
    answer_match = re.search(r"(?:^|\n)\s*答案\s*[:：]\s*", raw, flags=re.IGNORECASE)

    if question_match and answer_match:
        question = question_match.group(1).strip()
        answer_start = answer_match.end()
        answer_text = raw[answer_start:].strip()
    else:
        question = lines[0]
        answer_text = "\n".join(lines[1:]).strip()
        if not answer_text:
            answer_text = lines[0]

    answer_lines = _clean_lines(answer_text)

    return {
        "question": question or "未命名题目",
        "answerText": answer_text,
        "answerLines": answer_lines,
        "raw": raw,
    }

