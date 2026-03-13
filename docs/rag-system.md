# RAG System (Retrieval-Augmented Generation)

## 概述

RAG 系统为 AI Agent 提供"经验记忆"：将历史攻防 session 中提取的知识向量化存储，在新 session 启动时自动检索相关经验并注入 system prompt。

**核心原则：零额外 token 开销的知识注入**。RAG 上下文在 agent loop 启动前一次性拼接到 system prompt，不增加对话轮次。

---

## 架构

```
┌──────────────────────────────────────────────────────────┐
│                    写入阶段（Session 结束后）               │
│                                                          │
│  Session Turns ──► build_session_digest() ──► AI Call 1  │
│                      (压缩为摘要文本)      (结构化 JSON)   │
│                                               │          │
│                                          AI Call 2       │
│                                        (学习报告 MD)      │
│                                               │          │
│                     KnowledgeEntry ◄──────────┘          │
│                          │                               │
│                  build_embedding_text()                   │
│                          │                               │
│                  generate_embedding()                     │
│                     (zhipuai API)                         │
│                          │                               │
│                    pgvector 存储                          │
│                  vector(2048) 列                          │
└──────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────┐
│                    读取阶段（新 Session 启动时）            │
│                                                          │
│  用户消息 ──► generate_embedding(query)                   │
│                          │                               │
│              pgvector cosine similarity                   │
│              WHERE user_id = :uid                        │
│              AND similarity >= 0.6                        │
│                          │                               │
│              format_rag_context()                         │
│                          │                               │
│              system_prompt += rag_context                 │
│                          │                               │
│              Agent Loop 正常执行（带历史经验）              │
└──────────────────────────────────────────────────────────┘
```

---

## 配置

环境变量（`backend/.env`）：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `RAG_ENABLED` | `false` | 总开关 |
| `RAG_EMBEDDING_PROVIDER` | `""` | `openai` / `zhipuai` / `custom` |
| `RAG_EMBEDDING_API_KEY` | `""` | Embedding API 密钥 |
| `RAG_EMBEDDING_MODEL` | `text-embedding-3-small` | 模型名称 |
| `RAG_EMBEDDING_DIM` | `1536` | 向量维度（需与模型匹配） |
| `RAG_EMBEDDING_URL` | `""` | 自定义 OpenAI 兼容端点 |
| `RAG_TOP_K` | `5` | 检索返回条数上限 |
| `RAG_SIMILARITY_THRESHOLD` | `0.6` | 相似度阈值（低于此值丢弃） |
| `AUTO_EXTRACT_KNOWLEDGE` | `false` | Session 结束后自动提取知识 |

### 已支持的 Embedding 提供商

| Provider | URL | 常用模型 | 维度 |
|----------|-----|----------|------|
| OpenAI | `https://api.openai.com/v1/embeddings` | `text-embedding-3-small` | 1536 |
| ZhipuAI | `https://open.bigmodel.cn/api/paas/v4/embeddings` | `embedding-3` | 2048 |
| 自定义 | 任意 OpenAI 兼容端点 | 取决于服务 | 取决于服务 |

设置自定义端点时，只需设置 `RAG_EMBEDDING_URL`，provider 可以留空。

---

## 数据模型

### knowledge_entries 表

```sql
CREATE TABLE knowledge_entries (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER REFERENCES users(id),
    session_id      INTEGER REFERENCES agent_sessions(id) ON DELETE SET NULL,

    -- 结构化提取字段
    scenario        TEXT,               -- "OWASP Juice Shop XSS 攻击"
    target_type     VARCHAR(50),        -- web|network|host|api|cloud|other
    vulnerability_type VARCHAR(50),     -- sqli|xss|rce|ssrf|lfi|rfi|misconfig|privesc|other
    tools_used      JSONB,              -- ["nmap", "sqlmap"]
    attack_chain    TEXT,               -- 攻击路径描述
    outcome         VARCHAR(20),        -- success|partial|failed
    key_findings    TEXT,               -- 关键发现
    tags            JSONB,              -- ["juice-shop", "dom-xss"]
    summary         TEXT,               -- 一句话总结

    -- AI 生成的报告
    learning_report TEXT,               -- Markdown 格式学习报告

    -- RAG 向量
    embedding       vector(2048),       -- pgvector 向量列

    extraction_status VARCHAR(20),      -- pending|processing|success|failed
    created_at      TIMESTAMP DEFAULT NOW()
);
```

### agent_sessions / session_turns 表

