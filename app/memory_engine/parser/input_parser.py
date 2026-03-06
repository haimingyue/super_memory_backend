import re

_PREFIX_RE = re.compile(r"^\s*(?:\d+[\.、]|[①②③④⑤⑥⑦⑧⑨⑩]|[(（]\d+[)）]|[一二三四五六七八九十]+、|[-*])\s*")


def _clean_line(line: str) -> str:
    return _PREFIX_RE.sub("", line).strip()


def _split_long_answer_lines(lines: list[str]) -> list[str]:
    if len(lines) != 1:
        return lines
    only = lines[0].strip()
    if len(only) < 30 or not any(sep in only for sep in ["，", "；", "。", ";", ","]):
        return lines

    parts = re.split(r"[，；。;,]", only)
    chunks = [p.strip() for p in parts if p.strip()]
    if len(chunks) < 2:
        return lines
    return chunks[:9]


def parse_user_input(raw_text: str) -> dict:
    raw = (raw_text or "").strip()
    if not raw:
        raise ValueError("输入不能为空")

    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    if not lines:
        raise ValueError("输入不能为空")

    question = ""
    answer_lines: list[str] = []

    q_idx = next((i for i, line in enumerate(lines) if line.lower().startswith("题目") or line.lower().startswith("question")), -1)
    a_idx = next((i for i, line in enumerate(lines) if line.lower().startswith("答案") or line.lower().startswith("answer")), -1)

    if q_idx >= 0 and a_idx >= 0 and a_idx >= q_idx:
        question = re.sub(r"^\s*(题目|question)\s*[:：]?\s*", "", lines[q_idx], flags=re.IGNORECASE).strip()
        answer_header = lines[a_idx]
        answer_inline = re.sub(r"^\s*(答案|answer)\s*[:：]?\s*", "", answer_header, flags=re.IGNORECASE).strip()
        inline_lines: list[str] = []
        if answer_inline:
            # 允许“答案：xxx”与正文同一行
            inline_lines.append(_clean_line(answer_inline))
        tail_lines = [_clean_line(line) for line in lines[a_idx + 1:] if _clean_line(line)]
        answer_lines = [line for line in inline_lines + tail_lines if line]
    else:
        question = _clean_line(lines[0])
        answer_lines = [_clean_line(line) for line in lines[1:] if _clean_line(line)]

    if not answer_lines:
        answer_lines = [_clean_line(question)]
    answer_lines = _split_long_answer_lines(answer_lines)

    return {
        "question": question or "未命名题目",
        "answerLines": answer_lines,
    }
