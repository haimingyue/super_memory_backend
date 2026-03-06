from __future__ import annotations

import logging

from app.memory_engine import MemoryStrategyEngine
from app.memory_engine.validator import validate_and_autofix_draft
from app.memory_engine.visual_mapper import (
    build_visual_anchors,
    validate_imagery_lines,
    validate_visual_anchors,
)
from app.services.method_composition_service import (
    apply_secondary_methods_to_anchors,
    choose_method_composition,
    generate_composed_draft_parts,
)
from app.services.memory_card_export_service import build_exportable_memory_card
from app.services.revision_patch_service import (
    apply_revision_patches,
    build_revision_patches,
    parse_revision_intent,
)
from app.services.llm_service import llm_service
from app.services.memory_llm_generator import polish_memory_story_with_llm, build_rule_story

engine = MemoryStrategyEngine()
logger = logging.getLogger(__name__)

ALLOWED_CONTENT_TYPES = {
    "sequence_list",
    "numbered_list",
    "alphabet_list",
    "timeline",
    "concept",
    "large_list",
    "compare_contrast",
}
ALLOWED_HOOK_SYSTEMS = {"none_hooks", "number_hooks", "alphabet_hooks", "date_hooks", "space_hooks"}
ALLOWED_MEMORY_METHODS = {"link_method", "peg_method", "substitute_method", "timeline_method", "contrast_method"}

METHOD_ALIAS = {
    "substitute_word_method": "substitute_method",
    "space_method": "link_method",
}


def _pick_memory_goal(content_type: str) -> str:
    mapping = {
        "timeline": "按时间顺序快速回忆",
        "numbered_list": "按编号稳定回忆",
        "alphabet_list": "按字母线索回忆",
        "compare_contrast": "快速区分对比项",
        "large_list": "分组压缩后回忆",
        "sequence_list": "按步骤连续回忆",
        "concept": "把抽象概念转成画面",
    }
    return mapping.get(content_type, "结构化快速回忆")


def _estimate_difficulty(content_type: str, answer_lines: list[str]) -> str:
    line_count = len(answer_lines)
    if content_type in {"large_list", "compare_contrast"} or line_count >= 8:
        return "hard"
    if line_count >= 4 or content_type in {"timeline", "numbered_list", "sequence_list"}:
        return "medium"
    return "easy"


def _build_analysis_reason(content_type: str, method: str, hook_system: str) -> str:
    hook_text = "启用挂钩" if hook_system != "none_hooks" else "不启用挂钩"
    return f"根据内容结构识别为 {content_type}，主方法选择 {method}，{hook_text}以平衡稳定性与负担。"


def _infer_secondary_methods(primary_method: str, content_type: str) -> list[str]:
    default_map = {
        "link_method": ["substitute_word_method"],
        "peg_method": ["link_method"],
        "timeline_method": ["link_method"],
        "contrast_method": ["substitute_word_method"],
        "substitute_method": ["link_method"],
    }
    secondary = default_map.get(primary_method, ["link_method"])
    if content_type == "compare_contrast" and "contrast_method" not in secondary:
        secondary = ["contrast_method"] + secondary
    return secondary[:2]


def _infer_recap_style(recap: str) -> str:
    text = (recap or "").strip()
    if "→" in text:
        return "arrow_sequence"
    if "=" in text and ";" in text:
        return "indexed_mapping"
    if "|" in text:
        return "contrast_pair"
    return "plain_sequence"


def _normalize_draft_payload(draft: dict, question: str, answer_lines: list[str]) -> dict:
    content_type = str(draft.get("contentType", "concept")).strip() or "concept"
    hook_system = str(draft.get("hookSystem", "none_hooks")).strip() or "none_hooks"
    memory_method = str(draft.get("memoryMethod", "link_method")).strip() or "link_method"
    memory_method = METHOD_ALIAS.get(memory_method, memory_method)

    if content_type not in ALLOWED_CONTENT_TYPES:
        content_type = "concept"
    if hook_system not in ALLOWED_HOOK_SYSTEMS:
        hook_system = "none_hooks"
    if memory_method not in ALLOWED_MEMORY_METHODS:
        memory_method = "link_method"

    return {
        "contentType": content_type,
        "hookSystem": hook_system,
        "memoryMethod": memory_method,
        "keywords": [str(item).strip() for item in draft.get("keywords", []) if str(item).strip()][:9],
        "imagery": [str(item).strip() for item in draft.get("imagery", []) if str(item).strip()][:10],
        "recap": str(draft.get("recap", "")).strip(),
        "contrastMatrix": draft.get("contrastMatrix"),
        "memoryPlan": draft.get("memoryPlan"),
        "question": question,
        "answerLines": answer_lines,
    }


