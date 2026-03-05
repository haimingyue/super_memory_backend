"""
AI 功能路由 - LangChain + 通义千问
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

from app.services.llm_service import llm_service
from app.routers.memory import get_memory_store

router = APIRouter(prefix="/api/ai", tags=["AI 功能"])


class AnalyzeRequest(BaseModel):
    """分析请求"""
    title: str
    content: str


class QuestionRequest(BaseModel):
    """问答请求"""
    question: str
    memory_id: Optional[int] = None


class SearchRequest(BaseModel):
    """搜索请求"""
    query: str


class ExpandRequest(BaseModel):
    """扩展请求"""
    title: str
    brief: str


class ChatMessage(BaseModel):
    """对话消息"""
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str


class ChatRequest(BaseModel):
    """对话请求"""
    messages: list[ChatMessage] = Field(default_factory=list)


@router.post("/analyze")
def analyze_memory(request: AnalyzeRequest):
    """
    智能分析记忆内容
    返回：分类、标签、重要性评分、关键词、摘要
    """
    result = llm_service.analyze_memory(request.title, request.content)
    return result


@router.post("/summary")
def generate_summary(content: str, max_length: int = 100):
    """生成记忆摘要"""
    summary = llm_service.generate_summary(content, max_length)
    return {"summary": summary}


@router.post("/answer")
def answer_question(request: QuestionRequest):
    """
    基于记忆内容回答问题
    """
    context = ""
    if request.memory_id:
        memories = get_memory_store()
        if request.memory_id in memories:
            memory = memories[request.memory_id]
            context = f"标题：{memory.title}\n内容：{memory.content}"
        else:
            raise HTTPException(status_code=404, detail="记忆不存在")

    answer = llm_service.answer_question(request.question, context)
    return {"answer": answer}


@router.post("/search")
def semantic_search(request: SearchRequest):
    """
    语义搜索记忆
    基于查询语义查找最相关的记忆
    """
    memories = list(get_memory_store().values())
    if not memories:
        return {"results": []}

    memories_data = [m.model_dump() for m in memories]
    results = llm_service.semantic_search(request.query, memories_data)
    return {"results": results}


@router.post("/expand")
def expand_memory(request: ExpandRequest):
    """
    扩展记忆内容
    根据标题和简要描述生成更丰富的内容
    """
    expanded = llm_service.expand_memory(request.title, request.brief)
    return {"content": expanded}


@router.get("/chat")
def chat_with_ai(prompt: str):
    """
    与 AI 助手聊天
    通用对话接口
    """
    answer = llm_service.answer_question(prompt)
    return {"reply": answer}


@router.post("/chat")
def chat_with_ai_v2(request: ChatRequest):
    """
    与 AI 助手多轮聊天
    """
    answer = llm_service.chat([m.model_dump() for m in request.messages])
    return {"reply": answer}
