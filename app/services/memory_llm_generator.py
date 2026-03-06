"""LLM-driven structured memory strategy generator."""

from __future__ import annotations

import logging

from app.services.llm_service import llm_service
from app.services.memory_prompt_builder import (
    build_memory_generation_prompt,
    build_memory_revision_prompt,
    build_story_polish_prompt,
)
from app.services.memory_result_validator import validate_memory_strategy_result, validate_story_alignment

logger = logging.getLogger(__name__)


def _fallback_strategy(
    *,
    method: str,
    topic: str,
    keywords: list[str],
    reason: str,
) -> dict:
    safe_keywords = [str(x).strip() for x in keywords if str(x).strip()][:9]
    if len(safe_keywords) < 3:
        safe_keywords = (safe_keywords + ["锚点A", "锚点B", "锚点C"])[:3]

    keyword_visuals = [{"keyword": kw, "visual": f"{kw}道具", "reason": f"fallback: {reason}"} for kw in safe_keywords]
    memory_scenes: list[dict] = []
    for idx in range(min(max(len(safe_keywords), 3), 9)):
        cur = safe_keywords[idx % len(safe_keywords)]
        nxt = safe_keywords[(idx + 1) % len(safe_keywords)]
        memory_scenes.append(
            {
                "scene_id": idx + 1,
                "type": method.replace("_method", ""),
                "from": cur,
                "to": nxt,
                "scene": f"{cur}道具推动{nxt}道具穿过教室黑板",
                "why_memorable": "fallback 场景，保证结构完整",
            }
        )
    memory_scenes.append(
        {
            "scene_id": len(memory_scenes) + 1,
            "type": "focus",
            "from": safe_keywords[0],
            "to": safe_keywords[-1],
            "scene": "现在闭上眼睛想象 5 秒",
            "why_memorable": "强化回忆触发",
        }
    )

    return {
        "method": method,
        "topic": topic,
        "keywords": safe_keywords,
        "keyword_visuals": keyword_visuals,
        "memory_scenes": memory_scenes[:10],
        "final_readable_story": "。".join(item["scene"] for item in memory_scenes[:6]),
    }


def generate_memory_strategy_with_llm(
    *,
    method: str,
    topic: str,
    keywords: list[str],
    content_type: str = "",
    hook_system: str = "none_hooks",
    context: str = "",
    feedback: str = "",
    previous_strategy: dict | None = None,
    diversify: bool = False,
) -> dict:
    """Generate structured memory strategy by LLM with validation and fallback."""
    try:
        if previous_strategy:
            system_prompt, user_prompt = build_memory_revision_prompt(
                method=method,
                topic=topic,
                keywords=keywords,
                content_type=content_type,
                hook_system=hook_system,
                feedback=feedback,
                previous_strategy=previous_strategy,
                context=context,
            )
        else:
            system_prompt, user_prompt = build_memory_generation_prompt(
                method=method,
                topic=topic,
                keywords=keywords,
                content_type=content_type,
                hook_system=hook_system,
                context=context,
                diversify=diversify,
            )

        parsed = llm_service.run_structured_json_prompt(system_prompt=system_prompt, user_prompt=user_prompt)
        if not isinstance(parsed, dict):
            raise ValueError("LLM memory strategy result 非 JSON 对象")

        valid, issues, normalized = validate_memory_strategy_result(parsed, required_keywords=keywords, method=method)
        if valid:
            normalized["quality"] = {"issues": [], "source": "llm"}
            return normalized

        logger.warning("Structured strategy validation failed, fallback used. issues=%s", issues)
        fallback = _fallback_strategy(method=method, topic=topic, keywords=keywords, reason="validation_failed")
        fallback["quality"] = {"issues": issues, "source": "fallback"}
        return fallback
    except TimeoutError:
        fallback = _fallback_strategy(method=method, topic=topic, keywords=keywords, reason="timeout")
        fallback["quality"] = {"issues": ["llm_timeout"], "source": "fallback"}
        return fallback
    except Exception as exc:
        logger.warning("generate_memory_strategy_with_llm failed: %s", exc)
        fallback = _fallback_strategy(method=method, topic=topic, keywords=keywords, reason="exception")
        fallback["quality"] = {"issues": [str(exc)], "source": "fallback"}
        return fallback


def build_rule_story(scene_chain: list[dict]) -> str:
    """Deterministic fallback story from scene chain."""
    lines: list[str] = []
    for item in scene_chain:
        if not isinstance(item, dict):
            continue
        text = str(item.get("scene", "")).strip()
        if not text or text == "现在闭上眼睛想象 5 秒":
            continue
        lines.append(text)
    story = "，随后".join(lines)
    if story and not story.endswith("。"):
        story += "。"
    return story


def polish_memory_story_with_llm(
    *,
    topic: str,
    method: str,
    keywords: list[str],
    scenes: list[dict],
) -> dict:
    """Polish final readable story with alignment validation + fallback."""
    fallback_story = build_rule_story(scenes)
    try:
        system_prompt, user_prompt = build_story_polish_prompt(
            topic=topic,
            method=method,
            keywords=keywords,
            memory_scenes=scenes,
        )
        parsed = llm_service.run_structured_json_prompt(system_prompt=system_prompt, user_prompt=user_prompt)
        if not isinstance(parsed, dict):
            raise ValueError("story polish 非 JSON 对象")

        story = str(parsed.get("final_readable_story", "")).strip()
        aligned, issues = validate_story_alignment(story, scenes, keywords)
        if not aligned:
            return {
                "final_readable_story": fallback_story,
                "storyMeta": {
                    "style": "story_first",
                    "source": "rule_fallback",
                    "aligned": False,
                    "issues": issues,
                },
            }
        return {
            "final_readable_story": story,
            "storyMeta": {
                "style": "story_first",
                "source": "llm_polish",
                "aligned": True,
                "issues": [],
                "styleNotes": str(parsed.get("style_notes", "")).strip(),
            },
        }
    except TimeoutError:
        return {
            "final_readable_story": fallback_story,
            "storyMeta": {
                "style": "story_first",
                "source": "rule_fallback",
                "aligned": False,
                "issues": ["llm_timeout"],
            },
        }
    except Exception as exc:
        logger.warning("polish_memory_story_with_llm failed: %s", exc)
        return {
            "final_readable_story": fallback_story,
            "storyMeta": {
                "style": "story_first",
                "source": "rule_fallback",
                "aligned": False,
                "issues": [str(exc)],
            },
        }
