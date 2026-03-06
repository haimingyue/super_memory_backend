from __future__ import annotations

import re

from app.memory_engine.formatter import format_memory_card
from app.memory_engine.generators import generate_imagery
from app.memory_engine.hook_library import ALPHABET_HOOKS, DATE_HOOKS, NUMBER_HOOKS, SPACE_HOOKS
from app.memory_engine.mapper import map_concepts, map_visual_anchors
from app.memory_engine.parser import parse_user_input
from app.memory_engine.planner import detect_content_type, select_hook_system, select_memory_method


class MemoryStrategyEngine:
    def parse_user_input(self, raw_text: str) -> dict:
        return parse_user_input(raw_text)

    def build_draft(self, raw_text: str) -> dict:
        parsed = self.parse_user_input(raw_text)
        return self.build_draft_from_task(parsed["question"], parsed["answerLines"])

    def build_draft_from_task(self, question: str, answer_lines: list[str]) -> dict:
        content_type = detect_content_type(question, answer_lines)
        hook_system = select_hook_system(content_type)
        memory_method = select_memory_method(content_type)

        concepts = map_concepts(answer_lines)
        keywords = map_visual_anchors(question, concepts)
        hooks = self._resolve_hooks(hook_system, len(keywords))
        imagery = generate_imagery(memory_method, hooks, keywords)
        recap = self._build_recap(content_type, concepts)

        return {
            "contentType": content_type,
            "hookSystem": hook_system,
            "memoryMethod": memory_method,
            "keywords": keywords,
            "imagery": imagery,
            "recap": recap,
            "question": question,
            "answerLines": answer_lines,
        }

    def revise_draft(self, draft: dict, feedback: str) -> dict:
        text = (feedback or "").strip().lower()
        style = "balanced"
        if any(k in text for k in ["生活", "简单", "日常"]):
            style = "daily"
        elif any(k in text for k in ["夸张", "荒谬", "戏剧"]):
            style = "wild"

        keywords = draft.get("keywords", [])[:]
        if "关键词" in text and any(k in text for k in ["短", "精简", "少"]):
            keywords = keywords[: max(3, min(6, len(keywords)))]

        hooks = self._resolve_hooks(draft.get("hookSystem", "none_hooks"), len(keywords))
        imagery = generate_imagery(draft.get("memoryMethod", "link_method"), hooks, keywords)
        imagery = [self._apply_style(line, style) for line in imagery]

        new_draft = {
            **draft,
            "keywords": keywords,
            "imagery": imagery,
        }
        return new_draft

    def build_card(self, draft: dict) -> dict:
        card_format = format_memory_card(
            question=draft.get("question", ""),
            keywords=draft.get("keywords", []),
            imagery=draft.get("imagery", []),
            recap=draft.get("recap", ""),
        )
        return {
            "front": card_format["front"],
            "back": card_format["back"],
        }

    def _resolve_hooks(self, hook_system: str, size: int) -> list[str]:
        size = max(1, size)
        if hook_system == "none_hooks":
            return []
        if hook_system == "alphabet_hooks":
            seq = [ALPHABET_HOOKS[k] for k in sorted(ALPHABET_HOOKS.keys())]
        elif hook_system == "date_hooks":
            seq = [DATE_HOOKS[k] for k in sorted(DATE_HOOKS.keys())]
        elif hook_system == "space_hooks":
            seq = SPACE_HOOKS[:]
        else:
            seq = [NUMBER_HOOKS[k] for k in sorted(NUMBER_HOOKS.keys())]

        if len(seq) >= size:
            return seq[:size]
        repeats = (size + len(seq) - 1) // len(seq)
        return (seq * repeats)[:size]

    @staticmethod
    def _extract_keywords(question: str, answer_lines: list[str]) -> list[str]:
        text = " ".join([question] + answer_lines)
        tokens = re.findall(r"[A-Za-z0-9_+-]{2,}|[\u4e00-\u9fff]{2,}", text)
        deny = {"题目", "答案", "模型", "系统", "定义", "区别", "内容", "知识"}
        out: list[str] = []
        for token in tokens:
            t = token.strip("，。；：、（）()[]【】")
            if not t or t in deny:
                continue
            if t not in out:
                out.append(t)
            if len(out) >= 9:
                break

        if len(out) < 3:
            for line in answer_lines:
                s = line.strip()
                if s and s not in out:
                    out.append(s)
                if len(out) >= 3:
                    break

        return out[:9]

    @staticmethod
    def _build_recap(content_type: str, concepts: list[str]) -> str:
        cleaned = [line.strip() for line in concepts if line.strip()]
        if content_type == "numbered_list":
            return " ".join([f"{i + 1} {line}" for i, line in enumerate(cleaned)])
        if content_type in {"timeline"}:
            return " ".join([f"时间点{i + 1} {line}" for i, line in enumerate(cleaned)])
        return " → ".join(cleaned)

    @staticmethod
    def _apply_style(sentence: str, style: str) -> str:
        if style == "daily":
            return sentence.replace("突然", "慢慢").replace("甩到天花板", "放到桌上")
        if style == "wild":
            return sentence.replace("突然", "轰然").replace("乱飞", "爆炸般乱飞")
        return sentence
