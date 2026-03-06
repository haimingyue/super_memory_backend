import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services import memory_strategy_service as mss


class TestMemoryStrategyService(unittest.TestCase):
    def test_normalize_alias_and_whitelist(self):
        normalized = mss._normalize_draft_payload(
            {
                "contentType": "unknown_type",
                "hookSystem": "unknown_hooks",
                "memoryMethod": "substitute_word_method",
                "keywords": ["A", "B", "C"],
                "imagery": ["x"],
                "recap": "r",
            },
            "q",
            ["a", "b"],
        )
        self.assertEqual(normalized["contentType"], "concept")
        self.assertEqual(normalized["hookSystem"], "none_hooks")
        self.assertEqual(normalized["memoryMethod"], "substitute_method")

    def test_build_contrast_matrix_for_tcp_udp(self):
        draft = {
            "contentType": "compare_contrast",
            "keywords": ["TCP道具", "UDP道具", "联系道具"],
            "imagery": ["TCP推UDP", "UDP跑过联系", "现在闭上眼睛想象 5 秒"],
        }
        lines = [
            "TCP：面向连接，可靠传输",
            "UDP：无连接，不保证可靠",
            "联系：都用于端到端通信",
        ]
        matrix = mss._build_contrast_matrix("TCP vs UDP", lines, draft)
        self.assertIsNotNone(matrix)
        self.assertGreaterEqual(len(matrix["a"]), 1)
        self.assertGreaterEqual(len(matrix["b"]), 1)
        self.assertGreaterEqual(len(matrix["common"]), 1)

    def test_run_memory_strategy_timeout_degrades(self):
        llm_exc = TimeoutError("timeout")
        fallback_draft = {
            "contentType": "compare_contrast",
            "hookSystem": "none_hooks",
            "memoryMethod": "contrast_method",
            "keywords": ["TCP道具", "UDP道具", "联系道具"],
            "imagery": ["TCP推UDP", "UDP拉联系", "现在闭上眼睛想象 5 秒"],
            "recap": "A(TCP) | B(UDP)",
            "question": "TCP vs UDP",
            "answerLines": ["TCP：可靠", "UDP：快", "联系：传输层"],
        }
        fake_ir = {
            "version": "memory_strategy_ir.v1",
            "task": {"question": "TCP vs UDP", "rawAnswerLines": ["TCP：可靠", "UDP：快", "联系：传输层"]},
            "analysis": {"contentType": "compare_contrast", "memoryGoal": "快速区分对比项", "difficulty": "medium", "reason": "ok"},
            "strategy": {
                "primaryMethod": "contrast_method",
                "secondaryMethods": [],
                "hookPolicy": {"useHooks": False, "hookSystem": "none_hooks", "hookPurpose": "-"},
            },
            "anchors": [],
            "outputPolicy": {
                "keywordCount": 3,
                "imagerySentenceCount": 3,
                "recapStyle": "contrast_pair",
                "tone": "balanced",
                "allowAbstractWords": False,
            },
        }

        with patch.object(mss.engine, "parse_user_input", return_value={"question": "TCP vs UDP", "answerLines": ["TCP：可靠", "UDP：快", "联系：传输层"]}), \
             patch.object(mss.llm_service, "plan_memory_strategy", side_effect=llm_exc), \
             patch.object(mss.engine, "build_draft", return_value=fallback_draft), \
             patch.object(mss, "build_strategy_ir_from_draft", return_value=fake_ir), \
             patch.object(mss, "validate_and_autofix_draft", side_effect=lambda ir, dr: (ir, dr, {"qualityScore": 80, "issues": [], "suggestions": [], "autoFixApplied": []})):
            result = mss.run_memory_strategy("题目：TCP vs UDP\n答案：...\n")

        self.assertTrue(result["meta"]["degraded"])
        self.assertEqual(result["meta"]["degradeReason"], "llm_timeout")
        self.assertIn("contrastMatrix", result["draft"])

    def test_sync_memory_plan_adds_story_meta(self):
        draft = {
            "memoryMethod": "link_method",
            "keywords": ["电线", "网线", "路由器"],
            "imagery": ["电线缠住网线", "网线插入路由器", "现在闭上眼睛想象 5 秒"],
            "memoryPlan": {},
        }
        with patch.object(
            mss,
            "polish_memory_story_with_llm",
            return_value={
                "final_readable_story": "先看到电线缠住网线，随后网线插入路由器，最后闭眼回想。",
                "storyMeta": {"style": "story_first", "source": "llm_polish", "aligned": True, "issues": []},
            },
        ):
            synced = mss._sync_memory_plan_with_imagery(draft, "OSI")
        self.assertIn("memoryPlan", synced)
        self.assertIn("final_readable_story", synced["memoryPlan"])
        self.assertEqual(synced["memoryPlan"]["storyMeta"]["source"], "llm_polish")


if __name__ == "__main__":
    unittest.main()
