import re

_NUMBERED_RE = re.compile(r"^\s*(?:\d+[\.、]|[①②③④⑤⑥⑦⑧⑨⑩]|[(（]\d+[)）]|[一二三四五六七八九十]+、|[-*])")
_ALPHA_RE = re.compile(r"^\s*[A-Za-z][\.\)]")
_DATE_RE = re.compile(r"(\d{4}[-/年]\d{1,2}(?:[-/月]\d{1,2}日?)?|\d{1,2}月\d{0,2}日?)")


def detect_content_type(question: str, answer_lines: list[str]) -> str:
    if not answer_lines:
        return "concept"

    if len(answer_lines) > 8:
        return "large_list"

    if any(_DATE_RE.search(line) for line in answer_lines) or _DATE_RE.search(question):
        return "timeline"

    alpha_hits = sum(1 for line in answer_lines if _ALPHA_RE.search(line))
    if alpha_hits >= max(2, len(answer_lines) // 2):
        return "alphabet_list"

    num_hits = sum(1 for line in answer_lines if _NUMBERED_RE.search(line))
    if num_hits >= max(2, len(answer_lines) // 2):
        return "numbered_list"

    if len(answer_lines) >= 5:
        return "sequence_list"

    return "concept"
