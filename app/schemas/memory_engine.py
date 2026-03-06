"""Schemas for Memory Engine API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class MemorySolveRequest(BaseModel):
    rawText: str = Field(..., min_length=1, description="用户输入全文")


class ParsedResult(BaseModel):
    question: str
    answerText: str
    answerLines: list[str]
    raw: str


class MemoryBlocksMeta(BaseModel):
    typeLabel: str
    methodLabel: str


class MemoryBlocks(BaseModel):
    meta: MemoryBlocksMeta
    keywords: list[str]
    imagery: list[str]
    recap: str


class MemorySolveData(BaseModel):
    parsed: ParsedResult
    type: str
    typeLabel: str
    method: str
    methodLabel: str
    resultBlocks: MemoryBlocks
    resultText: str


class MemorySolveSuccessResponse(BaseModel):
    ok: bool = True
    data: MemorySolveData


class MemorySolveErrorResponse(BaseModel):
    ok: bool = False
    message: str

