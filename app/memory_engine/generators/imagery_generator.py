from __future__ import annotations

from app.services.llm_service import llm_service

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


def generate_imagery(method: str, hooks: list[str], keywords: list[str], diversify: bool = False) -> list[str]:
    points = [str(x).strip() for x in (keywords or ["锚点A", "锚点B", "锚点C"]) if str(x).strip()][:9]
    if len(points) < 3:
        points.extend(["锚点A", "锚点B", "锚点C"])
        points = points[:3]

    feedback = "请给出明显不同的新版本画面，避免重复句式。" if diversify else ""
    lines = llm_service.generate_visual_imagery(
        question="",
        content_type=_infer_content_type(method),
        hook_system=_infer_hook_system(method, hooks),
        memory_method=method or "link_method",
        concepts=points,
        visual_anchors=points,
        feedback=feedback,
    )
    return _normalize_imagery(lines)
