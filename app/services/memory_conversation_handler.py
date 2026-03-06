"""Conversation orchestrator for unified general chat + memory workflow."""

from __future__ import annotations

import logging

from app.schemas.memory_chat import (
    MemoryChatResponse,
    MemoryCard,
    MemoryDraft,
    MemorySession,
    MemoryStrategyIR,
    SessionTask,
)
from app.services.llm_service import llm_service
from app.services.memory_strategy_service import (
    build_memory_card_from_draft,
    revise_memory_strategy,
    run_memory_strategy,
)
from app.services.memory_session_manager import session_manager
from app.memory_engine.parser import parse_user_input

logger = logging.getLogger(__name__)

FINALIZE_HINTS = ("生成卡片", "导出卡片", "最终版", "final", "final card", "确认")
MEMORY_REQUEST_HINTS = ("记忆", "背", "背诵", "记住", "卡片", "联想", "记忆法", "记忆方案")
REVISION_HINTS = (
    "改",
    "换",
    "重写",
    "重生成",
    "重新",
    "再来",
    "另一版",
    "画面",
    "想象",
    "关键词",
    "复述",
    "生活化",
    "夸张",
    "风格",
)


def _is_new_task_message(message: str) -> bool:
    msg = (message or "").strip()
    if not msg:
        return False
    lines = [line.strip() for line in msg.splitlines() if line.strip()]
    has_question_header = any(line.lower().startswith("题目") or line.lower().startswith("question") for line in lines)
    has_answer_header = any(line.lower().startswith("答案") or line.lower().startswith("answer") for line in lines)
    return has_question_header and has_answer_header


def _is_finalize_message(message: str) -> bool:
    msg = (message or "").lower()
    return any(h.lower() in msg for h in FINALIZE_HINTS)


def _is_memory_intent_message(message: str) -> bool:
    msg = (message or "").strip().lower()
    if not msg:
        return False
    return any(k in msg for k in MEMORY_REQUEST_HINTS)


def _is_revision_message(message: str) -> bool:
    msg = (message or "").strip()
    if not msg:
        return False
    return any(k in msg for k in REVISION_HINTS)


def _assistant_question_text() -> str:
    return "请发送“题目+答案（多行）”，我会自动选记忆方法并生成方案。例如：题目：...\\n答案：\\n1....\\n2...."


def _draft_to_text(draft: MemoryDraft, reply_type: str = "memory_draft") -> str:
    header = "这是第一版记忆草稿：" if reply_type == "memory_draft" else "已根据你的反馈完成修订："
    matrix_text = ""
    if draft.contrastMatrix:
        a = draft.contrastMatrix.get("a", []) or []
        b = draft.contrastMatrix.get("b", []) or []
        common = draft.contrastMatrix.get("common", []) or []
        matrix_text = (
            "\n对比矩阵：\n"
            f"TCP列：{'；'.join(a) if a else '-'}\n"
            f"UDP列：{'；'.join(b) if b else '-'}\n"
            f"共同点：{'；'.join(common) if common else '-'}\n"
        )
    return (
        f"{header}\n"
        f"内容类型：{draft.contentType}\n"
        f"挂钩系统：{draft.hookSystem}\n"
        f"记忆方法：{draft.memoryMethod}\n"
        f"关键词：{' / '.join(draft.keywords)}\n"
        + matrix_text
        + "想象画面：\n"
        + "\n".join([f"{i + 1}. {line}" for i, line in enumerate(draft.imagery)])
        + f"\n快速复述：{draft.recap}\n"
        + "你可以继续聊天，也可以说“请把第2条改成…”或“生成卡片”。"
    )


def _build_chat_messages(session: MemorySession, memory_context: str = "") -> list[dict]:
    messages: list[dict] = []
    if memory_context:
        messages.append({"role": "assistant", "content": memory_context})
    for item in session.history[-12:]:
        if item.type not in {"text", "memory_question"}:
            continue
        content = (item.content or "").strip()
        if not content:
            continue
        messages.append({"role": item.role, "content": content})
    return messages


def _general_chat_reply(session: MemorySession, memory_context: str = "") -> tuple[str, bool, str]:
    try:
        reply_text = llm_service.chat(_build_chat_messages(session, memory_context=memory_context))
        return reply_text, False, "none"
    except TimeoutError:
        return "我这次回复超时了。你可以再发一次，或直接给我“题目+答案”让我开始生成记忆方案。", True, "llm_timeout"
    except Exception:
        return "我暂时无法完整回复，但可以继续聊天，或先帮你做记忆方案。", True, "invalid_llm_payload"


