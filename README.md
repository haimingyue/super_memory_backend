# Super Memory Backend - FastAPI + LangChain + 通义千问

基于 FastAPI 框架，集成 LangChain 和阿里云通义千问大模型的记忆管理 API 服务。

## 功能特性

### 基础功能
- 记忆内容的增删改查（CRUD）
- 按分类和标签筛选
- 记忆统计信息

### AI 功能（LangChain + 通义千问）
- **智能分析**：自动分析记忆内容，生成分类、标签、重要性评分和关键词
- **摘要生成**：自动生成记忆内容的简洁摘要
- **AI 问答**：基于记忆内容的智能问答
- **语义搜索**：理解查询语义，找到最相关的记忆
- **内容扩展**：根据简要描述扩展成丰富的记忆内容

## 快速开始

### 1. 环境要求

- Python 3.9+
- 阿里云账号（获取通义千问 API Key）

### 2. 创建虚拟环境

```bash
cd super_memory/backend
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 配置环境变量

```bash
# 复制环境配置示例
cp .env.example .env

# 编辑 .env 文件，填入你的通义千问 API Key
# DASHSCOPE_API_KEY=your_actual_api_key
```

**获取 API Key：**
1. 访问 [阿里云 DashScope 控制台](https://dashscope.console.aliyun.com/apiKey)
2. 登录/注册阿里云账号
3. 创建或查看你的 API Key

### 5. 启动服务

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

服务启动后访问：
- **API 文档**：http://localhost:8000/docs
- **替代文档**：http://localhost:8000/redoc
- **健康检查**：http://localhost:8000/health

## API 端点

### 记忆管理

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/api/memory` | 获取记忆列表 |
| GET | `/api/memory/{id}` | 获取单个记忆 |
| POST | `/api/memory` | 创建新记忆 |
| PUT | `/api/memory/{id}` | 更新记忆 |
| DELETE | `/api/memory/{id}` | 删除记忆 |
| GET | `/api/memory/stats/summary` | 获取统计信息 |

### AI 功能

| 方法 | 路径 | 描述 |
|------|------|------|
| POST | `/api/ai/analyze` | 智能分析记忆 |
| POST | `/api/ai/summary` | 生成摘要 |
| POST | `/api/ai/answer` | AI 问答 |
| POST | `/api/ai/search` | 语义搜索 |
| POST | `/api/ai/expand` | 内容扩展 |
| GET | `/api/ai/chat` | AI 聊天 |

## 使用示例

### 创建记忆

```bash
curl -X POST "http://localhost:8000/api/memory" \
  -H "Content-Type: application/json" \
  -d '{"title": "学习 FastAPI", "content": "今天学习了 FastAPI 框架，感觉很好用"}'
```

### 智能分析记忆

```bash
curl -X POST "http://localhost:8000/api/ai/analyze" \
  -H "Content-Type: application/json" \
  -d '{"title": "学习 FastAPI", "content": "今天学习了 FastAPI 框架，性能很好，文档清晰"}'
```

### 语义搜索

```bash
curl -X POST "http://localhost:8000/api/ai/search" \
  -H "Content-Type: application/json" \
  -d '{"query": "编程学习"}'
```

## 项目结构

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py              # 应用入口
│   ├── core/
│   │   ├── __init__.py
│   │   └── config.py        # 配置管理
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── memory.py        # 记忆路由
│   │   └── ai.py            # AI 路由
│   ├── services/
│   │   ├── __init__.py
│   │   └── llm_service.py   # LLM 服务
│   ├── models/              # 数据库模型
│   └── schemas/             # Pydantic 模式
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

## 技术栈

- **FastAPI** - 高性能现代 Web 框架
- **LangChain** - LLM 应用开发框架
- **DashScope** - 阿里云通义千问 SDK
- **Pydantic** - 数据验证
- **Uvicorn** - ASGI 服务器

## 注意事项

1. **API Key 安全**：不要将 `.env` 文件提交到版本控制
2. **费用**：通义千问 API 调用可能产生费用，请查看阿里云定价
3. **速率限制**：注意 API 调用频率限制

## 开发计划

- [ ] 添加数据库支持（PostgreSQL/MySQL）
- [ ] 添加用户认证
- [ ] 添加记忆向量存储，支持更精准的语义搜索
- [ ] 添加批量导入/导出功能
