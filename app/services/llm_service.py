"""
LangChain + 通义千问 LLM 服务
"""
import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from typing import Optional

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

try:
    # langchain-community==0.0.10
    from langchain_community.chat_models import ChatTongyi as ChatDashScope
except ImportError:
    # 兼容其他旧版本命名
    try:
        from langchain_community.chat_models.dashscope import ChatDashScope
    except ImportError:
        from langchain_community.chat_models import QwenChat as ChatDashScope

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class LLMService:
    """LLM 服务类 - 封装通义千问大模型能力"""

    def __init__(self):
        self.settings = get_settings()
        self._llm: Optional[ChatDashScope] = None
        self._executor = ThreadPoolExecutor(max_workers=4)
        self._timeout_seconds = 15

    @property
    def llm(self) -> ChatDashScope:
        """懒加载 LLM 实例"""
        if self._llm is None:
            if not self.settings.DASHSCOPE_API_KEY:
                raise ValueError("DASHSCOPE_API_KEY 未配置")

            self._llm = ChatDashScope(
                model=self.settings.DASHSCOPE_MODEL,
                dashscope_api_key=self.settings.DASHSCOPE_API_KEY,
            )
        return self._llm

    def analyze_memory(self, title: str, content: str) -> dict:
        """
        智能分析记忆内容
        返回：分类、标签、重要性评分、关键词
        """
        prompt = f"""请分析以下记忆内容，并以 JSON 格式返回分析结果：

记忆标题：{title}
记忆内容：{content}

请返回以下格式的 JSON：
{{
    "category": "分类（如：学习、工作、生活、情感等）",
    "tags": ["标签 1", "标签 2", "标签 3"],
    "importance": 重要性评分（1-10 的整数）,
    "keywords": ["关键词 1", "关键词 2", "关键词 3"],
    "summary": "一句话摘要（50 字以内）"
}}

只返回 JSON，不要其他内容。"""

        try:
            response = self._invoke_with_timeout([HumanMessage(content=prompt)])
            return self._parse_json_response(response.content)
        except Exception as e:
            logger.error(f"记忆分析失败：{e}")
            return {
                "category": "未分类",
                "tags": [],
                "importance": 5,
                "keywords": [],
                "summary": content[:50] + "..." if len(content) > 50 else content,
            }

    def generate_summary(self, content: str, max_length: int = 100) -> str:
        """生成记忆摘要"""
        prompt = f"""请将以下内容概括为{max_length}字以内的摘要：

{content}

只返回摘要内容，不要其他说明。"""

        try:
            response = self._invoke_with_timeout([HumanMessage(content=prompt)])
            return response.content.strip()
        except Exception as e:
            logger.error(f"摘要生成失败：{e}")
            return content[:max_length] + "..." if len(content) > max_length else content

    def answer_question(self, question: str, context: str = "") -> str:
        """
        基于记忆内容回答问题
        """
        system_prompt = """你是一个智能记忆助手，基于用户提供的记忆内容来回答问题。
如果问题与记忆内容无关，请礼貌地告知用户。"""

        if context:
            user_prompt = f"""记忆内容：
{context}

问题：{question}

请基于上述记忆内容回答问题。"""
        else:
            user_prompt = f"问题：{question}\n\n请回答："

        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt),
            ]
            response = self._invoke_with_timeout(messages)
            return response.content.strip()
        except Exception as e:
            logger.error(f"问答失败：{e}")
            return "抱歉，回答问题时出现错误，请稍后再试。"

    def chat(self, conversation: list[dict]) -> str:
        """
        多轮对话
        conversation 示例：
        [{"role":"user","content":"..."}, {"role":"assistant","content":"..."}]
        """
        system_prompt = (
            "你是一个专业的记忆训练助手。"
            "请根据用户问题给出清晰、可执行、简洁的建议。"
        )
        messages = [SystemMessage(content=system_prompt)]

        for item in conversation:
            role = item.get("role")
            content = (item.get("content") or "").strip()
            if not content:
                continue
            if role == "user":
                messages.append(HumanMessage(content=content))
            elif role == "assistant":
                messages.append(AIMessage(content=content))

        if len(messages) == 1:
            return "请先告诉我你想记忆什么，我会给你具体方案。"

        try:
            response = self._invoke_with_timeout(messages)
            return response.content.strip()
        except Exception as e:
            logger.error(f"多轮对话失败：{e}")
            return "抱歉，我暂时无法回复，请稍后重试。"

    def semantic_search(self, query: str, memories: list[dict]) -> list[dict]:
        """
        语义搜索记忆
        返回与查询最相关的记忆列表
        """
        memories_text = "\n\n".join(
            [f"标题：{m.get('title', '')}\n内容：{m.get('content', '')}" for m in memories]
        )

        prompt = f"""我有以下记忆：

{memories_text}

请找出与"{query}"最相关的记忆，返回它们的索引（从 0 开始），格式为 JSON 数组：
[0, 2, 3]

只返回索引数组，不要其他内容。如果没有相关记忆，返回空数组。"""

        try:
            response = self._invoke_with_timeout([HumanMessage(content=prompt)])
            indices = self._parse_json_response(response.content)
            if isinstance(indices, list):
                return [memories[i] for i in indices if 0 <= i < len(memories)]
            return []
        except Exception as e:
            logger.error(f"语义搜索失败：{e}")
            # 降级：简单关键词匹配
            query_lower = query.lower()
            return [
                m for m in memories
                if query_lower in m.get("title", "").lower() or query_lower in m.get("content", "").lower()
            ]

    def expand_memory(self, title: str, brief: str) -> str:
        """
        扩展记忆内容
        根据标题和简要描述，生成更丰富的内容
        """
        prompt = f"""请根据以下标题和简要描述，扩展成一篇更丰富的记忆内容（200-500 字）：

标题：{title}
简要描述：{brief}

要求：
1. 保持内容的真实感和个人化
2. 添加细节和情感描述
3. 结构清晰，易于阅读

只返回扩展后的内容，不要其他说明。"""

        try:
            response = self._invoke_with_timeout([HumanMessage(content=prompt)])
            return response.content.strip()
        except Exception as e:
            logger.error(f"内容扩展失败：{e}")
            return brief

    def generate_memory_blocks(
        self,
        question: str,
        answer_text: str,
        memory_type: str,
        type_label: str,
        method: str,
        method_label: str,
    ) -> dict:
        """
        使用大模型生成 Memory Engine 的结构化 blocks。
        返回格式：
        {"keywords": [...], "imagery": [...], "recap": "..."}
        """
        prompt = f"""你是“记忆引擎”文案专家。请根据输入生成严格 JSON。

输入信息：
- 题目：{question}
- 答案：{answer_text}
- 题型：{memory_type}（{type_label}）
- 记忆方法：{method}（{method_label}）

输出 JSON 要求（只输出 JSON，不要 markdown）：
{{
  "keywords": ["词1","词2","词3"],
  "imagery": ["句子1","句子2","句子3","句子4"],
  "recap": "..."
}}

硬性约束：
1) keywords 数量 3~9，尽量具体、可画面化，避免抽象词。
2) imagery 数量 4~9，荒谬、夸张、带动作，尽量一条对应一个要点。
3) imagery 中必须包含完全一致的一句：现在闭上眼睛想象 5 秒
4) recap 规则：
   - sequence_list/general/concept_definition/number_or_code：A → B → C 形式
   - numbered_list：1=...;2=...;3=... 形式
   - compare_contrast：A(锚点)=... | B(锚点)=... + 关键差异短句
"""

        response = self._invoke_with_timeout([HumanMessage(content=prompt)])
        parsed = self._parse_json_response(response.content)
        if not isinstance(parsed, dict):
            raise ValueError("LLM 返回格式错误：非 JSON 对象")

        keywords = parsed.get("keywords", [])
        imagery = parsed.get("imagery", [])
        recap = str(parsed.get("recap", "")).strip()

        if not isinstance(keywords, list):
            keywords = []
        if not isinstance(imagery, list):
            imagery = []

        keywords = [str(x).strip() for x in keywords if str(x).strip()][:9]
        imagery = [str(x).strip() for x in imagery if str(x).strip()][:9]

        if len(keywords) < 3 or len(imagery) < 4 or not recap:
            raise ValueError("LLM 返回字段不完整")

        if "现在闭上眼睛想象 5 秒" not in imagery:
            imagery = imagery[:8] + ["现在闭上眼睛想象 5 秒"]

        return {
            "keywords": keywords[:9],
            "imagery": imagery[:9],
            "recap": recap,
        }

    def revise_draft(
        self,
        question: str,
        answer_text: str,
        draft: dict,
        user_feedback: str,
        history: list[dict] | None = None,
    ) -> dict:
        """
        根据用户反馈修订记忆草稿。
        draft 结构：
        {"type","typeLabel","method","methodLabel","keywords","imagery","recap"}
        """
        history_text = ""
        if history:
            lines = []
            for item in history[-8:]:
                role = item.get("role", "")
                content = (item.get("content") or "").strip()
                if content:
                    lines.append(f"{role}: {content}")
            history_text = "\n".join(lines)

        prompt = f"""你是记忆共创助手。请根据用户反馈修订草稿并输出严格 JSON。

题目：
{question}

答案：
{answer_text}

当前草稿：
{json.dumps(draft, ensure_ascii=False)}

对话历史（可选）：
{history_text or "无"}

用户本轮反馈：
{user_feedback}

只输出 JSON：
{{
  "keywords": ["..."],
  "imagery": ["..."],
  "recap": "..."
}}

约束：
1) keywords 3~9 个。
2) imagery 4~9 句，必须包含：现在闭上眼睛想象 5 秒
3) recap 与当前草稿题型兼容（顺序箭头 / 编号映射 / 对比格式）。
"""
        response = self._invoke_with_timeout([HumanMessage(content=prompt)])
        parsed = self._parse_json_response(response.content)
        if not isinstance(parsed, dict):
            raise ValueError("LLM 修订返回格式错误")

        keywords = parsed.get("keywords", draft.get("keywords", []))
        imagery = parsed.get("imagery", draft.get("imagery", []))
        recap = str(parsed.get("recap", draft.get("recap", ""))).strip()

        if not isinstance(keywords, list):
            keywords = draft.get("keywords", [])
        if not isinstance(imagery, list):
            imagery = draft.get("imagery", [])

        keywords = [str(x).strip() for x in keywords if str(x).strip()][:9]
        imagery = [str(x).strip() for x in imagery if str(x).strip()][:9]
        if len(keywords) < 3:
            keywords = (draft.get("keywords") or [])[:9]
        if len(imagery) < 4:
            imagery = (draft.get("imagery") or [])[:9]
        if "现在闭上眼睛想象 5 秒" not in imagery:
            imagery = imagery[:8] + ["现在闭上眼睛想象 5 秒"]
        if not recap:
            recap = str(draft.get("recap", ""))

        return {
            "keywords": keywords[:9],
            "imagery": imagery[:9],
            "recap": recap,
        }

    def _invoke_with_timeout(self, messages):
        future = self._executor.submit(self.llm.invoke, messages)
        try:
            return future.result(timeout=self._timeout_seconds)
        except FuturesTimeoutError:
            future.cancel()
            raise TimeoutError(f"LLM 调用超时（>{self._timeout_seconds}s）")

    @staticmethod
    def _parse_json_response(content: str) -> dict | list:
        """解析 JSON 响应"""
        # 清理可能的 markdown 标记
        content = content.strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        cleaned = content.strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            # 兜底：提取首个 JSON 对象/数组
            match = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", cleaned)
            if not match:
                raise
            return json.loads(match.group(1))


# 全局服务实例
llm_service = LLMService()