def _log_route(
    *,
    session: MemorySession,
    mode_before: str,
    mode_after: str,
    route_decision: str,
    generation_source: str,
    degrade_reason: str,
) -> None:
    logger.info(
        "memory.chat route session=%s mode_before=%s mode_after=%s route_decision=%s generation_source=%s degrade_reason=%s",
        session.sessionId,
        mode_before,
        mode_after,
        route_decision,
        generation_source,
        degrade_reason,
    )


def handle_memory_conversation(session: MemorySession, message: str) -> MemoryChatResponse:
    mode_before = session.conversationMode
    user_msg = session_manager.make_message("user", "text", message)
    session.history.append(user_msg)

    # 1) finalize 优先
    if _is_finalize_message(message):
        if not session.task or not session.draft:
            reply_text = "当前还没有可导出的记忆草稿。先发“题目+答案”，我会自动生成。"
            session.history.append(session_manager.make_message("assistant", "memory_question", reply_text))
            session_manager.save(session)
            _log_route(
                session=session,
                mode_before=mode_before,
                mode_after=session.conversationMode,
                route_decision="finalize_without_draft",
                generation_source="none",
                degrade_reason="none",
            )
            return MemoryChatResponse(
                sessionId=session.sessionId,
                replyType="chat",
                replyText=reply_text,
                mode=session.conversationMode,
                triggeredBy="finalize",
                degraded=False,
                degradeReason="none",
                strategyIr=session.strategyIr,
            )

        card_payload = build_memory_card_from_draft(
            {
                "question": session.task.question,
                "answerLines": session.task.answerLines,
                "keywords": session.draft.keywords,
                "imagery": session.draft.imagery,
                "recap": session.draft.recap,
                "contrastMatrix": session.draft.contrastMatrix,
                "strategyIr": session.strategyIr.model_dump() if session.strategyIr else None,
            }
        )
        card_data = MemoryCard.model_validate(card_payload)
        session.finalCard = card_data
        session.state = "finalized"
        session.conversationMode = "memory_flow"
        reply_text = "已生成最终记忆卡片，你可以直接复制或导出。"
        session.history.append(session_manager.make_message("assistant", "memory_card", reply_text))
        session_manager.save(session)
        _log_route(
            session=session,
            mode_before=mode_before,
            mode_after=session.conversationMode,
            route_decision="finalize",
            generation_source="card_export",
            degrade_reason="none",
        )
        return MemoryChatResponse(
            sessionId=session.sessionId,
            replyType="memory_card",
            replyText=reply_text,
            mode=session.conversationMode,
            triggeredBy="finalize",
            degraded=False,
            degradeReason="none",
            finalCard=card_data,
            strategyIr=session.strategyIr,
        )

    # 2) new_task
    if _is_new_task_message(message):
        parsed = parse_user_input(message)
        session.task = SessionTask(question=parsed["question"], answerLines=parsed["answerLines"])
        strategy_data = run_memory_strategy(message)
        draft_data = strategy_data["draft"]
        meta = strategy_data.get("meta", {}) or {}
        draft = MemoryDraft(
            contentType=draft_data["contentType"],
            hookSystem=draft_data["hookSystem"],
            memoryMethod=draft_data["memoryMethod"],
            keywords=draft_data["keywords"],
            imagery=draft_data["imagery"],
            recap=draft_data["recap"],
            contrastMatrix=draft_data.get("contrastMatrix"),
        )
        session.draft = draft
        if strategy_data.get("strategyIr"):
            session.strategyIr = MemoryStrategyIR.model_validate(strategy_data["strategyIr"])
        session.state = "draft_generated"
        session.conversationMode = "memory_flow"
        reply_text = _draft_to_text(draft, "memory_draft")
        session.history.append(session_manager.make_message("assistant", "memory_draft", reply_text))
        session_manager.save(session)
        _log_route(
            session=session,
            mode_before=mode_before,
            mode_after=session.conversationMode,
            route_decision="new_task",
            generation_source=str(meta.get("generationSource", "unknown")),
            degrade_reason=str(meta.get("degradeReason", "none")),
        )
        return MemoryChatResponse(
            sessionId=session.sessionId,
            replyType="memory_draft",
            replyText=reply_text,
            mode=session.conversationMode,
            triggeredBy="qa_pair",
            degraded=bool(meta.get("degraded", False)),
            degradeReason=str(meta.get("degradeReason", "none")),
            draft=draft,
            strategyIr=session.strategyIr,
        )

    # 3) memory_intent
    if _is_memory_intent_message(message):
        if not session.task or not session.draft:
            reply_text = _assistant_question_text()
        else:
            reply_text = "你当前已经在记忆模式了。可以继续聊天，或直接说“请把第2条改成…”来修订草稿。"
        session.history.append(session_manager.make_message("assistant", "memory_question", reply_text))
        session_manager.save(session)
        _log_route(
            session=session,
            mode_before=mode_before,
            mode_after=session.conversationMode,
            route_decision="memory_intent",
            generation_source="none",
            degrade_reason="none",
        )
        return MemoryChatResponse(
            sessionId=session.sessionId,
            replyType="chat",
            replyText=reply_text,
            mode=session.conversationMode,
            triggeredBy="memory_intent",
            degraded=False,
            degradeReason="none",
            strategyIr=session.strategyIr,
            draft=session.draft,
        )

    # 4) revision
    if _is_revision_message(message):
        if not session.task or not session.draft:
            reply_text = _assistant_question_text()
            session.history.append(session_manager.make_message("assistant", "memory_question", reply_text))
            session_manager.save(session)
            _log_route(
                session=session,
                mode_before=mode_before,
                mode_after=session.conversationMode,
                route_decision="revision_without_task",
                generation_source="none",
                degrade_reason="none",
            )
            return MemoryChatResponse(
                sessionId=session.sessionId,
                replyType="chat",
                replyText=reply_text,
                mode=session.conversationMode,
                triggeredBy="manual_revision",
                degraded=False,
                degradeReason="none",
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
        meta = revised_payload.get("meta", {}) or {}
        draft = MemoryDraft(
            contentType=revised.get("contentType", session.draft.contentType),
            hookSystem=revised.get("hookSystem", session.draft.hookSystem),
            memoryMethod=revised.get("memoryMethod", session.draft.memoryMethod),
            keywords=revised["keywords"],
            imagery=revised["imagery"],
            recap=revised["recap"],
            contrastMatrix=revised.get("contrastMatrix"),
        )
        session.draft = draft
        if revised_payload.get("strategyIr"):
            session.strategyIr = MemoryStrategyIR.model_validate(revised_payload["strategyIr"])
        session.state = "revising"
        session.conversationMode = "memory_flow"
        reply_text = _draft_to_text(draft, "memory_revision")
        session.history.append(session_manager.make_message("assistant", "memory_revision", reply_text))
        session_manager.save(session)
        _log_route(
            session=session,
            mode_before=mode_before,
            mode_after=session.conversationMode,
            route_decision="manual_revision",
            generation_source=str(meta.get("generationSource", "patch_flow")),
            degrade_reason=str(meta.get("degradeReason", "none")),
        )
        return MemoryChatResponse(
            sessionId=session.sessionId,
            replyType="memory_revision",
            replyText=reply_text,
            mode=session.conversationMode,
            triggeredBy="manual_revision",
            degraded=bool(meta.get("degraded", False)),
            degradeReason=str(meta.get("degradeReason", "none")),
            draft=draft,
            strategyIr=session.strategyIr,
        )

    # 5) general_chat
    memory_context = ""
    if session.task and session.draft:
        memory_context = (
            f"当前记忆题目：{session.task.question}\n"
            f"当前方法：{session.draft.memoryMethod}\n"
            f"当前关键词：{' / '.join(session.draft.keywords)}\n"
            "如果用户只是聊天，请正常回答；若用户请求改动草稿，提醒其使用“请把第X条改成...”格式。"
        )
    reply_text, degraded, degrade_reason = _general_chat_reply(session, memory_context=memory_context)
    session.conversationMode = "general_chat"
    session.history.append(session_manager.make_message("assistant", "memory_question", reply_text))
    session_manager.save(session)
    _log_route(
        session=session,
        mode_before=mode_before,
        mode_after=session.conversationMode,
        route_decision="general_chat",
        generation_source="llm_chat",
        degrade_reason=degrade_reason,
    )
    return MemoryChatResponse(
        sessionId=session.sessionId,
        replyType="chat",
        replyText=reply_text,
        mode=session.conversationMode,
        triggeredBy=None,
        degraded=degraded,
        degradeReason=degrade_reason,
        strategyIr=session.strategyIr,
        draft=session.draft,
    )
