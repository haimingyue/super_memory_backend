from __future__ import annotations

from app.memory_engine.generators import generate_imagery, generate_imagery_structured

ABSTRACT_WORDS = {
    "能力",
    "原则",
    "机制",
    "系统",
    "模型",
    "过程",
    "流程",
    "策略",
    "方法",
    "概念",
    "定义",
    "思想",
    "理论",
    "架构",
    "优化",
    "管理",
    "质量",
    "效率",
}


def _is_abstract_text(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return True
    return any(word in t for word in ABSTRACT_WORDS)


def _estimate_abstract_ratio(anchors: list[dict]) -> float:
    if not anchors:
        return 0.0
    abstract = 0
    for item in anchors:
        level = str(item.get("abstractLevel", "")).strip().lower()
        if level == "high":
            abstract += 1
            continue
        if _is_abstract_text(str(item.get("source", ""))):
            abstract += 1
    return abstract / max(len(anchors), 1)


def choose_method_composition(
    content_type: str,
    memory_goal: str,
    anchors: list[dict],
    current_primary: str,
    current_secondary: list[str] | None = None,
    current_hook_system: str = "none_hooks",
) -> dict:
    secondary = (current_secondary or [])[:]
    primary = current_primary or "link_method"
    hook_system = current_hook_system or "none_hooks"

    abstract_ratio = _estimate_abstract_ratio(anchors)
    anchor_count = len(anchors)

    if content_type == "sequence_list":
        primary = "link_method"
        secondary = []
        hook_system = "number_hooks" if anchor_count >= 6 else "none_hooks"
    elif content_type == "numbered_list":
        primary = "peg_method"
        secondary = ["link_method"]
        hook_system = "number_hooks"
    elif content_type in {"concept", "concept_definition"} and abstract_ratio >= 0.34:
        primary = "link_method"
        secondary = ["substitute_word_method"]
        hook_system = "none_hooks"
    elif content_type == "timeline":
        primary = "timeline_method"
        secondary = ["link_method"]
        hook_system = "date_hooks"
    elif content_type == "large_list":
        primary = "space_method" if anchor_count >= 7 else "link_method"
        secondary = []
        hook_system = "space_hooks"

    # 兜底去重
    dedup_secondary: list[str] = []
    for method in secondary:
        if method != primary and method not in dedup_secondary:
            dedup_secondary.append(method)
    secondary = dedup_secondary[:2]

    use_hooks = hook_system != "none_hooks"
    hook_purpose = "用于定位与顺序回忆" if use_hooks else "当前任务不需要额外定位挂钩"

    return {
        "primaryMethod": primary,
        "secondaryMethods": secondary,
        "hookPolicy": {
            "useHooks": use_hooks,
            "hookSystem": hook_system,
            "hookPurpose": hook_purpose,
        },
    }


def _apply_substitute_to_visual(source: str, visual: str) -> str:
    vis = (visual or "").strip()
    src = (source or "").strip()
    if not vis or _is_abstract_text(vis):
        base = src or vis or "概念"
        base = base.replace("系统", "").replace("模型", "").replace("策略", "").replace("方法", "").strip()
        return f"{base or '概念'}道具"
    return vis


def apply_secondary_methods_to_anchors(anchors: list[dict], secondary_methods: list[str]) -> list[dict]:
    if "substitute_word_method" not in secondary_methods and "substitute_method" not in secondary_methods:
        return anchors

    updated: list[dict] = []
    for item in anchors:
        row = {**item}
        row["visual"] = _apply_substitute_to_visual(str(item.get("source", "")), str(item.get("visual", "")))
        if _is_abstract_text(str(item.get("source", ""))):
            row["abstractLevel"] = "medium"
        updated.append(row)
    return updated


def _resolve_generation_method(primary_method: str) -> str:
    if primary_method == "space_method":
        return "link_method"
    return primary_method


def _build_hooks_from_ir(strategy_ir: dict) -> list[str]:
    hook_policy = strategy_ir.get("strategy", {}).get("hookPolicy", {}) or {}
    if not hook_policy.get("useHooks", False):
        return []
    hooks = [str(item.get("hook", "")).strip() for item in strategy_ir.get("anchors", []) if str(item.get("hook", "")).strip()]
    return hooks


def _ensure_last_imagery_line(lines: list[str]) -> list[str]:
    cleaned = [str(line).strip() for line in lines if str(line).strip()]
    cleaned = [line for line in cleaned if line != "现在闭上眼睛想象 5 秒"]
    cleaned = cleaned[:9]
    cleaned.append("现在闭上眼睛想象 5 秒")
    return cleaned[:10]


def _apply_tone(lines: list[str], tone: str) -> list[str]:
    out: list[str] = []
    for line in lines:
        s = line
        if tone == "daily":
            s = s.replace("突然", "慢慢").replace("爆闪", "亮起").replace("卷走", "搬走")
        elif tone == "wild":
            s = s.replace("突然", "轰然").replace("亮起", "爆闪").replace("推着", "狂推着")
        out.append(s)
    return out


def build_recap_from_strategy(strategy_ir: dict, keywords: list[str]) -> str:
    strategy = strategy_ir.get("strategy", {}) or {}
    hook_policy = strategy.get("hookPolicy", {}) or {}
    primary = str(strategy.get("primaryMethod", "link_method"))
    secondary = strategy.get("secondaryMethods", []) or []
    output_policy = strategy_ir.get("outputPolicy", {}) or {}
    recap_style = str(output_policy.get("recapStyle", "plain_sequence"))

    words = [w for w in keywords if w][:9]
    if not words:
        return ""

    if hook_policy.get("useHooks") and hook_policy.get("hookSystem") == "number_hooks" and primary == "peg_method":
        return ";".join([f"{i + 1}={w}" for i, w in enumerate(words)])

    if hook_policy.get("useHooks") and hook_policy.get("hookSystem") == "date_hooks":
        return " ".join([f"T{i + 1}:{w}" for i, w in enumerate(words)])

    if "link_method" in secondary or primary in {"link_method", "space_method"}:
        return " → ".join(words)

    if recap_style == "contrast_pair" and len(words) >= 2:
        return f"A({words[0]}) | B({words[1]})"

    return " → ".join(words)


def generate_composed_draft_parts(strategy_ir: dict, draft: dict, diversify: bool = False) -> dict:
    strategy = strategy_ir.get("strategy", {}) or {}
    primary = str(strategy.get("primaryMethod", draft.get("memoryMethod", "link_method")))
    secondary = strategy.get("secondaryMethods", []) or []
    output_policy = strategy_ir.get("outputPolicy", {}) or {}
    tone = str(output_policy.get("tone", "balanced"))

    anchors = strategy_ir.get("anchors", []) or []
    anchors = apply_secondary_methods_to_anchors(anchors, secondary)
    strategy_ir["anchors"] = anchors

    anchor_keywords = [str(item.get("visual", "")).strip() for item in anchors if str(item.get("visual", "")).strip()][:9]
    draft_keywords = [str(x).strip() for x in draft.get("keywords", []) if str(x).strip()][:9]
    if len(anchor_keywords) >= 3:
        keywords = anchor_keywords
    else:
        merged: list[str] = []
        for item in anchor_keywords + draft_keywords:
            if item and item not in merged:
                merged.append(item)
        keywords = merged[:9]
    if not keywords:
        keywords = ["锚点A", "锚点B", "锚点C"]

    hooks = _build_hooks_from_ir(strategy_ir)
    method_for_generation = _resolve_generation_method(primary)
    generated = generate_imagery_structured(
        method=method_for_generation,
        hooks=hooks,
        keywords=keywords,
        diversify=diversify,
        topic=str(strategy_ir.get("task", {}).get("question", "")).strip(),
        content_type=str(strategy_ir.get("analysis", {}).get("contentType", "")).strip(),
        previous_strategy=draft.get("memoryPlan") if isinstance(draft.get("memoryPlan"), dict) else None,
    )
    imagery = generated["imagery"] if generated.get("imagery") else generate_imagery(method=method_for_generation, hooks=hooks, keywords=keywords, diversify=diversify)
    imagery = _apply_tone(imagery, tone)
    imagery = _ensure_last_imagery_line(imagery)

    recap = build_recap_from_strategy(strategy_ir, keywords)
    return {
        "keywords": keywords,
        "imagery": imagery,
        "recap": recap,
        "anchors": anchors,
        "memoryPlan": generated.get("strategy"),
    }
