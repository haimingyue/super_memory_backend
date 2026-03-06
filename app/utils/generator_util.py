"""Template-based memory block generator."""

from __future__ import annotations

import re

STOPWORDS = {
    "的",
    "和",
    "是",
    "在",
    "与",
    "及",
    "或",
    "一个",
    "一种",
    "这个",
    "那个",
    "进行",
    "通过",
    "以及",
    "包括",
    "需要",
    "可以",
    "主要",
    "使用",
}

PEG_OBJECTS = ["铅笔", "天鹅", "耳朵", "帆船", "钩子", "口哨", "镰刀", "眼镜", "气球"]


def _sanitize_line(line: str) -> str:
    return re.sub(r"^\s*(?:\d+[\.、]|[①②③④⑤⑥⑦⑧⑨⑩]|[(（]\d+[)）]|[一二三四五六七八九十]+、|[A-Za-z][\.\)]|[-*])\s*", "", line).strip()


def _extract_keywords(question: str, answer_lines: list[str]) -> list[str]:
    source = " ".join([question] + answer_lines)
    tokens = re.findall(r"[A-Za-z0-9_+\-]{2,}|[\u4e00-\u9fff]{2,}", source)

    deduped: list[str] = []
    for token in tokens:
        normalized = token.strip("，。；：、（）()[]【】<>《》")
        if not normalized or normalized in STOPWORDS:
            continue
        if normalized not in deduped:
            deduped.append(normalized)
        if len(deduped) >= 9:
            break

    if len(deduped) < 3:
        fallback = [_sanitize_line(line)[:10] for line in answer_lines if _sanitize_line(line)]
        for item in fallback:
            if item and item not in deduped:
                deduped.append(item)
            if len(deduped) >= 3:
                break

    while len(deduped) < 3:
        deduped.append(f"锚点{len(deduped) + 1}")

    return deduped[:9]


def _build_scenes(method: str, points: list[str], keywords: list[str]) -> list[str]:
    usable_points = points[:8] if points else keywords[:8]
    scenes: list[str] = []

    if method == "peg_method":
        for idx, point in enumerate(usable_points[:6]):
            peg = PEG_OBJECTS[idx % len(PEG_OBJECTS)]
            scenes.append(f"{idx + 1}号{peg}突然变成扩音器，边跳舞边大喊“{point}”，声音把地板都震起波纹。")
    elif method == "contrast_matrix_method":
        left = usable_points[0] if usable_points else "对象A"
        right = usable_points[1] if len(usable_points) > 1 else "对象B"
        scenes.extend(
            [
                f"左边舞台站着“{left}”，身上贴满蓝色标签，正推着巨型齿轮前进。",
                f"右边舞台站着“{right}”，披着红色披风，踩着弹簧一步跳到天花板。",
                "两边同时按下按钮，火花在空中拼成差异关键词，像霓虹灯一样反复闪烁。",
            ]
        )
    elif method == "chunk_and_encode_method":
        for idx, point in enumerate(usable_points[:6]):
            scenes.append(f"第{idx + 1}组数字被装进透明盒子，盒子长出轮子冲向终点，牌子上写着“{point}”。")
    elif method == "analogy_method":
        for point in usable_points[:6]:
            scenes.append(f"把“{point}”想成一个会说话的工具箱，它一打开就喷出彩带并示范核心作用。")
    else:
        for idx, point in enumerate(usable_points[:6]):
            nxt = usable_points[(idx + 1) % len(usable_points)] if usable_points else "下一步"
            scenes.append(f"“{point}”像滚球一样撞上“{nxt}”，两者合体后继续冲刺，形成连续剧情。")

    if len(scenes) < 3:
        scenes.append("一个巨型放大镜把关键词照亮，画面夸张到像电影慢镜头。")

    scenes = scenes[:8]
    scenes.append("现在闭上眼睛想象 5 秒")

    if len(scenes) < 4:
        scenes.insert(0, "场景突然切换到巨大的记忆剧场，所有线索都在发光移动。")

    return scenes[:9]


def _build_recap(memory_type: str, points: list[str], keywords: list[str]) -> str:
    if memory_type == "numbered_list":
        pairs = [f"{i + 1}={item}" for i, item in enumerate((points or keywords)[:6])]
        return ";".join(pairs)

    if memory_type == "compare_contrast":
        a = (points[0] if points else keywords[0]) if keywords else "对象A"
        b = (points[1] if len(points) > 1 else (keywords[1] if len(keywords) > 1 else "对象B"))
        return f"A(锚点)={a} | B(锚点)={b} + 关键差异短句"

    chain_items = (points or keywords)[:6]
    if not chain_items:
        chain_items = ["锚点A", "锚点B", "锚点C"]
    return " → ".join(chain_items)


def generate_memory_blocks(
    memory_type: str,
    type_label: str,
    method: str,
    method_label: str,
    question: str,
    answer_lines: list[str],
) -> tuple[dict, str]:
    points = [_sanitize_line(line) for line in answer_lines if _sanitize_line(line)]
    keywords = _extract_keywords(question, points or answer_lines)
    imagery = _build_scenes(method, points, keywords)
    recap = _build_recap(memory_type, points, keywords)

    blocks = {
        "meta": {
            "typeLabel": type_label,
            "methodLabel": method_label,
        },
        "keywords": keywords[:9],
        "imagery": imagery,
        "recap": recap,
    }

    text_parts = [
        f"题型：{type_label}",
        f"方法：{method_label}",
        f"关键词：{' / '.join(blocks['keywords'])}",
        "想象画面：",
        *[f"{idx + 1}. {line}" for idx, line in enumerate(blocks["imagery"])],
        f"快速复述：{blocks['recap']}",
    ]
    return blocks, "\n".join(text_parts)

