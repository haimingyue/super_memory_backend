import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.memory_result_validator import validate_memory_strategy_result, validate_story_alignment


class TestMemoryResultValidator(unittest.TestCase):
    def test_normalize_and_fill_missing_visuals(self):
        raw = {
            "method": "link_method",
            "topic": "遵义会议的意义",
            "keywords": ["遵义会议", "挽救", "转折点"],
            "keyword_visuals": [{"keyword": "遵义会议", "visual": "会议桌", "reason": "具体"}],
            "memory_scenes": [
                {"scene_id": 1, "type": "link", "from": "遵义会议", "to": "挽救", "scene": "会议桌掀起救护车", "why_memorable": "冲突"},
                {"scene_id": 2, "type": "link", "from": "挽救", "to": "转折点", "scene": "救护车冲上急转弯山路", "why_memorable": "动态"},
                {"scene_id": 3, "type": "link", "from": "转折点", "to": "成熟", "scene": "山路挂满红苹果", "why_memorable": "鲜明"},
                {"scene_id": 4, "type": "link", "from": "成熟", "to": "总结", "scene": "苹果变成红旗", "why_memorable": "符号化"},
                {"scene_id": 5, "type": "focus", "from": "总结", "to": "回忆", "scene": "现在闭上眼睛想象 5 秒", "why_memorable": "强化"},
            ],
            "final_readable_story": "...",
        }
        valid, issues, normalized = validate_memory_strategy_result(raw, required_keywords=["遵义会议", "挽救", "转折点"], method="link_method")
        self.assertTrue(valid)
        self.assertEqual(issues, [])
        self.assertGreaterEqual(len(normalized["keyword_visuals"]), 3)

    def test_detect_repetitive_action_word(self):
        raw = {
            "method": "link_method",
            "topic": "测试",
            "keywords": ["A", "B", "C"],
            "keyword_visuals": [
                {"keyword": "A", "visual": "锤子", "reason": ""},
                {"keyword": "B", "visual": "雨伞", "reason": ""},
                {"keyword": "C", "visual": "齿轮", "reason": ""},
            ],
            "memory_scenes": [
                {"scene_id": 1, "type": "link", "from": "A", "to": "B", "scene": "锤子撞雨伞", "why_memorable": ""},
                {"scene_id": 2, "type": "link", "from": "B", "to": "C", "scene": "雨伞撞齿轮", "why_memorable": ""},
                {"scene_id": 3, "type": "link", "from": "C", "to": "A", "scene": "齿轮撞锤子", "why_memorable": ""},
                {"scene_id": 4, "type": "link", "from": "A", "to": "B", "scene": "锤子撞雨伞", "why_memorable": ""},
                {"scene_id": 5, "type": "focus", "from": "A", "to": "C", "scene": "现在闭上眼睛想象 5 秒", "why_memorable": ""},
            ],
            "final_readable_story": "",
        }
        valid, issues, _ = validate_memory_strategy_result(raw, required_keywords=["A", "B", "C"], method="link_method")
        self.assertFalse(valid)
        self.assertTrue(any("动作词重复" in item for item in issues))

    def test_validate_story_alignment_success(self):
        scenes = [
            {"scene_id": 1, "from": "电线", "to": "网线", "scene": "电线缠住网线"},
            {"scene_id": 2, "from": "网线", "to": "路由器", "scene": "网线插入路由器"},
            {"scene_id": 3, "from": "路由器", "to": "快递箱", "scene": "路由器推送快递箱"},
        ]
        story = (
            "先看到电线缠住网线，随后网线慢慢插入路由器，路由器开始旋转并把快递箱推向空中，"
            "最后你回头再次确认电线、网线、路由器和快递箱的顺序，整条链路非常清晰。"
        )
        ok, issues = validate_story_alignment(story, scenes, ["电线", "网线", "路由器", "快递箱"])
        self.assertTrue(ok)
        self.assertEqual(issues, [])

    def test_validate_story_alignment_fail_coverage(self):
        scenes = [
            {"scene_id": 1, "from": "电线", "to": "网线", "scene": "电线缠住网线"},
            {"scene_id": 2, "from": "网线", "to": "路由器", "scene": "网线插入路由器"},
        ]
        story = "这是一个很短的故事。"
        ok, issues = validate_story_alignment(story, scenes, ["电线", "网线", "路由器"])
        self.assertFalse(ok)
        self.assertTrue(any("覆盖率" in x or "过短" in x for x in issues))


if __name__ == "__main__":
    unittest.main()