def _build_contrast_matrix(question: str, answer_lines: list[str], draft: dict) -> dict | None:
    content_type = str(draft.get("contentType", "")).strip()
    if content_type != "compare_contrast":
        return None

    a_rows: list[str] = []
    b_rows: list[str] = []
    common_rows: list[str] = []
    for raw in answer_lines:
        line = str(raw).strip()
        lowered = line.lower()
        if not line:
            continue
        if lowered.startswith("tcp"):
            a_rows.append(line.split("：", 1)[-1].split(":", 1)[-1].strip() or line)
        elif lowered.startswith("udp"):
            b_rows.append(line.split("：", 1)[-1].split(":", 1)[-1].strip() or line)
        elif "联系" in line or "共同" in line or "都" in line:
            common_rows.append(line.split("：", 1)[-1].split(":", 1)[-1].strip() or line)

    # 兜底拆分：当答案没写 TCP/UDP 前缀时，至少按顺序填充 A/B/Common。
    if not a_rows and answer_lines:
        a_rows = [answer_lines[0].strip()]
    if not b_rows and len(answer_lines) > 1:
        b_rows = [answer_lines[1].strip()]
    if not common_rows and len(answer_lines) > 2:
        common_rows = [answer_lines[2].strip()]

    keywords = [str(x).strip() for x in draft.get("keywords", []) if str(x).strip()]
    scenes = [str(x).strip() for x in draft.get("imagery", []) if str(x).strip() and "闭上眼睛" not in str(x)][:3]
    if not scenes and keywords:
        scenes = [f"{keywords[0]}对比{keywords[min(1, len(keywords) - 1)]}"][:1]
    if not (a_rows or b_rows or common_rows):
        return None
    return {
        "titleA": "TCP列",
        "titleB": "UDP列",
        "titleCommon": "共同点",
        "a": a_rows[:3],
        "b": b_rows[:3],
        "common": common_rows[:3],
        "scenes": scenes,
        "question": question,
    }


def _sync_memory_plan_with_imagery(draft: dict, question: str) -> dict:
    """Keep imagery and memoryPlan aligned so UI story/scene stay consistent.

    Rule:
    - imagery is the source of truth for display sequence
    - memoryPlan.memory_scenes and final_readable_story are rebuilt from imagery
    - keep existing keyword_visuals/quality when available
    """
    imagery = [str(x).strip() for x in draft.get("imagery", []) if str(x).strip()]
    keywords = [str(x).strip() for x in draft.get("keywords", []) if str(x).strip()]
    if not imagery:
        return draft

    plan = draft.get("memoryPlan") if isinstance(draft.get("memoryPlan"), dict) else {}
    method = str(draft.get("memoryMethod", plan.get("method", "link_method"))).strip() or "link_method"
    topic = str(question or plan.get("topic", "")).strip()
    keyword_visuals = plan.get("keyword_visuals", []) if isinstance(plan.get("keyword_visuals"), list) else []
    quality = plan.get("quality", {"issues": [], "source": "sync_from_imagery"})

    scenes = _build_scene_chain_from_imagery(imagery=imagery, keywords=keywords, method=method)
    polished_story, story_meta = _build_polished_story_from_scenes(
        topic=topic,
        method=method,
        keywords=keywords,
        scenes=scenes,
    )

    draft["memoryPlan"] = {
        "method": method,
        "topic": topic,
        "keywords": keywords,
        "keyword_visuals": keyword_visuals,
        "memory_scenes": scenes[:10],
        "final_readable_story": polished_story,
        "storyMeta": story_meta,
        "quality": quality,
    }
    return draft


def _build_scene_chain_from_imagery(*, imagery: list[str], keywords: list[str], method: str) -> list[dict]:
    scene_lines = [line for line in imagery if line != "现在闭上眼睛想象 5 秒"]
    if not scene_lines:
        scene_lines = imagery[:]

    method_type = method.replace("_method", "")
    scenes: list[dict] = []
    for idx, line in enumerate(scene_lines):
        frm = keywords[idx] if idx < len(keywords) else (keywords[-1] if keywords else "")
        to = keywords[idx + 1] if idx + 1 < len(keywords) else "闭眼想象"
        scenes.append(
            {
                "scene_id": idx + 1,
                "type": method_type,
                "from": frm,
                "to": to,
                "scene": line,
                "why_memorable": "与想象画面一致，便于串联复述",
            }
        )
    return scenes[:10]


