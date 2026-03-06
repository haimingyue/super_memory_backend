import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.memory_llm_generator import generate_memory_strategy_with_llm, polish_memory_story_with_llm


class TestMemoryLLMGenerator(unittest.TestCase):
    def test_generate_strategy_from_llm_json(self):
        llm_payload = {
            "method": "link_method",
            "topic": "TCP vs UDP",
            "keywords": ["TCP", "UDP", "联系"],
            "keyword_visuals": [
                {"keyword": "TCP", "visual": "挂号信", "reason": "可靠"},
                {"keyword": "UDP", "visual": "纸飞机", "reason": "快速"},
                {"keyword": "联系", "visual": "网线", "reason": "连接"},
            ],
            "memory_scenes": [
                {"scene_id": 1, "type": "contrast", "from": "TCP", "to": "UDP", "scene": "挂号信和纸飞机在跑道竞速", "why_memorable": "强对比"},
                {"scene_id": 2, "type": "contrast", "from": "UDP", "to": "联系", "scene": "纸飞机落在网线上", "why_memorable": "连接感"},
                {"scene_id": 3, "type": "contrast", "from": "联系", "to": "TCP", "scene": "网线缠回挂号信", "why_memorable": "闭环"},
                {"scene_id": 4, "type": "contrast", "from": "TCP", "to": "联系", "scene": "挂号信贴上传输层标签", "why_memorable": "语义绑定"},
                {"scene_id": 5, "type": "focus", "from": "联系", "to": "UDP", "scene": "现在闭上眼睛想象 5 秒", "why_memorable": "强化"},
            ],
            "final_readable_story": "...",
        }
        with patch("app.services.memory_llm_generator.llm_service.run_structured_json_prompt", return_value=llm_payload):
            result = generate_memory_strategy_with_llm(
                method="link_method",
                topic="TCP vs UDP",
                keywords=["TCP", "UDP", "联系"],
                content_type="compare_contrast",
            )

        self.assertEqual(result["method"], "link_method")
        self.assertGreaterEqual(len(result["memory_scenes"]), 5)
        self.assertEqual(result["quality"]["source"], "llm")

    def test_fallback_on_timeout(self):
        with patch("app.services.memory_llm_generator.llm_service.run_structured_json_prompt", side_effect=TimeoutError("timeout")):
            result = generate_memory_strategy_with_llm(
                method="link_method",
                topic="测试",
                keywords=["A", "B", "C"],
            )
        self.assertEqual(result["quality"]["source"], "fallback")
        self.assertIn("memory_scenes", result)

    def test_polish_story_llm_success(self):
        scenes = [
            {"scene_id": 1, "from": "电线", "to": "网线", "scene": "电线缠住网线"},
            {"scene_id": 2, "from": "网线", "to": "路由器", "scene": "网线插入路由器"},
            {"scene_id": 3, "from": "路由器", "to": "快递箱", "scene": "路由器推送快递箱"},
        ]
        payload = {
            "final_readable_story": (
                "先看到电线缠住网线，随后网线插入路由器，路由器持续旋转后把快递箱推向空中，"
                "再回想电线、网线、路由器、快递箱这一整条顺序链，画面衔接自然清晰。"
            ),
            "coverage_keywords": ["电线", "网线", "路由器", "快递箱"],
            "style_notes": "自然连接",
        }
        with patch("app.services.memory_llm_generator.llm_service.run_structured_json_prompt", return_value=payload):
            result = polish_memory_story_with_llm(
                topic="OSI",
                method="link_method",
                keywords=["电线", "网线", "路由器", "快递箱"],
                scenes=scenes,
            )
        self.assertEqual(result["storyMeta"]["source"], "llm_polish")
        self.assertTrue(result["storyMeta"]["aligned"])

    def test_polish_story_fallback_when_invalid(self):
        scenes = [
            {"scene_id": 1, "from": "电线", "to": "网线", "scene": "电线缠住网线"},
            {"scene_id": 2, "from": "网线", "to": "路由器", "scene": "网线插入路由器"},
        ]
        payload = {"final_readable_story": "太短", "coverage_keywords": [], "style_notes": ""}
        with patch("app.services.memory_llm_generator.llm_service.run_structured_json_prompt", return_value=payload):
            result = polish_memory_story_with_llm(
                topic="OSI",
                method="link_method",
                keywords=["电线", "网线", "路由器"],
                scenes=scenes,
            )
        self.assertEqual(result["storyMeta"]["source"], "rule_fallback")
        self.assertFalse(result["storyMeta"]["aligned"])


if __name__ == "__main__":
    unittest.main()
