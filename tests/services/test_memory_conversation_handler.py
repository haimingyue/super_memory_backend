import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.schemas.memory_chat import MemorySession, MemoryDraft, SessionTask
from app.services.memory_conversation_handler import handle_memory_conversation


class TestMemoryConversationHandler(unittest.TestCase):
    def test_general_chat_without_memory_intent(self):
        session = MemorySession(sessionId="s1")
        with patch("app.services.memory_conversation_handler.llm_service.chat", return_value="你好，我可以帮你学习。"):
            resp = handle_memory_conversation(session, "你好，今天学什么？")

        self.assertEqual(resp.replyType, "chat")
        self.assertEqual(resp.mode, "general_chat")
        self.assertIsNone(resp.draft)

    def test_memory_intent_prompts_for_qa(self):
        session = MemorySession(sessionId="s2")
        resp = handle_memory_conversation(session, "帮我背这个")
        self.assertEqual(resp.replyType, "chat")
        self.assertIn("题目+答案", resp.replyText)

    def test_new_task_generates_memory_draft(self):
        session = MemorySession(sessionId="s3")
        strategy_result = {
            "draft": {
                "contentType": "sequence_list",
                "hookSystem": "none_hooks",
                "memoryMethod": "link_method",
                "keywords": ["A", "B", "C"],
                "imagery": ["A推B", "B推C", "现在闭上眼睛想象 5 秒"],
                "recap": "A → B → C",
                "contrastMatrix": None,
            },
            "strategyIr": {
                "version": "memory_strategy_ir.v1",
                "task": {"question": "q", "rawAnswerLines": ["a", "b"]},
                "analysis": {"contentType": "sequence_list", "memoryGoal": "按步骤连续回忆", "difficulty": "easy", "reason": "ok"},
                "strategy": {
                    "primaryMethod": "link_method",
                    "secondaryMethods": [],
                    "hookPolicy": {"useHooks": False, "hookSystem": "none_hooks", "hookPurpose": "-"},
                },
                "anchors": [],
                "outputPolicy": {
                    "keywordCount": 3,
                    "imagerySentenceCount": 3,
                    "recapStyle": "arrow_sequence",
                    "tone": "balanced",
                    "allowAbstractWords": False,
                },
            },
            "meta": {"generationSource": "llm", "degraded": False, "degradeReason": "none"},
        }
        with patch("app.services.memory_conversation_handler.run_memory_strategy", return_value=strategy_result):
            resp = handle_memory_conversation(session, "题目：测试\n答案：\n1.A\n2.B")

        self.assertEqual(resp.replyType, "memory_draft")
        self.assertEqual(resp.mode, "memory_flow")
        self.assertIsNotNone(resp.draft)

    def test_followup_question_not_revision(self):
        session = MemorySession(sessionId="s4")
        session.task = SessionTask(question="OSI", answerLines=["物理层", "链路层"])
        session.draft = MemoryDraft(
            contentType="sequence_list",
            hookSystem="none_hooks",
            memoryMethod="link_method",
            keywords=["电线", "网线", "路由器"],
            imagery=["电线推网线", "网线拉路由器", "现在闭上眼睛想象 5 秒"],
            recap="电线 → 网线 → 路由器",
            contrastMatrix=None,
        )
        with patch("app.services.memory_conversation_handler.llm_service.chat", return_value="因为最后一条是闭眼提示，不是知识点。"):
            resp = handle_memory_conversation(session, "7层为什么有9条？")

        self.assertEqual(resp.replyType, "chat")
        self.assertEqual(resp.mode, "general_chat")

    def test_revision_message_updates_draft(self):
        session = MemorySession(sessionId="s5")
        session.task = SessionTask(question="q", answerLines=["a", "b"])
        session.draft = MemoryDraft(
            contentType="sequence_list",
            hookSystem="none_hooks",
            memoryMethod="link_method",
            keywords=["A", "B", "C"],
            imagery=["A推B", "B推C", "现在闭上眼睛想象 5 秒"],
            recap="A → B → C",
            contrastMatrix=None,
        )
        revised_payload = {
            "draft": {
                "contentType": "sequence_list",
                "hookSystem": "none_hooks",
                "memoryMethod": "link_method",
                "keywords": ["A", "篮球", "C"],
                "imagery": ["A推篮球", "篮球拉C", "现在闭上眼睛想象 5 秒"],
                "recap": "A → 篮球 → C",
                "contrastMatrix": None,
            },
            "strategyIr": None,
            "meta": {"generationSource": "patch_flow", "degraded": False, "degradeReason": "none"},
        }
        with patch("app.services.memory_conversation_handler.revise_memory_strategy", return_value=revised_payload):
            resp = handle_memory_conversation(session, "请把第2条改成篮球")

        self.assertEqual(resp.replyType, "memory_revision")
        self.assertEqual(resp.mode, "memory_flow")
        self.assertIn("篮球", resp.draft.keywords)


if __name__ == "__main__":
    unittest.main()
