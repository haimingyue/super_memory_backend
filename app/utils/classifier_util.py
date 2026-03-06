"""Rule-based classifier for memory question types."""

from __future__ import annotations

import re

TYPE_LABEL_MAP = {
    "sequence_list": "顺序型列表",
    "numbered_list": "编号型列表",
    "concept_definition": "概念解释",
    "compare_contrast": "对比型",
    "number_or_code": "数字/代码",
    "general": "通用",
}

METHOD_MAP = {
    "sequence_list": ("link_method", "链式记忆法"),
    "numbered_list": ("peg_method", "数字挂钩法"),
    "concept_definition": ("analogy_method", "类比法"),
    "compare_contrast": ("contrast_matrix_method", "对比矩阵法"),
    "number_or_code": ("chunk_and_encode_method", "分组编码法"),
    "general": ("link_method", "链式记忆法"),
}

_NUMBERED_PREFIX_RE = re.compile(
    r"^\s*(?:\d+[\.、]|[①②③④⑤⑥⑦⑧⑨⑩]|[(（]\d+[)）]|[一二三四五六七八九十]+、|[A-Za-z][\.\)]|[-*])\s*"
)
_SEQUENCE_HINT_RE = re.compile(r"(第一|第二|第三|步骤|流程|顺序|先|然后|最后)")
_CONCEPT_HINT_RE = re.compile(r"(是什么|定义|含义|解释|特点|作用)")
_COMPARE_HINT_RE = re.compile(r"(区别|对比|vs|VS|比较|联系|异同|优缺点)")
_LONG_DIGIT_RE = re.compile(r"\d{8,}")
_GROUPED_DIGIT_RE = re.compile(r"(?:\d[\d\-\(\)\s]{6,}\d)")


def _is_numbered_list(answer_lines: list[str]) -> bool:
    if not answer_lines:
        return False
    matched = sum(1 for line in answer_lines if _NUMBERED_PREFIX_RE.match(line))
    return matched >= 2 and matched >= max(2, len(answer_lines) // 2)


def _is_number_or_code(full_text: str) -> bool:
    if _LONG_DIGIT_RE.search(full_text):
        return True

    grouped_match = _GROUPED_DIGIT_RE.search(full_text)
    if not grouped_match:
        return False

    grouped_digits = re.sub(r"\D", "", grouped_match.group(0))
    return len(grouped_digits) >= 8


def classify_memory_type(question: str, answer_lines: list[str], raw_text: str) -> str:
    joined_answer = "\n".join(answer_lines)
    full_text = f"{question}\n{joined_answer}\n{raw_text}".strip()

    if _COMPARE_HINT_RE.search(question):
        return "compare_contrast"
    if _CONCEPT_HINT_RE.search(question):
        return "concept_definition"
    if len(answer_lines) >= 5 or _SEQUENCE_HINT_RE.search(question) or _SEQUENCE_HINT_RE.search(joined_answer):
        return "sequence_list"
    if _is_numbered_list(answer_lines):
        return "numbered_list"
    if _is_number_or_code(full_text):
        return "number_or_code"
    return "general"


def select_memory_method(memory_type: str) -> tuple[str, str]:
    return METHOD_MAP.get(memory_type, METHOD_MAP["general"])