```sql
-- Session 元数据
CREATE TABLE agent_sessions (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER REFERENCES users(id),
    title           VARCHAR(300),
    agent_mode      VARCHAR(20),        -- semi_auto|full_auto|terminal
    security_mode   VARCHAR(20),        -- offense|defense
    lang            VARCHAR(10),
    total_turns     INTEGER DEFAULT 0,
    status          VARCHAR(20),        -- active|completed|failed
    summary         TEXT,
    created_at      TIMESTAMP DEFAULT NOW(),
    finished_at     TIMESTAMP
);

-- 每轮对话记录
CREATE TABLE session_turns (
    id              SERIAL PRIMARY KEY,
    session_id      INTEGER REFERENCES agent_sessions(id) ON DELETE CASCADE,
    turn_number     INTEGER,
    role            VARCHAR(20),        -- user|assistant|action_result
    content         TEXT,               -- AI 推理文本
    action          JSONB,              -- 解析后的 action 结构
    action_result   JSONB,              -- 执行结果
    action_status   VARCHAR(20),        -- done|error|blocked
    created_at      TIMESTAMP DEFAULT NOW()
);
```

---

## API 端点

### Session 管理

#### `GET /api/v1/sessions`

列出当前用户的所有 Agent session。

**Response:**
```json
[
  {
    "id": 41,
    "title": "OWASP Juice Shop XSS",
    "agent_mode": "terminal",
    "security_mode": "offense",
    "total_turns": 28,
    "status": "completed",
    "created_at": "2026-03-12T19:08:18"
  }
]
```

#### `GET /api/v1/sessions/{session_id}`

获取 session 详情（含所有 turn）。

**Response:**
```json
{
  "id": 41,
  "title": "...",
  "turns": [
    {
      "turn_number": 1,
      "role": "assistant",
      "content": "我将分析这个靶场...",
      "action": {"type": "shell", "command": "curl ..."},
      "action_result": {"stdout": "...", "exit_code": 0},
      "action_status": "done"
    }
  ]
}
```

#### `DELETE /api/v1/sessions/{session_id}`

删除 session 及其所有 turn。

---

### 知识提取

#### `POST /api/v1/sessions/{session_id}/extract`

触发知识提取（后台执行，立即返回）。

**Response:**
```json
{"status": "processing", "session_id": 41}
```

**后台流程：**

1. 压缩 session turns 为摘要文本（`build_session_digest`）
2. AI 调用 1：提取结构化 JSON（scenario, target_type, tools, findings...）
3. AI 调用 2：生成 Markdown 学习报告
4. 保存 `KnowledgeEntry`，`extraction_status = "success"`
5. 如果 `RAG_ENABLED`：调用 `embed_knowledge_entry()` 生成向量

---

### 知识库 CRUD

#### `GET /api/v1/knowledge`

列出当前用户的所有知识条目。

**Response:**
```json
[
  {
    "id": 1,
    "scenario": "Juice Shop Video XSS via subtitle upload",
    "target_type": "web",
    "vulnerability_type": "xss",
    "tools_used": ["curl"],
    "outcome": "success",
    "key_findings": "通过 /api/Complaints 上传恶意 VTT 字幕文件实现 DOM XSS",
    "tags": ["juice-shop", "dom-xss", "file-upload"],
    "extraction_status": "success"
  }
]
```

#### `DELETE /api/v1/knowledge/{entry_id}`

删除知识条目。

---

### 向量语义搜索

#### `POST /api/v1/knowledge/search`

基于向量相似度搜索知识。

**Request:**
```json
{
  "query": "OWASP Juice Shop 视频 XSS",
  "limit": 5
}
```

**Response:**
```json
{
  "results": [
    {
      "knowledge": {
        "id": 1,
        "scenario": "Juice Shop Video XSS via subtitle upload",
        "target_type": "web",
        "vulnerability_type": "xss",
        "key_findings": "..."
      },
      "similarity": 0.92
    }
  ]
}
```

**内部流程：**

```
query text
  │
  ▼
generate_embedding(query)    ← 调用 zhipuai embedding API
  │
  ▼
pgvector cosine similarity   ← SQL: 1 - (embedding <=> query_vec::vector)
  │                            WHERE user_id = :uid
  │                            AND extraction_status = 'success'
  │                            ORDER BY distance LIMIT :k
  ▼
过滤 similarity < 0.6
  │
  ▼
返回 [(KnowledgeEntry, score), ...]
```

---

### Agent 端点（RAG 注入发生处）

#### `POST /api/v1/agent`

**Request:**
```json
{
  "messages": [{"role": "user", "content": "攻击 Juice Shop 的视频功能，嵌入 XSS"}],
  "agent_mode": "terminal",
  "security_mode": "offense",
  "lang": "zh-CN",
  "max_turns": 20
}
```

**RAG 注入（agent_service.py `run_agent_loop` 内部）：**

```python
# 1. 提取用户第一条消息作为查询
user_query = "攻击 Juice Shop 的视频功能，嵌入 XSS"

# 2. 向量检索
rag_context = await search_and_format_knowledge(user_query, user_id, lang)

# 3. 拼接到 system prompt 末尾
system_prompt += f"\n\n{rag_context}"
```

**注入后的 system prompt 片段：**