def _build_polished_story_from_scenes(*, topic: str, method: str, keywords: list[str], scenes: list[dict]) -> tuple[str, dict]:
    polished = polish_memory_story_with_llm(
        topic=topic,
        method=method,
        keywords=keywords,
        scenes=scenes,
    )
    story = str(polished.get("final_readable_story", "")).strip()
    if not story:
        story = build_rule_story(scenes)
    meta = polished.get("storyMeta", {})
    if not isinstance(meta, dict):
        meta = {
            "style": "story_first",
            "source": "rule_fallback",
            "aligned": False,
            "issues": ["storyMeta 非法，使用回退"],
        }
    return story, meta


def _apply_anchors_to_draft(draft: dict, strategy_ir: dict, regenerate_imagery: bool = True) -> dict:
    anchors = strategy_ir.get("anchors", []) or []
    visuals = [str(item.get("visual", "")).strip() for item in anchors if str(item.get("visual", "")).strip()]

    strategy = strategy_ir.get("strategy", {}) or {}
    hook_policy = strategy.get("hookPolicy", {}) or {}
    draft["memoryMethod"] = str(strategy.get("primaryMethod", draft.get("memoryMethod", "link_method")))
    draft["hookSystem"] = str(hook_policy.get("hookSystem", draft.get("hookSystem", "none_hooks")))
    if len(visuals) >= 3:
        draft["keywords"] = visuals[:9]

    if regenerate_imagery:
        composed = generate_composed_draft_parts(strategy_ir, draft)
        regenerated = composed["imagery"]
        issues = validate_imagery_lines(regenerated, composed.get("anchors", anchors))
        if issues:
            draft["imagery"] = regenerated
        else:
            draft["imagery"] = regenerated
        draft["keywords"] = composed["keywords"]
        draft["recap"] = composed["recap"]
        draft["memoryPlan"] = composed.get("memoryPlan")

    return draft


def build_strategy_ir_from_draft(draft: dict) -> dict:
    question = str(draft.get("question", "")).strip()
    answer_lines = [str(line).strip() for line in draft.get("answerLines", []) if str(line).strip()]
    content_type = str(draft.get("contentType", "concept")).strip() or "concept"
    hook_system = str(draft.get("hookSystem", "none_hooks")).strip() or "none_hooks"
    memory_method = str(draft.get("memoryMethod", "link_method")).strip() or "link_method"
    keywords = [str(item).strip() for item in draft.get("keywords", []) if str(item).strip()][:9]
    imagery = [str(item).strip() for item in draft.get("imagery", []) if str(item).strip()][:10]
    recap = str(draft.get("recap", "")).strip()

    memory_goal = _pick_memory_goal(content_type)
    base_secondary = _infer_secondary_methods(memory_method, content_type)
    prelim_strategy = choose_method_composition(
        content_type=content_type,
        memory_goal=memory_goal,
        anchors=[],
        current_primary=memory_method,
        current_secondary=base_secondary,
        current_hook_system=hook_system,
    )

    source_lines = answer_lines or keywords or [question or "默认要点"]
    anchors = build_visual_anchors(
        question=question,
        answer_lines=source_lines,
        content_type=content_type,
        primary_method=prelim_strategy["primaryMethod"],
        hook_system=prelim_strategy["hookPolicy"]["hookSystem"],
        secondary_methods=prelim_strategy["secondaryMethods"],
    )
    final_strategy = choose_method_composition(
        content_type=content_type,
        memory_goal=memory_goal,
        anchors=anchors,
        current_primary=prelim_strategy["primaryMethod"],
        current_secondary=prelim_strategy["secondaryMethods"],
        current_hook_system=prelim_strategy["hookPolicy"]["hookSystem"],
    )
    anchors = build_visual_anchors(
        question=question,
        answer_lines=source_lines,
        content_type=content_type,
        primary_method=final_strategy["primaryMethod"],
        hook_system=final_strategy["hookPolicy"]["hookSystem"],
        secondary_methods=final_strategy["secondaryMethods"],
    )
    anchors = apply_secondary_methods_to_anchors(anchors, final_strategy["secondaryMethods"])
    anchor_issues = validate_visual_anchors(anchors)
    imagery_issues = validate_imagery_lines(imagery, anchors)
    reason = _build_analysis_reason(content_type, final_strategy["primaryMethod"], final_strategy["hookPolicy"]["hookSystem"])
    if anchor_issues:
        reason += "（visual mapper 已自动兜底）"
    if imagery_issues:
        reason += "（imagery 需要基于 anchors 重建）"

    return {
        "version": "memory_strategy_ir.v1",
        "task": {
            "question": question,
            "rawAnswerLines": answer_lines,
        },
        "analysis": {
            "contentType": content_type,
            "memoryGoal": memory_goal,
            "difficulty": _estimate_difficulty(content_type, answer_lines),
            "reason": reason,
        },
        "strategy": final_strategy,
        "anchors": anchors,
        "outputPolicy": {
            "keywordCount": len(keywords),
            "imagerySentenceCount": len(imagery),
            "recapStyle": _infer_recap_style(recap),
            "tone": "balanced",
            "allowAbstractWords": False,
        },
    }


