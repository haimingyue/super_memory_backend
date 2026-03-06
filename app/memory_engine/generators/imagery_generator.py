from __future__ import annotations

from app.services.memory_llm_generator import generate_memory_strategy_with_llm

FINAL_LINE = "现在闭上眼睛想象 5 秒"


def _infer_content_type(method: str) -> str:
    if method == "peg_method":
        return "numbered_list"
    if method == "timeline_method":
        return "timeline"
    if method == "substitute_method":
        return "concept"
    return "sequence_list"


def _infer_hook_system(method: str, hooks: list[str]) -> str:
    if not hooks:
        return "none_hooks"
    if method == "timeline_method":
        return "date_hooks"
    if method == "peg_method":
        return "number_hooks"
    return "none_hooks"


def _normalize_imagery(lines: list[str]) -> list[str]:
    cleaned = [str(line).strip() for line in lines if str(line).strip()]
    cleaned = [line for line in cleaned if "撞" not in line]
    cleaned = [line for line in cleaned if line != FINAL_LINE]
    cleaned = cleaned[:9]
    cleaned.append(FINAL_LINE)
    return cleaned[:10]


def generate_imagery_structured(
    *,
    method: str,
    hooks: list[str],
    keywords: list[str],
    topic: str = "",
    content_type: str = "",
    feedback: str = "",
    diversify: bool = False,
    previous_strategy: dict | None = None,
) -> dict:
    points = [str(x).strip() for x in (keywords or ["锚点A", "锚点B", "锚点C"]) if str(x).strip()][:9]
    if len(points) < 3:
        points.extend(["锚点A", "锚点B", "锚点C"])
        points = points[:3]

    strategy = generate_memory_strategy_with_llm(
        method=method or "link_method",
        topic=topic or "记忆任务",
        keywords=points,
        content_type=content_type or _infer_content_type(method),
        hook_system=_infer_hook_system(method, hooks),
        context=f"hooks={hooks}" if hooks else "",
        feedback=feedback,
        previous_strategy=previous_strategy,
        diversify=diversify,
    )
    scenes = strategy.get("memory_scenes", []) if isinstance(strategy, dict) else []
    lines = [str(item.get("scene", "")).strip() for item in scenes if isinstance(item, dict) and str(item.get("scene", "")).strip()]
    imagery = _normalize_imagery(lines)
    return {
        "imagery": imagery,
        "strategy": strategy,
    }


def generate_imagery(method: str, hooks: list[str], keywords: list[str], diversify: bool = False) -> list[str]:
    generated = generate_imagery_structured(
        method=method,
        hooks=hooks,
        keywords=keywords,
        diversify=diversify,
        feedback="请给出明显不同的新版本画面，避免重复句式。" if diversify else "",
    )
    return generated["imagery"]
