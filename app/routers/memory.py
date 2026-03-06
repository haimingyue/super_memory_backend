"""
记忆管理路由
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional

from app.schemas.memory_chat import MemoryChatRequest
from app.schemas.memory_engine import MemorySolveRequest
from app.services.memory_conversation_handler import handle_memory_conversation
from app.services.memory_engine_service import run_memory_engine
from app.services.memory_session_manager import session_manager

router = APIRouter(prefix="/api/memory", tags=["记忆管理"])


# 数据模型
class MemoryItem(BaseModel):
    """记忆项"""
    id: Optional[int] = None
    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1)
    category: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    importance: int = Field(default=5, ge=1, le=10)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: Optional[datetime] = None


class MemoryCreate(BaseModel):
    """创建记忆"""
    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1)
    category: Optional[str] = None


class MemoryUpdate(BaseModel):
    """更新记忆"""
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    content: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[list[str]] = None
    importance: Optional[int] = Field(None, ge=1, le=10)


# 临时存储（实际项目中应该使用数据库）
_memories: dict[int, MemoryItem] = {}
_next_id: int = 1


def get_memory_store() -> dict[int, MemoryItem]:
    """获取记忆存储（用于其他模块访问）"""
    return _memories


@router.post("/solve")
async def solve_memory(request: MemorySolveRequest):
    """记忆引擎：输入题目+答案，输出结构化记忆卡片数据"""
    try:
        data = run_memory_engine(request.rawText)
        return {"ok": True, "data": data}
    except ValueError as exc:
        return JSONResponse(status_code=400, content={"ok": False, "message": str(exc)})
    except Exception:
        return JSONResponse(status_code=500, content={"ok": False, "message": "记忆引擎处理失败"})


@router.post("/chat")
async def memory_chat(request: MemoryChatRequest):
    """记忆共创对话接口：支持会话、草稿修订、最终卡片生成"""
    try:
        session = session_manager.get_or_create(request.sessionId)
        response = handle_memory_conversation(session, request.message)
        return response.model_dump()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="记忆共创对话失败") from exc


@router.get("")
async def get_memories(category: Optional[str] = None, tag: Optional[str] = None):
    """获取记忆列表"""
    results = list(_memories.values())

    if category:
        results = [m for m in results if m.category == category]
    if tag:
        results = [m for m in results if tag in m.tags]

    return [m.model_dump() for m in results]


@router.get("/{memory_id}")
async def get_memory(memory_id: int):
    """获取单个记忆"""
    if memory_id not in _memories:
        raise HTTPException(status_code=404, detail="记忆不存在")
    return _memories[memory_id]


@router.post("")
async def create_memory(memory: MemoryCreate):
    """创建新记忆"""
    global _next_id

    memory_item = MemoryItem(
        id=_next_id,
        title=memory.title,
        content=memory.content,
        category=memory.category,
    )
    _memories[_next_id] = memory_item
    _next_id += 1

    return memory_item


@router.put("/{memory_id}")
async def update_memory(memory_id: int, memory: MemoryUpdate):
    """更新记忆"""
    if memory_id not in _memories:
        raise HTTPException(status_code=404, detail="记忆不存在")

    existing = _memories[memory_id]
    update_data = memory.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(existing, field, value)

    existing.updated_at = datetime.now()
    return existing


@router.delete("/{memory_id}")
async def delete_memory(memory_id: int):
    """删除记忆"""
    if memory_id not in _memories:
        raise HTTPException(status_code=404, detail="记忆不存在")

    del _memories[memory_id]
    return {"message": "记忆已删除"}


@router.get("/stats/summary")
async def get_memory_stats():
    """获取记忆统计信息"""
    total = len(_memories)
    categories = {}
    importance_sum = 0

    for m in _memories.values():
        cat = m.category or "未分类"
        categories[cat] = categories.get(cat, 0) + 1
        importance_sum += m.importance

    return {
        "total": total,
        "categories": categories,
        "avg_importance": round(importance_sum / total, 2) if total > 0 else 0,
    }