def run_memory_strategy(raw_text: str) -> dict:
    # LLM 优先：直接完成题型/挂钩/方法/画面/复述的全量规划
    parsed = engine.parse_user_input(raw_text)
    question = parsed["question"]
    answer_lines = parsed["answerLines"]
    degraded = False
    degrade_reason = "none"
    try:
        generated = llm_service.plan_memory_strategy(
            question=question,
            answer_lines=answer_lines,
            raw_text=raw_text,
        )
        generation_source = "llm"
    except TimeoutError as exc:
        logger.warning("run_memory_strategy llm timeout, fallback to rule engine: %s", exc)
        generated = engine.build_draft(raw_text)
        generation_source = "fallback_rule_engine"
        degraded = True
        degrade_reason = "llm_timeout"
    except Exception as exc:
        logger.warning("run_memory_strategy llm invalid payload, fallback to rule engine: %s", exc)
        # 规则兜底
        generated = engine.build_draft(raw_text)
        generation_source = "fallback_rule_engine"
        degraded = True
        degrade_reason = "invalid_llm_payload"

    draft = _normalize_draft_payload(generated, question, answer_lines)
    strategy_ir = build_strategy_ir_from_draft(draft)

    # 关键改动：LLM 成功时优先保留其生成结果，避免被固定模板二次覆盖。
    if generation_source == "llm":
        anchors = strategy_ir.get("anchors", []) or []
        if len(draft.get("keywords", []) or []) < 3:
            draft["keywords"] = [str(item.get("visual", "")).strip() for item in anchors if str(item.get("visual", "")).strip()][:9]
        draft["memoryMethod"] = strategy_ir.get("strategy", {}).get("primaryMethod", draft.get("memoryMethod"))
        draft["hookSystem"] = strategy_ir.get("strategy", {}).get("hookPolicy", {}).get("hookSystem", draft.get("hookSystem"))
        if len(draft.get("imagery", []) or []) < 5 or not draft.get("recap"):
            composed = generate_composed_draft_parts(strategy_ir, draft)
            if len(draft.get("imagery", []) or []) < 5:
                draft["imagery"] = composed["imagery"]
            if not draft.get("recap"):
                draft["recap"] = composed["recap"]
            if composed.get("memoryPlan"):
                draft["memoryPlan"] = composed.get("memoryPlan")
        elif not draft.get("memoryPlan"):
            composed = generate_composed_draft_parts(strategy_ir, draft)
            if composed.get("memoryPlan"):
                draft["memoryPlan"] = composed.get("memoryPlan")
    else:
        draft = _apply_anchors_to_draft(draft, strategy_ir)
        composed = generate_composed_draft_parts(strategy_ir, draft)
        draft["keywords"] = composed["keywords"]
        draft["imagery"] = composed["imagery"]
        draft["recap"] = composed["recap"]
        draft["memoryPlan"] = composed.get("memoryPlan")
        draft["memoryMethod"] = strategy_ir.get("strategy", {}).get("primaryMethod", draft.get("memoryMethod"))
        draft["hookSystem"] = strategy_ir.get("strategy", {}).get("hookPolicy", {}).get("hookSystem", draft.get("hookSystem"))

    strategy_ir = build_strategy_ir_from_draft(draft)
    strategy_ir["analysis"]["reason"] = f"{strategy_ir['analysis']['reason']}（source={generation_source}）"
    strategy_ir, draft, quality = validate_and_autofix_draft(strategy_ir, draft)
    draft = _sync_memory_plan_with_imagery(draft, question)
    draft["contrastMatrix"] = _build_contrast_matrix(question, answer_lines, draft)
    strategy_ir["quality"] = quality
    strategy_ir["outputPolicy"]["keywordCount"] = len(draft.get("keywords", []) or [])
    strategy_ir["outputPolicy"]["imagerySentenceCount"] = len(draft.get("imagery", []) or [])
    return {
        "draft": draft,
        "strategyIr": strategy_ir,
        "meta": {
            "generationSource": generation_source,
            "degraded": degraded,
            "degradeReason": degrade_reason if degraded else "none",
        },
    }


