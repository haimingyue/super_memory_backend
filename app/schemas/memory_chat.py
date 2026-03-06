"""Schemas for memory co-creation chat."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class MemoryChatRequest(BaseModel):
    sessionId: Optional[str] = Field(default=None, description="会话 ID")
    message: str = Field(..., min_length=1, description="用户消息")


class SessionTask(BaseModel):
    question: str
    answerLines: list[str]


class MemoryDraft(BaseModel):
    contentType: str
    hookSystem: str
    memoryMethod: str
    keywords: list[str]
    imagery: list[str]
    recap: str
    contrastMatrix: Optional[dict] = None
    memoryPlan: Optional[dict] = None


class MemoryCardStrategySummary(BaseModel):
    primaryMethod: str
    secondaryMethods: list[str] = Field(default_factory=list)
    hookSystem: str
    qualityScore: Optional[int] = None
    summaryText: str


class MemoryCardFormat(BaseModel):
    standard: dict
    ankiText: str
    structured: dict


class MemoryCard(BaseModel):
    id: str
    front: str
    back: str
    question: str
    answer: str
    keywords: list[str]
    imagery: list[str]
    recap: str
    strategySummary: MemoryCardStrategySummary
    cardFormat: MemoryCardFormat


class MemoryStrategyTask(BaseModel):
    question: str
    rawAnswerLines: list[str]


class MemoryStrategyAnalysis(BaseModel):
    contentType: str
    memoryGoal: str
    difficulty: str
    reason: str


class MemoryStrategyHookPolicy(BaseModel):
    useHooks: bool
    hookSystem: str
    hookPurpose: str


class MemoryStrategyPlan(BaseModel):
    primaryMethod: str
    secondaryMethods: list[str]
    hookPolicy: MemoryStrategyHookPolicy


class MemoryStrategyAnchor(BaseModel):
    index: int
    source: str
    visual: str
    hook: Optional[str] = None
    functionHint: Optional[str] = None
    abstractLevel: Optional[str] = None


class MemoryStrategyOutputPolicy(BaseModel):
    keywordCount: int
    imagerySentenceCount: int
    recapStyle: str
    tone: str
    allowAbstractWords: bool


class MemoryDraftQuality(BaseModel):
    qualityScore: int
    issues: list[str]
    suggestions: list[str]
    autoFixApplied: list[str] = Field(default_factory=list)


class MemoryStrategyIR(BaseModel):
    version: str
    task: MemoryStrategyTask
    analysis: MemoryStrategyAnalysis
    strategy: MemoryStrategyPlan
    anchors: list[MemoryStrategyAnchor]
    outputPolicy: MemoryStrategyOutputPolicy
    quality: Optional[MemoryDraftQuality] = None


class SessionMessage(BaseModel):
    role: Literal["user", "assistant"]
    type: Literal["text", "memory_draft", "memory_question", "memory_revision", "memory_card"]
    content: str
    timestamp: int


class MemorySession(BaseModel):
    sessionId: str
    state: Literal["collecting_material", "draft_generated", "revising", "finalized"] = "collecting_material"
    conversationMode: Literal["general_chat", "memory_flow"] = "general_chat"
    task: Optional[SessionTask] = None
    draft: Optional[MemoryDraft] = None
    finalCard: Optional[MemoryCard] = None
    strategyIr: Optional[MemoryStrategyIR] = None
    history: list[SessionMessage] = Field(default_factory=list)


class MemoryChatResponse(BaseModel):
    sessionId: str
    replyType: Literal["chat", "memory_draft", "memory_revision", "memory_card"]
    replyText: str
    mode: Literal["general_chat", "memory_flow"]
    triggeredBy: Optional[Literal["qa_pair", "memory_intent", "manual_revision", "finalize"]] = None
    degraded: bool = False
    degradeReason: Optional[Literal["llm_timeout", "invalid_llm_payload", "fallback_rule_engine", "none"]] = "none"
    draft: Optional[MemoryDraft] = None
    finalCard: Optional[MemoryCard] = None
    strategyIr: Optional[MemoryStrategyIR] = None