```markdown
## 相关历史经验
以下是从知识库检索到的相关经验，仅供参考（目标环境可能不同）：

### 经验 1: Juice Shop Video XSS via subtitle upload（相似度: 92%）
- 目标类型: web | 漏洞: xss
- 工具: curl
- 关键发现: 通过 /api/Complaints 认证后上传恶意 VTT 字幕文件，
  字幕内容包含 </script><script>alert(`xss`)</script> 实现 DOM XSS
- 结果: success
```

**SSE 事件流：**
```
data: {"event": "session_start", "data": {"session_id": 44}}
data: {"event": "turn", "data": {"turn": 1, "max_turns": 20}}
data: {"event": "text", "data": {"content": "根据历史经验..."}}
data: {"event": "action", "data": {"type": "shell", ...}}
data: {"event": "action_result", "data": {...}}
...
data: {"event": "done", "data": {"reason": "complete"}}
data: [DONE]
```

---

## Embedding API 调用详情

### 请求格式（OpenAI 兼容，zhipuai 相同）

```
POST https://open.bigmodel.cn/api/paas/v4/embeddings
Authorization: Bearer {RAG_EMBEDDING_API_KEY}
Content-Type: application/json

{
  "input": "Scenario: Juice Shop XSS\nSummary: ...\nKey findings: ...",
  "model": "embedding-3"
}
```

- `input` 截断至 8000 字符
- `model` 取自 `RAG_EMBEDDING_MODEL`

### 响应格式

```json
{
  "data": [
    {
      "embedding": [0.017928, 0.014538, 0.000363, ...],
      "index": 0
    }
  ],
  "model": "embedding-3",
  "usage": {
    "prompt_tokens": 42,
    "total_tokens": 42
  }
}
```

返回值取 `data[0]["embedding"]`，为 float 数组（zhipuai embedding-3 返回 2048 维）。

### pgvector 存储

```sql
UPDATE knowledge_entries
SET embedding = '[0.017928, 0.014538, ...]'::vector
WHERE id = :entry_id;
```

### pgvector 检索

```sql
SELECT id, 1 - (embedding <=> :query_vec::vector) AS similarity
FROM knowledge_entries
WHERE user_id = :uid
  AND embedding IS NOT NULL
  AND extraction_status = 'success'
ORDER BY embedding <=> :query_vec::vector
LIMIT 5;
```

`<=>` 是 pgvector 的 cosine distance 运算符：`distance = 1 - cosine_similarity`。

---

## 完整流程示例

### 第一次：用户手动教 AI

```
用户: "Juice Shop Video XSS 应该用 /api/Complaints 上传恶意 VTT 文件"
AI:   "明白了，让我按这个方案执行..."
      → curl -X POST /api/Complaints -F "file=@xss.vtt" -H "Authorization: ..."
      → 成功触发 XSS
```

Session 结束 → 自动持久化到 `agent_sessions` + `session_turns`。

### 第二步：提取知识

用户在 Sessions 页面点击"生成报告"：

```
POST /api/v1/sessions/44/extract
```

后台：
1. 压缩 session → 摘要文本
2. AI 提取 → `{"scenario": "Juice Shop Video XSS", "vulnerability_type": "xss", ...}`
3. AI 生成 → 学习报告 Markdown
4. 保存 KnowledgeEntry
5. 调用 zhipuai embedding API → 向量存入 pgvector

### 第三次：新 Session 自动检索

```
用户: "帮我攻击 Juice Shop 的视频功能"
```

Agent 启动前：
1. `generate_embedding("帮我攻击 Juice Shop 的视频功能")` → 查询向量
2. pgvector 余弦搜索 → 命中 "Juice Shop Video XSS" 条目（相似度 0.92）
3. 格式化为 RAG 上下文 → 注入 system prompt
4. AI 直接按历史经验执行，不再瞎猜端点

---

## 设计决策

| 决策 | 理由 |
|------|------|
| 每用户隔离 | 知识检索 `WHERE user_id = :uid`，确保多用户数据隔离 |
| 延迟 embedding | 只在 `RAG_ENABLED=true` 时生成向量，降低无 RAG 场景的 API 开销 |
| 优雅降级 | RAG 失败不中断 agent 执行，try/except 静默吞异常 |
| 语言感知 | RAG 上下文根据 session 语言格式化（中/英） |
| 无 ANN 索引 | zhipuai embedding-3 为 2048 维，超过 pgvector HNSW/IVFFlat 的 2000 维限制，使用顺序扫描（小数据量足够） |
| 阈值过滤 | 相似度 < 0.6 的结果丢弃，避免注入无关经验干扰 agent |
| 自定义 URL | `RAG_EMBEDDING_URL` 支持任意 OpenAI 兼容端点，不绑定厂商 |

---

> **写入**：每次攻防会话结束 → AI 提取结构化知识 → Embedding API 转向量 → 存入 pgvector
>
> **读取**：新会话开始 → 用户问题转向量 → 余弦相似度检索 TOP 5 → 拼接到 System Prompt → AI 带着历史经验执行
>
> **核心价值：AI Agent 不再失忆，每次攻防都能站在历史经验的肩膀上。**
