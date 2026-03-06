from __future__ import annotations

import re

from app.memory_engine.visual_mapper import build_visual_anchors
from app.services.method_composition_service import build_recap_from_strategy, generate_composed_draft_parts

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

ACTION_WORDS = [
    "推",
    "拉",
    "扔",
    "举",
    "拖",
    "喷",
    "点亮",
    "卷",
    "挂",
    "变",
    "贴",
    "砸",
    "拧",
    "甩",
    "吸",
    "夹",
    "装",
    "搬",
    "拽",
    "弹",
]

PATTERN_TEMPLATES = [
    "突然",
    "点亮",
    "卷走",
    "狂闪",
    "现在闭上眼睛想象 5 秒",
]


def _is_abstract(text: str) -> bool:
    t = (text or "").strip()
    return any(word in t for word in ABSTRACT_WORDS)


def _is_concrete_like(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return False
    if _is_abstract(t):
        return False
    concrete_suffix = ("器", "机", "箱", "锁", "柜", "门", "车", "灯", "图标", "按钮", "牌", "桥", "杯", "伞", "道具")
    if any(t.endswith(suf) for suf in concrete_suffix):
        return True
    return len(t) <= 6 and bool(re.search(r"[\u4e00-\u9fff]", t))


def _detect_action(line: str) -> str:
    for action in ACTION_WORDS:
        if action in line:
            return action
    return ""


def _related_imagery_indices(method: str, anchor_index: int, visuals_len: int) -> list[int]:
    idx = max(1, anchor_index) - 1
    if method in {"peg_method", "timeline_method", "substitute_method"}:
        return [idx]
    related: list[int] = []
    if idx - 1 >= 0:
        related.append(idx - 1)
    if idx < max(visuals_len - 1, 1):
        related.append(idx)
    return sorted(set(related))


def _ensure_last_imagery_line(lines: list[str]) -> list[str]:
    cleaned = [str(line).strip() for line in lines if str(line).strip()]
    cleaned = [line for line in cleaned if line != "现在闭上眼睛想象 5 秒"]
    cleaned = cleaned[:9]
    cleaned.append("现在闭上眼睛想象 5 秒")
    return cleaned[:10]


def _validate_anchors(strategy_ir: dict) -> tuple[list[str], list[str], list[int]]:
    issues: list[str] = []
    suggestions: list[str] = []
    abstract_anchor_indexes: list[int] = []
    anchors = strategy_ir.get("anchors", []) or []

    abstract_count = 0
    for i, anchor in enumerate(anchors):
        source = str(anchor.get("source", "")).strip()
        visual = str(anchor.get("visual", "")).strip()
        idx = i + 1
        if not visual:
            issues.append(f"anchor[{idx}] visual 为空")
            suggestions.append(f"为第{idx}个锚点补充具体物体 visual")
            abstract_anchor_indexes.append(idx)
            continue
        if visual == source and not _is_concrete_like(source):
            issues.append(f"anchor[{idx}] visual 与 source 相同且 source 抽象")
            suggestions.append(f"将第{idx}个锚点替换为具体道具")
            abstract_anchor_indexes.append(idx)
        if not _is_concrete_like(visual):
            issues.append(f"anchor[{idx}] visual 偏抽象")
            suggestions.append(f"将第{idx}个锚点具象化")
            abstract_anchor_indexes.append(idx)
            abstract_count += 1

    if anchors and abstract_count / max(len(anchors), 1) >= 0.5:
        issues.append("anchors 抽象锚点占比过高")
        suggestions.append("优先替换抽象 anchors，减少抽象词重复")

    return issues, suggestions, sorted(set(abstract_anchor_indexes))


def _validate_imagery(strategy_ir: dict, draft: dict) -> tuple[list[str], list[str], bool]:
    issues: list[str] = []
    suggestions: list[str] = []
    imagery = [str(line).strip() for line in draft.get("imagery", []) if str(line).strip()]
    anchors = strategy_ir.get("anchors", []) or []
    visuals = [str(a.get("visual", "")).strip() for a in anchors if str(a.get("visual", "")).strip()]

    if not imagery:
        issues.append("imagery 为空")
        suggestions.append("重生成 imagery")
        return issues, suggestions, True

    action_hits: list[str] = []
    object_line_count = 0
    template_like_count = 0
    abstract_explain_count = 0

    for idx, line in enumerate(imagery):
        if line == "现在闭上眼睛想象 5 秒":
            continue
        has_object = any(v in line for v in visuals) or _is_concrete_like(line)
        action = _detect_action(line)
        if has_object:
            object_line_count += 1
        if action:
            action_hits.append(action)
        if not has_object:
            issues.append(f"imagery[{idx + 1}] 缺少具体物体")
        if not action:
            issues.append(f"imagery[{idx + 1}] 缺少动作")
        if sum(1 for p in PATTERN_TEMPLATES if p in line) >= 2:
            template_like_count += 1
        if any(k in line for k in ["表示", "意味着", "本质", "定义", "主要是"]):
            abstract_explain_count += 1

    if action_hits:
        max_repeat = max(action_hits.count(a) for a in set(action_hits))
        if max_repeat >= max(3, len(action_hits) - 1):
            issues.append("imagery 动作重复过多")
            suggestions.append("重生成 imagery，提升动作多样性")
    else:
        issues.append("imagery 几乎无动作词")
        suggestions.append("重生成 imagery，加入动作词")

    if template_like_count >= max(2, len(imagery) // 2):
        issues.append("imagery 句式模板化明显")
        suggestions.append("重生成 imagery，降低模板化")
    if abstract_explain_count >= max(2, len(imagery) // 2):
        issues.append("imagery 抽象解释句过多")
        suggestions.append("重生成 imagery，改为物体+动作")
    if object_line_count < max(2, len(imagery) // 2):
        issues.append("imagery 具体物体覆盖率偏低")
        suggestions.append("重生成 imagery，增强可视化对象")

    regenerate_needed = any(
        key in " ".join(issues)
        for key in ["动作重复过多", "句式模板化", "抽象解释句过多", "几乎无动作词", "imagery 为空"]
    )
    return issues, suggestions, regenerate_needed


def _validate_recap(strategy_ir: dict, draft: dict) -> tuple[list[str], list[str], bool]:
    issues: list[str] = []
    suggestions: list[str] = []
    recap = str(draft.get("recap", "")).strip()
    content_type = str(strategy_ir.get("analysis", {}).get("contentType", "")).strip()
    primary = str(strategy_ir.get("strategy", {}).get("primaryMethod", "")).strip()

    if not recap:
        issues.append("recap 为空")
        suggestions.append("重生成 recap")
        return issues, suggestions, True

    if len(recap) > 80:
        issues.append("recap 过长，不利于扫读")
        suggestions.append("压缩 recap 长度")

    if content_type in {"sequence_list", "timeline", "large_list"} and "→" not in recap and "T1:" not in recap:
        issues.append("顺序题 recap 未体现顺序结构")
        suggestions.append("使用箭头或时间标记")

    if content_type == "numbered_list" or primary == "peg_method":
        if "=" not in recap and not re.search(r"\b1\b", recap):
            issues.append("编号题 recap 未体现编号")
            suggestions.append("改为 1=...;2=... 形式")

    if any(k in recap for k in ["因为", "所以", "主要是", "意味着", "本质"]):
        issues.append("recap 含解释性长句")
        suggestions.append("改为关键词串联")

    regenerate_needed = any(k in " ".join(issues) for k in ["recap 为空", "过长", "未体现", "解释性长句"])
    return issues, suggestions, regenerate_needed


def _score_from_issues(issue_count: int) -> int:
    score = 100 - issue_count * 8
    return max(0, min(100, score))


def _fix_abstract_anchors(strategy_ir: dict, draft: dict, abstract_indexes: list[int]) -> tuple[dict, dict, list[str]]:
    if not abstract_indexes:
        return strategy_ir, draft, []
    fixed = [x for x in abstract_indexes if x >= 1]
    if not fixed:
        return strategy_ir, draft, []

    anchors = strategy_ir.get("anchors", []) or []
    if not anchors:
        return strategy_ir, draft, []

    source_lines = [str(a.get("source", "")).strip() for a in anchors]
    remapped = build_visual_anchors(
        question=str(strategy_ir.get("task", {}).get("question", "")),
        answer_lines=source_lines,
        content_type=str(strategy_ir.get("analysis", {}).get("contentType", "")),
        primary_method=str(strategy_ir.get("strategy", {}).get("primaryMethod", "link_method")),
        hook_system=str(strategy_ir.get("strategy", {}).get("hookPolicy", {}).get("hookSystem", "none_hooks")),
        secondary_methods=strategy_ir.get("strategy", {}).get("secondaryMethods", []),
    )

    for idx in fixed:
        if idx - 1 < len(anchors) and idx - 1 < len(remapped):
            anchors[idx - 1]["visual"] = remapped[idx - 1]["visual"]
            anchors[idx - 1]["abstractLevel"] = remapped[idx - 1]["abstractLevel"]
    strategy_ir["anchors"] = anchors
    anchor_keywords = [str(a.get("visual", "")).strip() for a in anchors if str(a.get("visual", "")).strip()][:9]
    existing_keywords = [str(x).strip() for x in draft.get("keywords", []) if str(x).strip()][:9]
    if len(anchor_keywords) >= 3:
        draft["keywords"] = anchor_keywords
    else:
        merged: list[str] = []
        for item in anchor_keywords + existing_keywords:
            if item and item not in merged:
                merged.append(item)
        draft["keywords"] = merged[:9]

    composed = generate_composed_draft_parts(strategy_ir, draft)
    method = str(strategy_ir.get("strategy", {}).get("primaryMethod", "link_method"))
    related_lines: set[int] = set()
    for idx in fixed:
        for li in _related_imagery_indices(method, idx, len(draft.get("keywords", []))):
            related_lines.add(li)

    current = _ensure_last_imagery_line([str(line).strip() for line in draft.get("imagery", []) if str(line).strip()])
    regen = _ensure_last_imagery_line(composed["imagery"])
    if not current:
        draft["imagery"] = regen
    else:
        for li in sorted(related_lines):
            if 0 <= li < len(current) - 1 and li < len(regen) - 1:
                current[li] = regen[li]
        draft["imagery"] = _ensure_last_imagery_line(current)

    return strategy_ir, draft, [f"修复抽象 anchors: {', '.join(str(i) for i in fixed)}"]


def _fix_imagery(strategy_ir: dict, draft: dict) -> tuple[dict, dict, list[str]]:
    composed = generate_composed_draft_parts(strategy_ir, draft)
    draft["imagery"] = _ensure_last_imagery_line(composed["imagery"])
    return strategy_ir, draft, ["重生成 imagery（动作/句式优化）"]


def _fix_recap(strategy_ir: dict, draft: dict) -> tuple[dict, dict, list[str]]:
    keywords = [str(x).strip() for x in draft.get("keywords", []) if str(x).strip()][:9]
    recap = build_recap_from_strategy(strategy_ir, keywords)
    if len(recap) > 80:
        parts = [p.strip() for p in recap.replace(";", "；").split("；") if p.strip()]
        if parts:
            recap = "；".join(parts[:3])
        if len(recap) > 80:
            recap = recap[:80]
    draft["recap"] = recap
    return strategy_ir, draft, ["重生成 recap（压缩与结构化）"]


def validate_and_autofix_draft(strategy_ir: dict, draft: dict) -> tuple[dict, dict, dict]:
    ir = {**strategy_ir}
    dr = {**draft}
    auto_fixes: list[str] = []

    anchor_issues, anchor_suggestions, abstract_idx = _validate_anchors(ir)
    imagery_issues, imagery_suggestions, imagery_need_fix = _validate_imagery(ir, dr)
    recap_issues, recap_suggestions, recap_need_fix = _validate_recap(ir, dr)

    if abstract_idx:
        ir, dr, fixes = _fix_abstract_anchors(ir, dr, abstract_idx[:3])
        auto_fixes.extend(fixes)
    if imagery_need_fix:
        ir, dr, fixes = _fix_imagery(ir, dr)
        auto_fixes.extend(fixes)
    if recap_need_fix:
        ir, dr, fixes = _fix_recap(ir, dr)
        auto_fixes.extend(fixes)

    # 复检并给最终评分
    anchor_issues2, anchor_suggestions2, _ = _validate_anchors(ir)
    imagery_issues2, imagery_suggestions2, _ = _validate_imagery(ir, dr)
    recap_issues2, recap_suggestions2, _ = _validate_recap(ir, dr)

    final_issues = anchor_issues2 + imagery_issues2 + recap_issues2
    final_suggestions = list(dict.fromkeys(anchor_suggestions2 + imagery_suggestions2 + recap_suggestions2))
    score = _score_from_issues(len(final_issues))
    quality = {
        "qualityScore": score,
        "issues": final_issues[:20],
        "suggestions": final_suggestions[:20],
        "autoFixApplied": auto_fixes,
    }
    return ir, dr, quality