def revise_memory_strategy(draft: dict, feedback: str, strategy_ir: dict | None = None) -> dict:
    # patch-based revise：先识别意图并 patch strategyIr，再局部重生成草稿
    question = str(draft.get("question", "")).strip()
    answer_lines = [str(line).strip() for line in draft.get("answerLines", []) if str(line).strip()]
    normalized = _normalize_draft_payload(draft, question, answer_lines)

    working_ir = strategy_ir or build_strategy_ir_from_draft(normalized)
    intent = parse_revision_intent(feedback)
    patches = build_revision_patches(intent, working_ir, normalized, feedback)

    if patches:
        patched_ir, patched_draft = apply_revision_patches(working_ir, normalized, patches)
    else:
        patched_ir, patched_draft = working_ir, normalized

    # 保证草稿结构完整，并在必要时对齐 anchors
    patched_draft = _normalize_draft_payload(patched_draft, question, answer_lines)
    patched_draft = _apply_anchors_to_draft(patched_draft, patched_ir, regenerate_imagery=False)
    composed = generate_composed_draft_parts(patched_ir, patched_draft)
    patched_draft["keywords"] = composed["keywords"]
    if not patched_draft.get("imagery"):
        patched_draft["imagery"] = composed["imagery"]
    if not patched_draft.get("recap"):
        patched_draft["recap"] = composed["recap"]
    if composed.get("memoryPlan"):
        patched_draft["memoryPlan"] = composed.get("memoryPlan")
    patched_draft["memoryMethod"] = patched_ir.get("strategy", {}).get("primaryMethod", patched_draft.get("memoryMethod"))
    patched_draft["hookSystem"] = patched_ir.get("strategy", {}).get("hookPolicy", {}).get("hookSystem", patched_draft.get("hookSystem"))
    refreshed_ir = build_strategy_ir_from_draft(patched_draft)
    # 尽量保留 patch 后输出策略偏好
    if patched_ir.get("outputPolicy"):
        refreshed_ir["outputPolicy"] = {**refreshed_ir.get("outputPolicy", {}), **patched_ir.get("outputPolicy", {})}
        refreshed_ir["outputPolicy"]["keywordCount"] = len(patched_draft.get("keywords", []) or [])
        refreshed_ir["outputPolicy"]["imagerySentenceCount"] = len(patched_draft.get("imagery", []) or [])
    refreshed_ir, patched_draft, quality = validate_and_autofix_draft(refreshed_ir, patched_draft)
    patched_draft = _sync_memory_plan_with_imagery(patched_draft, question)
    patched_draft["contrastMatrix"] = _build_contrast_matrix(question, answer_lines, patched_draft)
    refreshed_ir["quality"] = quality
    refreshed_ir["outputPolicy"]["keywordCount"] = len(patched_draft.get("keywords", []) or [])
    refreshed_ir["outputPolicy"]["imagerySentenceCount"] = len(patched_draft.get("imagery", []) or [])

    return {
        "draft": patched_draft,
        "strategyIr": refreshed_ir,
        "meta": {
            "generationSource": "patch_flow",
            "degraded": False,
            "degradeReason": "none",
        },
    }


def build_memory_card_from_draft(draft: dict) -> dict:
    return build_exportable_memory_card(
        question=str(draft.get("question", "")).strip(),
        answer_lines=[str(line).strip() for line in draft.get("answerLines", []) if str(line).strip()],
        keywords=[str(x).strip() for x in draft.get("keywords", []) if str(x).strip()],
        imagery=[str(x).strip() for x in draft.get("imagery", []) if str(x).strip()],
        recap=str(draft.get("recap", "")).strip(),
        strategy_ir=draft.get("strategyIr"),
        contrast_matrix=draft.get("contrastMatrix"),
        memory_plan=draft.get("memoryPlan"),
    )
