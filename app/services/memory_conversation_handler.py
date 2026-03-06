"""Conversation orchestrator for memory co-creation flow."""

from __future__ import annotations

from app.schemas.memory_chat import MemoryChatResponse, MemoryDraft, MemorySession, SessionTask
from app.services.llm_service import llm_service
from app.services.memory_card_formatter import format_memory_card
from app.services.memory_engine_service import build_memory_draft
from app.services.memory_session_manager import session_manager
from app.utils.parse_util import parse_user_input

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
        f"题型：{draft.typeLabel}\n"
        f"方法：{draft.methodLabel}\n"
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
        draft_data = build_memory_draft(
            question=parsed["question"],
            answer_lines=parsed["answerLines"],
            raw_text=parsed["raw"],
        )
        draft = MemoryDraft(
            type=draft_data["type"],
            typeLabel=draft_data["typeLabel"],
            method=draft_data["method"],
            methodLabel=draft_data["methodLabel"],
            keywords=draft_data["resultBlocks"]["keywords"],
            imagery=draft_data["resultBlocks"]["imagery"],
            recap=draft_data["resultBlocks"]["recap"],
        )
        session.draft = draft
        session.state = "draft_generated"
        reply_text = _draft_to_text(draft, "draft")
        session.history.append(session_manager.make_message("assistant", "memory_draft", reply_text))
        session_manager.save(session)
        return MemoryChatResponse(
            sessionId=session.sessionId,
            replyType="draft",
            replyText=reply_text,
            draft=draft,
        )

    if not session.task or not session.draft:
        reply_text = _assistant_question_text()
        session.history.append(session_manager.make_message("assistant", "memory_question", reply_text))
        session_manager.save(session)
        return MemoryChatResponse(
            sessionId=session.sessionId,
            replyType="question",
            replyText=reply_text,
        )

    if _is_finalize_message(message):
        card = format_memory_card(
            question=session.task.question,
            answer_lines=session.task.answerLines,
            draft=session.draft,
        )
        session.state = "finalized"
        reply_text = "已生成最终记忆卡片，你可以直接复制或导出。"
        session.history.append(session_manager.make_message("assistant", "memory_final_card", reply_text))
        session_manager.save(session)
        return MemoryChatResponse(
            sessionId=session.sessionId,
            replyType="final_card",
            replyText=reply_text,
            finalCard=card,
        )

    revised = llm_service.revise_draft(
        question=session.task.question,
        answer_text="\n".join(session.task.answerLines),
        draft=session.draft.model_dump(),
        user_feedback=message,
        history=[m.model_dump() for m in session.history],
    )
    draft = MemoryDraft(
        type=session.draft.type,
        typeLabel=session.draft.typeLabel,
        method=session.draft.method,
        methodLabel=session.draft.methodLabel,
        keywords=revised["keywords"],
        imagery=revised["imagery"],
        recap=revised["recap"],
    )
    session.draft = draft
    session.state = "revising"
    reply_text = _draft_to_text(draft, "revision")
    session.history.append(session_manager.make_message("assistant", "memory_revision", reply_text))
    session_manager.save(session)
    return MemoryChatResponse(
        sessionId=session.sessionId,
        replyType="revision",
        replyText=reply_text,
        draft=draft,
    )
