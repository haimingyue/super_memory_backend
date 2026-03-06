"""Prompt builders for structured memory strategy generation."""

from __future__ import annotations

import json


def build_memory_generation_prompt(
    *,
    method: str,
    topic: str,
    keywords: list[str],
    content_type: str = "",
    hook_system: str = "none_hooks",
    context: str = "",
    diversify: bool = False,
) -> tuple[str, str]:
    """Build system/user prompts for first-pass memory strategy generation."""
    system_prompt = (
        "你是专业记忆术教练。目标不是解释知识，而是生成最容易记住的视觉联想。"
        "必须具体、可视化、动态、夸张、荒谬；抽象词先视觉化替代。"
        "禁止模板化复读，避免固定动作词重复。"
        "输出必须是严格 JSON，不要 markdown，不要额外解释。"
        "场景面向中国学生学习（考研、历史、政治、计算机简答题）。"
    )
    user_prompt = f"""请基于以下输入生成结构化记忆策略 JSON。

输入：
- method: {method}
- topic: {topic}
- content_type: {content_type}
- hook_system: {hook_system}
- keywords: {json.dumps(keywords, ensure_ascii=False)}
- context: {context or "无"}
- diversify: {"true" if diversify else "false"}

输出 JSON schema（严格遵守字段名）：
{{
  "method": "{method}",
  "topic": "{topic}",
  "keywords": ["..."],
  "keyword_visuals": [
    {{
      "keyword": "...",
      "visual": "...",
      "reason": "..."
    }}
  ],
  "memory_scenes": [
    {{
      "scene_id": 1,
      "type": "link|peg|timeline|substitute|contrast",
      "from": "...",
      "to": "...",
      "scene": "...",
      "why_memorable": "..."
    }}
  ],
  "final_readable_story": "..."
}}

规则：
1) keywords 覆盖输入关键词，保留顺序。
2) keyword_visuals 对每个关键词给一个具体可见对象，避免抽象词。
3) memory_scenes 数量 5~10，最后一条 scene 必须是引导闭眼想象（scene 可写该提示）。
4) link_method：突出前一个元素触发下一个元素。
5) peg_method：突出编号钩子与信息绑定。
6) timeline_method：突出时间顺序和变化。
7) contrast_method：突出 A/B 对照和共同点。
8) 不要大量重复“撞/飞/弹起/钉住”等模板动作。
9) 场景句子中文输出，便于直接展示。
"""
    return system_prompt, user_prompt


def build_memory_revision_prompt(
    *,
    method: str,
    topic: str,
    keywords: list[str],
    content_type: str = "",
    hook_system: str = "none_hooks",
    feedback: str = "",
    previous_strategy: dict | None = None,
    context: str = "",
) -> tuple[str, str]:
    """Build system/user prompts for strategy revision."""
    system_prompt = (
        "你是记忆策略修订器。请基于用户反馈最小修改，不要无关重写。"
        "保持结构化 JSON 输出，确保记忆画面具体、动态、可视化。"
    )
    user_prompt = f"""请修订记忆策略并输出严格 JSON。

输入：
- method: {method}
- topic: {topic}
- content_type: {content_type}
- hook_system: {hook_system}
- keywords: {json.dumps(keywords, ensure_ascii=False)}
- context: {context or "无"}
- feedback: {feedback or "无"}
- previous_strategy: {json.dumps(previous_strategy or {}, ensure_ascii=False)}

输出 JSON schema（与原策略一致）：
{{
  "method": "{method}",
  "topic": "{topic}",
  "keywords": ["..."],
  "keyword_visuals": [{{"keyword":"...","visual":"...","reason":"..."}}],
  "memory_scenes": [{{"scene_id":1,"type":"...","from":"...","to":"...","scene":"...","why_memorable":"..."}}],
  "final_readable_story": "..."
}}

修订规则：
1) 尽量保留用户未提到的部分。
2) 若 feedback 要求更生活化/夸张，只改场景风格与动作细节。
3) 若 feedback 指定某条 scene，优先改对应 scene_id。
4) 仍需覆盖全部关键词并保持结构稳定。
"""
    return system_prompt, user_prompt


def build_story_polish_prompt(
    *,
    topic: str,
    method: str,
    keywords: list[str],
    memory_scenes: list[dict],
) -> tuple[str, str]:
    """Build prompt for polishing readable story from fixed scene chain."""
    system_prompt = (
        "你是记忆文案润色器。请把给定场景链改写成自然、顺滑、可读的记忆故事。"
        "禁止引入与输入无关的新核心实体；保持场景顺序；输出严格 JSON。"
    )
    user_prompt = f"""请根据输入生成 JSON：

输入：
- topic: {topic}
- method: {method}
- keywords: {json.dumps(keywords, ensure_ascii=False)}
- memory_scenes: {json.dumps(memory_scenes, ensure_ascii=False)}

输出格式（仅 JSON）：
{{
  "final_readable_story": "...",
  "coverage_keywords": ["..."],
  "style_notes": "..."
}}

约束：
1) 必须按 memory_scenes 顺序叙述。
2) 必须覆盖大部分 keywords（至少 80%）。
3) 允许润色语气与连接词，但不要改写核心信息链。
4) 字数建议 80~280 字，读起来自然流畅，不要机械重复。
"""
    return system_prompt, user_prompt
