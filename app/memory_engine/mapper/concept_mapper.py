import re


def map_concepts(answer_lines: list[str]) -> list[str]:
    concepts: list[str] = []
    for line in answer_lines:
        s = re.sub(r"^\s*(?:\d+[\.、]|[①②③④⑤⑥⑦⑧⑨⑩]|[(（]\d+[)）]|[一二三四五六七八九十]+、|[-*])\s*", "", line).strip()
        if not s:
            continue
        # 保留冒号前主概念，避免整句过长
        if "：" in s:
            s = s.split("：", 1)[0].strip()
        elif ":" in s:
            s = s.split(":", 1)[0].strip()
        concepts.append(s)
    return concepts
