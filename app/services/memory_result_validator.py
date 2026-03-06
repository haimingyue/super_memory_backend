"""Validation and normalization for structured memory strategy results."""

from __future__ import annotations

from collections import Counter

REPETITIVE_ACTION_WORDS = ("撞", "飞", "弹起", "钉住")
ABSTRACT_HINT_WORDS = ("机制", "原理", "系统", "策略", "概念", "定义", "思想", "模型")


def _normalize_keywords(keywords: list[str], required_keywords: list[str]) -> list[str]:
    required = [str(x).strip() for x in required_keywords if str(x).strip()]
    got = [str(x).strip() for x in keywords if str(x).strip()]
    merged: list[str] = []
    for item in got + required:
        if item and item not in merged:
            merged.append(item)
    return merged[:9]


def _contains_abstract(text: str) -> bool:
    s = (text or "").strip()
    return any(w in s for w in ABSTRACT_HINT_WORDS)


def validate_memory_strategy_result(
    result: dict,
    *,
    required_keywords: list[str],
    method: str,
) -> tuple[bool, list[str], dict]:
    """Validate and normalize structured LLM result.

    Returns:
        (is_valid, issues, normalized_result)
    """
    issues: list[str] = []
    normalized = dict(result or {})

    if not isinstance(result, dict):
        return False, ["result 不是 JSON 对象"], {}

    normalized["method"] = str(result.get("method", method)).strip() or method
    normalized["topic"] = str(result.get("topic", "")).strip()
    normalized["keywords"] = _normalize_keywords(result.get("keywords", []), required_keywords)

    visuals = result.get("keyword_visuals", [])
    if not isinstance(visuals, list):
        visuals = []
    normalized_visuals: list[dict] = []
    seen_keywords: set[str] = set()
    for item in visuals:
        if not isinstance(item, dict):
            continue
        keyword = str(item.get("keyword", "")).strip()
        visual = str(item.get("visual", "")).strip()
        reason = str(item.get("reason", "")).strip()
        if not keyword or not visual:
            continue
        if keyword in seen_keywords:
            continue
        seen_keywords.add(keyword)
        normalized_visuals.append({"keyword": keyword, "visual": visual, "reason": reason})
    for kw in normalized["keywords"]:
        if kw not in seen_keywords:
            normalized_visuals.append({"keyword": kw, "visual": f"{kw}道具", "reason": "fallback: 缺失视觉化映射"})
    normalized["keyword_visuals"] = normalized_visuals[:12]

    scenes = result.get("memory_scenes", [])
    if not isinstance(scenes, list):
        scenes = []
    normalized_scenes: list[dict] = []
    action_word_counter: Counter[str] = Counter()
    for idx, scene_item in enumerate(scenes):
        if not isinstance(scene_item, dict):
            continue
        scene_text = str(scene_item.get("scene", "")).strip()
        if not scene_text:
            continue
        for w in REPETITIVE_ACTION_WORDS:
            if w in scene_text:
                action_word_counter[w] += 1
        normalized_scenes.append(
            {
                "scene_id": int(scene_item.get("scene_id", idx + 1)),
                "type": str(scene_item.get("type", "")).strip() or method.replace("_method", ""),
                "from": str(scene_item.get("from", "")).strip(),
                "to": str(scene_item.get("to", "")).strip(),
                "scene": scene_text,
                "why_memorable": str(scene_item.get("why_memorable", "")).strip(),
            }
        )

    if len(normalized_scenes) < 5:
        issues.append("memory_scenes 数量不足")
    if len(normalized["keywords"]) < 3:
        issues.append("keywords 数量不足")

    if normalized_scenes:
        frequent = [w for w, cnt in action_word_counter.items() if cnt >= max(3, len(normalized_scenes) - 1)]
        if frequent:
            issues.append(f"动作词重复明显: {','.join(frequent)}")
        abstract_scene_count = sum(1 for item in normalized_scenes if _contains_abstract(item["scene"]))
        if abstract_scene_count >= max(2, len(normalized_scenes) // 2):
            issues.append("scene 过于抽象")
    normalized["memory_scenes"] = normalized_scenes[:10]

    story = str(result.get("final_readable_story", "")).strip()
    if not story and normalized_scenes:
        story = " ".join(item["scene"] for item in normalized_scenes[:6])
    normalized["final_readable_story"] = story

    # 覆盖性：检查关键词是否在 visuals 中出现
    visual_keyword_set = {str(item.get("keyword", "")).strip() for item in normalized["keyword_visuals"]}
    missing = [kw for kw in normalized["keywords"] if kw not in visual_keyword_set]
    if missing:
        issues.append(f"keyword_visuals 未覆盖关键词: {', '.join(missing)}")

    is_valid = len(issues) == 0
    return is_valid, issues, normalized


def validate_story_alignment(
    story: str,
    scenes: list[dict],
    keywords: list[str],
    *,
    min_keyword_coverage: float = 0.8,
) -> tuple[bool, list[str]]:
    """Validate that polished story is aligned with scene chain and keywords."""
    issues: list[str] = []
    text = (story or "").strip()
    if not text:
        return False, ["final_readable_story 为空"]

    if len(text) < 60:
        issues.append("final_readable_story 过短")
    if len(text) > 400:
        issues.append("final_readable_story 过长")

    required_keywords = [str(k).strip() for k in keywords if str(k).strip()]
    if required_keywords:
        covered = sum(1 for kw in required_keywords if kw in text)
        coverage = covered / max(len(required_keywords), 1)
        if coverage < min_keyword_coverage:
            issues.append(f"关键词覆盖率不足: {coverage:.2f}")

    ordered_tokens: list[str] = []
    for scene in scenes or []:
        if not isinstance(scene, dict):
            continue
        frm = str(scene.get("from", "")).strip()
        to = str(scene.get("to", "")).strip()
        if frm:
            ordered_tokens.append(frm)
        if to and to not in {"闭眼想象", "现在闭上眼睛想象 5 秒"}:
            ordered_tokens.append(to)
    # 轻量顺序检验：首尾锚点至少出现
    if ordered_tokens:
        head = ordered_tokens[0]
        tail = ordered_tokens[-1]
        if head and head not in text:
            issues.append("故事未覆盖首个锚点")
        if tail and tail not in text:
            issues.append("故事未覆盖末尾锚点")

    is_valid = len(issues) == 0
    return is_valid, issues
