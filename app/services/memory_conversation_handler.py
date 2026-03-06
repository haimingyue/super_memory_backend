"""Conversation orchestrator for memory co-creation flow."""

from __future__ import annotations

from app.schemas.memory_chat import (
    MemoryChatResponse,
    MemoryCard,
    MemoryDraft,
    MemorySession,
    MemoryStrategyIR,
    SessionTask,
)
from app.services.memory_strategy_service import (
    build_memory_card_from_draft,
    revise_memory_strategy,
    run_memory_strategy,
)
from app.services.memory_session_manager import session_manager
from app.memory_engine.parser import parse_user_input

FINALIZE_HINTS = ("生成卡片", "导出卡片", "最终版", "final", "final card", "确认")


def _is_new_task_message(message: str) -> bool:
    msg = (message or "").strip()
    if not msg:
        return False
    lines = [line.strip() for line in msg.splitlines() if line.strip()]
    if "题目" in msg and "答案" in msg:
        return True
    if len(lines) >= 3 and ("：" in lines[0] or ":" in lines[0]):
        return True
    return False


def _is_finalize_message(message: str) -> bool:
    msg = (message or "").lower()
    return any(h.lower() in msg for h in FINALIZE_HINTS)


def _draft_to_text(draft: MemoryDraft, reply_type: str = "draft") -> str:
    header = "这是第一版记忆草稿：" if reply_type == "draft" else "已根据你的反馈完成修订："
    return (
        f"{header}\n"
        f"内容类型：{draft.contentType}\n"
        f"挂钩系统：{draft.hookSystem}\n"
        f"记忆方法：{draft.memoryMethod}\n"
        f"关键词：{' / '.join(draft.keywords)}\n"
        "想象画面：\n"
        + "\n".join([f"{i + 1}. {line}" for i, line in enumerate(draft.imagery)])
        + f"\n快速复述：{draft.recap}\n"
        "你可以继续告诉我：更生活化、更多夸张动作、精简关键词，或直接说“生成卡片”。"
    )


def _assistant_question_text() -> str:
    return "请先发送“题目+答案（多行）”。例如：题目：...\\n答案：\\n1....\\n2...."


def handle_memory_conversation(session: MemorySession, message: str) -> MemoryChatResponse:
    user_msg = session_manager.make_message("user", "text", message)
    session.history.append(user_msg)

    if _is_new_task_message(message):
        parsed = parse_user_input(message)
        session.task = SessionTask(question=parsed["question"], answerLines=parsed["answerLines"])
        strategy_data = run_memory_strategy(message)
        draft_data = strategy_data["draft"]
        draft = MemoryDraft(
            contentType=draft_data["contentType"],
            hookSystem=draft_data["hookSystem"],
            memoryMethod=draft_data["memoryMethod"],
            keywords=draft_data["keywords"],
            imagery=draft_data["imagery"],
            recap=draft_data["recap"],
        )
        session.draft = draft
        if strategy_data.get("strategyIr"):
            session.strategyIr = MemoryStrategyIR.model_validate(strategy_data["strategyIr"])
        session.state = "draft_generated"
        reply_text = _draft_to_text(draft, "draft")
        session.history.append(session_manager.make_message("assistant", "memory_draft", reply_text))
        session_manager.save(session)
        return MemoryChatResponse(
            sessionId=session.sessionId,
            replyType="draft",
            replyText=reply_text,
            draft=draft,
            strategyIr=session.strategyIr,
        )

    if not session.task or not session.draft:
        reply_text = _assistant_question_text()
        session.history.append(session_manager.make_message("assistant", "memory_question", reply_text))
        session_manager.save(session)
        return MemoryChatResponse(
            sessionId=session.sessionId,
            replyType="question",
            replyText=reply_text,
            strategyIr=session.strategyIr,
        )

    if _is_finalize_message(message):
        card_payload = build_memory_card_from_draft(
            {
                "question": session.task.question,
                "answerLines": session.task.answerLines,
                "keywords": session.draft.keywords,
                "imagery": session.draft.imagery,
                "recap": session.draft.recap,
                "strategyIr": session.strategyIr.model_dump() if session.strategyIr else None,
            }
        )
        card_data = MemoryCard.model_validate(card_payload)
        session.finalCard = card_data
        session.state = "finalized"
        reply_text = "已生成最终记忆卡片，你可以直接复制或导出。"
        session.history.append(session_manager.make_message("assistant", "memory_card", reply_text))
        session_manager.save(session)
        return MemoryChatResponse(
            sessionId=session.sessionId,
            replyType="final_card",
            replyText=reply_text,
            finalCard=card_data,
            strategyIr=session.strategyIr,
        )

    revise_input = {
        **session.draft.model_dump(),
        "question": session.task.question,
        "answerLines": session.task.answerLines,
    }
    revised_payload = revise_memory_strategy(
        revise_input,
        message,
        strategy_ir=session.strategyIr.model_dump() if session.strategyIr else None,
    )
    revised = revised_payload["draft"]
    draft = MemoryDraft(
        contentType=revised.get("contentType", session.draft.contentType),
        hookSystem=revised.get("hookSystem", session.draft.hookSystem),
        memoryMethod=revised.get("memoryMethod", session.draft.memoryMethod),
        keywords=revised["keywords"],
        imagery=revised["imagery"],
        recap=revised["recap"],
    )
    session.draft = draft
    if revised_payload.get("strategyIr"):
        session.strategyIr = MemoryStrategyIR.model_validate(revised_payload["strategyIr"])
    session.state = "revising"
    reply_text = _draft_to_text(draft, "revision")
    session.history.append(session_manager.make_message("assistant", "memory_revision", reply_text))
    session_manager.save(session)
    return MemoryChatResponse(
        sessionId=session.sessionId,
        replyType="revision",
        replyText=reply_text,
        draft=draft,
        strategyIr=session.strategyIr,
    )
