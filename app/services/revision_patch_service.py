from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import re
from typing import Literal

from app.memory_engine.visual_mapper import validate_imagery_lines
from app.services.method_composition_service import (
    build_recap_from_strategy,
    generate_composed_draft_parts,
)
from app.services.llm_service import llm_service

RevisionIntentType = Literal["revise_anchor", "revise_style", "revise_imagery", "revise_recap", "finalize_card"]
PatchOpType = Literal[
    "update_anchor_visual",
    "update_output_policy",
    "regenerate_imagery_only",
    "regenerate_recap_only",
]


@dataclass
class RevisionIntent:
    intent_type: RevisionIntentType
    anchor_index: int | None = None
    anchor_visual: str | None = None
    tone: str | None = None
    short_recap: bool = False
    diversify: bool = False


@dataclass
class StrategyPatch:
    op: PatchOpType
    payload: dict


FINALIZE_HINTS = ("生成卡片", "导出卡片", "最终版", "final", "final card", "确认")
ANCHOR_INDEX_RE = re.compile(r"第\s*([一二三四五六七八九十\d]+)\s*(?:层|条|个|点)?")


def _zh_num_to_int(token: str) -> int | None:
    token = (token or "").strip()
    if not token:
        return None
    if token.isdigit():
        return int(token)
    mapping = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
    if token in mapping:
        return mapping[token]
    if token.startswith("十") and len(token) == 2:
        return 10 + mapping.get(token[1], 0)
    if token.endswith("十") and len(token) == 2:
        return mapping.get(token[0], 0) * 10
    return None


def _extract_anchor_index(feedback: str) -> int | None:
    m = ANCHOR_INDEX_RE.search(feedback or "")
    if not m:
        return None
    return _zh_num_to_int(m.group(1))


def _extract_anchor_visual(feedback: str) -> str | None:
    text = (feedback or "").strip()
    for sep in ("改成", "换成", "改为", "换为"):
        if sep in text:
            part = text.split(sep, 1)[1].strip()
            part = re.split(r"[，。；;！!？?\n]", part)[0].strip()
            return part or None
    return None


def _infer_tone(feedback: str) -> str:
    text = (feedback or "").lower()
    if any(k in text for k in ["生活化", "日常", "简单", "朴素"]):
        return "daily"
    if any(k in text for k in ["夸张", "戏剧", "荒谬", "炸裂"]):
        return "wild"
    return "balanced"


def parse_revision_intent(feedback: str) -> RevisionIntent:
    text = (feedback or "").strip()
    lowered = text.lower()

    if any(h in lowered for h in [h.lower() for h in FINALIZE_HINTS]):
        return RevisionIntent(intent_type="finalize_card")
    if any(k in text for k in ["换一个答案", "换一种", "换个版本", "再来一个", "不一样", "另一版"]):
        return RevisionIntent(intent_type="revise_imagery", diversify=True)

    if "复述" in text or "recap" in lowered:
        return RevisionIntent(
            intent_type="revise_recap",
            short_recap=any(k in text for k in ["短", "精简", "简短", "更短"]),
        )

    if "画面" in text or "想象" in text or "imagery" in lowered:
        idx = _extract_anchor_index(text)
        if idx is not None:
            return RevisionIntent(
                intent_type="revise_anchor",
                anchor_index=idx,
                anchor_visual=_extract_anchor_visual(text),
            )
        return RevisionIntent(intent_type="revise_imagery")

    if any(k in text for k in ["生活化", "日常", "夸张", "戏剧", "风格"]):
        return RevisionIntent(intent_type="revise_style", tone=_infer_tone(text))

    idx = _extract_anchor_index(text)
    if idx is not None:
        return RevisionIntent(
            intent_type="revise_anchor",
            anchor_index=idx,
            anchor_visual=_extract_anchor_visual(text),
        )

    return RevisionIntent(intent_type="revise_imagery")


def _pick_anchor_visual_with_fallback(strategy_ir: dict, anchor_index: int, suggested_visual: str | None) -> str:
    anchors = strategy_ir.get("anchors", []) or []
    if not anchors:
        return suggested_visual or "锤子"

    target = anchors[max(0, min(anchor_index - 1, len(anchors) - 1))]
    source = str(target.get("source", "")).strip() or str(target.get("visual", "")).strip() or "要点"
    if suggested_visual:
        return suggested_visual.strip()

    try:
        return llm_service.generate_visual_anchor(
            question=str(strategy_ir.get("task", {}).get("question", "")),
            source=source,
            content_type=str(strategy_ir.get("analysis", {}).get("contentType", "")),
            primary_method=str(strategy_ir.get("strategy", {}).get("primaryMethod", "")),
        )
    except Exception:
        return f"{source}道具"


def build_revision_patches(intent: RevisionIntent, strategy_ir: dict, draft: dict, feedback: str) -> list[StrategyPatch]:
    patches: list[StrategyPatch] = []

    if intent.intent_type == "revise_anchor":
        idx = intent.anchor_index or 1
        visual = _pick_anchor_visual_with_fallback(strategy_ir, idx, intent.anchor_visual)
        patches.append(StrategyPatch(op="update_anchor_visual", payload={"anchorIndex": idx, "visual": visual}))
        patches.append(StrategyPatch(op="regenerate_imagery_only", payload={"mode": "related", "anchorIndex": idx}))
        return patches

    if intent.intent_type == "revise_style":
        tone = intent.tone or _infer_tone(feedback)
        patches.append(StrategyPatch(op="update_output_policy", payload={"tone": tone}))
        patches.append(StrategyPatch(op="regenerate_imagery_only", payload={"mode": "all"}))
        return patches

    if intent.intent_type == "revise_recap":
        if intent.short_recap:
            patches.append(StrategyPatch(op="update_output_policy", payload={"recapStyle": "short_arrow"}))
        patches.append(StrategyPatch(op="regenerate_recap_only", payload={"short": intent.short_recap}))
        return patches

    if intent.intent_type == "revise_imagery":
        patches.append(StrategyPatch(op="regenerate_imagery_only", payload={"mode": "all", "diversify": intent.diversify}))
        return patches

    return patches


def _anchor_visuals(strategy_ir: dict) -> list[str]:
    return [str(item.get("visual", "")).strip() for item in strategy_ir.get("anchors", []) if str(item.get("visual", "")).strip()]


def _related_imagery_indices(method: str, anchor_index: int, visuals_len: int) -> list[int]:
    idx = max(1, anchor_index) - 1
    if method in {"peg_method", "timeline_method", "substitute_method"}:
        return [idx]

    # link_method: anchor[i] 影响 (i-1)->i 与 i->(i+1) 两段
    result: list[int] = []
    if idx - 1 >= 0:
        result.append(idx - 1)
    if idx < max(visuals_len - 1, 1):
        result.append(idx)
    return sorted(set(result))


def _ensure_last_imagery_line(imagery: list[str]) -> list[str]:
    lines = [line for line in imagery if line and line.strip()]
    lines = [line.strip() for line in lines]
    if "现在闭上眼睛想象 5 秒" in lines:
        lines = [line for line in lines if line != "现在闭上眼睛想象 5 秒"]
    lines = lines[:9]
    lines.append("现在闭上眼睛想象 5 秒")
    return lines[:10]


def _regenerate_imagery(
    strategy_ir: dict,
    draft: dict,
    mode: str,
    anchor_index: int | None = None,
    diversify: bool = False,
) -> list[str]:
    composed = generate_composed_draft_parts(strategy_ir, draft, diversify=diversify)
    regenerated_all = _ensure_last_imagery_line(composed["imagery"])
    visuals = composed["keywords"]
    method = str(strategy_ir.get("strategy", {}).get("primaryMethod") or draft.get("memoryMethod", "link_method"))

    if mode == "all" or anchor_index is None:
        return regenerated_all

    current = [str(line).strip() for line in draft.get("imagery", []) if str(line).strip()]
    current = _ensure_last_imagery_line(current) if current else regenerated_all[:]
    related = _related_imagery_indices(method, anchor_index, len(visuals))
    for line_idx in related:
        if 0 <= line_idx < len(current) - 1 and line_idx < len(regenerated_all) - 1:
            current[line_idx] = regenerated_all[line_idx]
    return _ensure_last_imagery_line(current)


def _regenerate_recap(strategy_ir: dict, draft: dict, short: bool = False) -> str:
    visuals = _anchor_visuals(strategy_ir) or [str(x).strip() for x in draft.get("keywords", []) if str(x).strip()]
    if not visuals:
        return str(draft.get("recap", "")).strip()
    points = visuals[:3] if short else visuals
    return build_recap_from_strategy(strategy_ir, points)


def apply_revision_patches(strategy_ir: dict, draft: dict, patches: list[StrategyPatch]) -> tuple[dict, dict]:
    updated_ir = deepcopy(strategy_ir or {})
    updated_draft = deepcopy(draft or {})

    if not updated_ir.get("outputPolicy"):
        updated_ir["outputPolicy"] = {}

    for patch in patches:
        if patch.op == "update_anchor_visual":
            idx = int(patch.payload.get("anchorIndex", 1))
            new_visual = str(patch.payload.get("visual", "")).strip()
            anchors = updated_ir.get("anchors", []) or []
            target_idx = max(0, min(idx - 1, len(anchors) - 1))
            if anchors and new_visual:
                anchors[target_idx]["visual"] = new_visual
                updated_ir["anchors"] = anchors

        elif patch.op == "update_output_policy":
            out = updated_ir.get("outputPolicy", {})
            for key, value in patch.payload.items():
                out[key] = value
            updated_ir["outputPolicy"] = out

        elif patch.op == "regenerate_imagery_only":
            mode = str(patch.payload.get("mode", "all"))
            anchor_index = patch.payload.get("anchorIndex")
            diversify = bool(patch.payload.get("diversify", False))
            imagery = _regenerate_imagery(
                updated_ir,
                updated_draft,
                mode=mode,
                anchor_index=anchor_index,
                diversify=diversify,
            )
            updated_draft["imagery"] = imagery

        elif patch.op == "regenerate_recap_only":
            short = bool(patch.payload.get("short", False))
            updated_draft["recap"] = _regenerate_recap(updated_ir, updated_draft, short=short)

    # 同步 keywords 到 anchors.visual，确保草稿与策略一致
    visuals = _anchor_visuals(updated_ir)
    if len(visuals) >= 3:
        updated_draft["keywords"] = visuals[:9]

    # 轻量校验，不通过时兜底重生成 imagery
    issues = validate_imagery_lines(updated_draft.get("imagery", []), updated_ir.get("anchors", []) or [])
    if issues:
        updated_draft["imagery"] = _regenerate_imagery(updated_ir, updated_draft, mode="all")

    output_policy = updated_ir.get("outputPolicy", {})
    output_policy["keywordCount"] = len(updated_draft.get("keywords", []) or [])
    output_policy["imagerySentenceCount"] = len(updated_draft.get("imagery", []) or [])
    updated_ir["outputPolicy"] = output_policy

    return updated_ir, updated_draft
