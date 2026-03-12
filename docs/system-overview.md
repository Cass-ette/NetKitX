# NetKitX 系统全景 — 核心创新与完整度

> 面向演讲的系统性文档，展示 NetKitX 作为网络安全集成平台的核心创新点和工程完整度

---

## 一、系统定位

**NetKitX** 是一个**实验性网络安全工具平台**，核心目标：

1. **中国市场合法化** — 所有功能符合中国网络安全法律法规，面向合法授权的安全测试场景
2. **商业化潜力** — 架构和功能设计考虑未来商业化落地
3. **实用性优先** — 提高真实攻防场景下的应用价值，避免纯学术或演示性功能

**在线演示**: https://wql.me

---

## 二、核心创新点

### 2.1 AI 自主执行引擎（网安领域深度集成）

**创新点**：AI Agent 不仅能对话，还能**自主调用安全工具、执行 shell 命令、自我纠错**。在网安工具平台中率先实现完整的 Agent 自主执行闭环。

#### 三种执行模式

| 模式 | 行为 | 适用场景 |
|------|------|----------|
| **半自动 (Semi-Auto)** | AI 提议 → 用户确认 → 执行 → 结果 → AI 继续 | 学习场景，用户需要理解每一步 |
| **全自动 (Full-Auto)** | AI 自动执行插件（无需确认），最多 N 轮 | 标准化渗透测试流程 |
| **终端模式 (Terminal)** | AI 可执行 shell + 插件，沙箱保护 | 高级用户，需要灵活性 |

#### 防御/进攻双模式

- **防御模式**：漏洞分级、修复建议、加固方案
- **进攻模式**：精确 payload、攻击链、下一步侦察建议

#### 自我纠错机制

- **错误分类**：致命错误 vs 可重试错误
- **精准错误反馈**：多 action 并行部分失败时，AI 收到逐条 OK/FAILED 明细，只重试失败的 action
- **双层停滞检测**（战术层 + 战略层）：
  - **战术层（Action 指纹）**：归一化 shell 指纹（curl/wget/sqlmap 去除 URL base），不同端点探索不误判
  - **战略层（Reasoning 指纹）**：检测连续相似推理文本，同策略打转第 3 轮警告、第 5 轮终止
  - 比较时去除类型前缀（shell:/plugin:），shell 和 plugin 均受益
- **XML 恢复**：自动修复格式错误的 action 标签
- **命令预处理**：自动为 curl 添加 `-s` 静默模式
- **NULL 字节过滤**：session 持久化时自动清除 `\u0000`，避免 PostgreSQL 写入失败

**技术实现**：
- 文件：`backend/app/services/agent_service.py` (406 行)
- SSE 流式输出：9 种事件类型
- 测试覆盖：111 项单元测试

---

### 2.2 攻防知识库 + RAG 增强（三阶段完整实现）

**创新点**：AI Agent 能从历史攻防经验中学习，不再"失忆"。

#### Phase 1: 会话持久化
- 所有 Agent 对话自动保存到 PostgreSQL
- 支持会话回放
- 结构化存储：`AgentSession` + `SessionTurn`

#### Phase 2: 知识提取
- AI 从会话中提取结构化知识（场景、漏洞类型、工具、攻击链、结果）
- 自动生成 Markdown 学习报告
- 19 项测试覆盖提取逻辑

#### Phase 3: RAG Prompt Injection（向量检索增强）
- **pgvector** 向量数据库存储 1536 维 embedding
- **OpenAI / 智谱 AI** embedding API
- **余弦相似度**检索 TOP 5 相关经验（阈值 0.6）
- **自动注入** System Prompt — Agent 启动时带着历史经验执行

**架构图**：见 `docs/rag-architecture.md`

**技术实现**：
- 向量搜索：`backend/app/services/embedding_service.py` (268 行)
- 知识提取：`backend/app/services/knowledge_service.py` (710 行，含 NULL 字节过滤）
- 数据库：PostgreSQL + pgvector 扩展，HNSW 索引
- 测试覆盖：36 项单元测试

---

### 2.3 插件市场（7 阶段完整实现）

**创新点**：完整的插件生态系统，从发布、安装、依赖解析到安全扫描、自动更新。

| 阶段 | 功能 | 测试数 |
|------|------|--------|
| **Phase 1** | 基础设施（模型、API、SemVer 版本管理） | — |
| **Phase 2** | **PubGrub 依赖解析**（冲突检测、循环依赖检测） | 42 |
| **Phase 3** | 安装器（下载、SHA256 校验、安全解压、回滚） | 8 |
| **Phase 4** | 前端 UI（列表、详情、安装弹窗） | — |
| **Phase 5** | 发布系统（Publish API、Yank API、CLI 工具） | 9 |
| **Phase 6** | **安全扫描**（危险模式、权限检查、许可证） | 12 |
| **Phase 7** | **更新系统**（检查更新、一键更新、批量更新、破坏性变更警告） | 8 |

**技术亮点**：
- **PubGrub 算法**：Dart/Pub 同款依赖解析算法，业界最先进
- **安全扫描**：正则匹配 `eval()`, `exec()`, `os.system()` 等危险模式
- **版本约束**：支持 `^1.2.3`, `~1.2.3`, `>=1.0.0,<2.0.0` 等 SemVer 语法

**文件位置**：
- 依赖解析：`backend/app/marketplace/resolver.py` (200 行)
- 安全扫描：`backend/app/marketplace/scanner.py` (410 行)
- 版本管理：`backend/app/marketplace/version.py` (224 行)

---

### 2.4 沙箱终端（Docker 容器隔离）

**创新点**：每用户独立 Docker 容器，黑名单命令过滤，30 秒超时。

**安全机制**：
- **命令黑名单**：20+ 危险模式（`rm -rf /`, fork bomb, curl-to-shell）
- **资源限制**：512MB 内存，0.5 CPU 核心
- **自动清理**：30 分钟空闲超时
- **输出截断**：30KB stdout, 10KB stderr

**技术实现**：
- 沙箱：`backend/app/services/sandbox.py` (108 行)
- 容器管理：`backend/app/services/container_service.py` (153 行)

---

### 2.5 工作流可视化 + AI 逐步反思 + 模拟模式

**创新点**：Agent 会话自动转换为可视化 DAG 工作流，逐步回放时 AI 对每步执行结果进行反思分析；支持模拟模式展示攻击路径而不实际执行。

#### 自动生成 + 智能去重
- Agent 会话结束后一键转换为工作流（start → plugin/shell actions → end）
- 自动提取参数、原因、结果摘要
- **节点去重**：跨 turn 相同命令/插件+参数自动去重，避免 AI 重试产生的重复节点

#### 逐步回放 + AI 反思
- **SSE 流式回放**：`node_start` → `node_result` → `node_reflection` → `workflow_done`
- **AI 反思**：每步执行后，AI 分析「发现 / 意义 / 下一步」（可选，需配置 AI）
- **实时可视化**：running 脉冲动画 + spinner → done 绿色 / failed 红色
- **节点详情面板**：点击任意节点查看参数、原因、完整 JSON 结果、AI Markdown 反思

#### 模拟模式
- **不实际执行**：按 DAG 顺序逐层展示节点 + 显示历史结果摘要，无真实请求发出
- **适用场景**：一次性漏洞利用、破坏性操作等不可重演攻击的路径展示
- **琥珀色状态**：模拟节点以 amber 边框区分，与真实执行的绿色区分

#### 向后兼容
- `reflect=false` 时行为与普通回放一致，无 AI 开销
- `simulate=false` 时行为与真实回放一致（默认）

**技术实现**：
- 工作流服务：`backend/app/services/workflow_service.py`（含去重指纹函数）
- 回放 API：`backend/app/api/v1/workflows.py`（SSE + AI 反思 + 模拟模式）
- 前端组件：`frontend/src/components/workflow/`（graph, nodes, node-detail-panel）
- 测试覆盖：25 项单元测试

---

### 2.6 插件引擎 2.0 — 会话模式 + 自定义 UI + 工作流编排

**创新点**：插件从"一次性请求-响应"升级为**持久会话模式**，支持 WebSocket 双向通信；插件可注册自定义前端组件；Agent 会话可转换为可视化 DAG 工作流。

#### Phase 1: 会话模式（已完成）

```python
class SessionPlugin(PluginBase):
    mode = "session"

    async def on_session_start(self, params) -> dict:
        """初始化会话状态"""

    async def on_message(self, session_id, message, state):
        """处理会话内消息，yield 事件"""

    async def on_session_end(self, session_id, state):
        """会话结束清理"""
```

#### 会话管理

- **Redis 状态存储**：会话 state 以 JSON 序列化存入 Redis Hash，TTL 1 小时
- **REST API**：创建/列出/查询/关闭会话
- **WebSocket 端点**：`/api/v1/ws/plugin-sessions/{session_id}` 双向通信
- **消息协议**：`message`/`ping`/`close` 入站，`event`/`pong`/`error`/`session_end` 出站

#### WebShell 2.1.0 — 首个会话插件

- **xterm.js 交互终端**：命令行体验，命令历史（上下箭头）
- **持久会话**：连续执行命令无需重复传连接参数
- **工作目录跟踪**：`cd` 命令更新 state 中的 cwd

#### 向后兼容

- 所有现有 oneshot 插件零改动继续运行
- SessionPlugin 的 `execute()` 方法提供 one-shot 回退
- plugin.yaml 新增 `mode: session` 字段（默认 `oneshot`）

**技术实现**：
- SDK 基类：`sdk/netkitx_sdk/base.py` — SessionPlugin
- 会话服务：`backend/app/services/session_plugin_service.py`
- WebSocket：`backend/app/api/v1/plugin_sessions.py`
- 前端终端：`frontend/src/components/plugin-session/session-terminal.tsx`
- 测试覆盖：24 项单元测试

#### Phase 2: 自定义 UI（已完成）
- 插件可在 `plugin.yaml` 声明 `ui_component`
- 前端根据声明渲染自定义组件（不局限于表格输出）
- 插件注册表自动传递 UI 组件元数据

#### Phase 3: 工作流编排（已完成）
- Agent 会话自动转换为 DAG 工作流（start → actions → end）
- React Flow + dagre 自动布局可视化
- SSE 逐步回放：节点依次执行，实时状态更新
- AI 逐步反思：每步完成后 AI 分析发现/意义/下一步

---

## 三、工程完整度

### 3.1 前端（Next.js 16 + TypeScript）

**22 个页面路由**：

| 类别 | 页面 | 功能 |
|------|------|------|
| **核心功能** | Dashboard, Tools, Tasks, Plugins | 工具执行、任务管理、插件管理 |
| **AI 功能** | AI Chat, Sessions, Knowledge | AI 对话、会话回放、知识库 |
| **工作流** | Workflows, Workflow Detail | 工作流列表、可视化回放 + AI 反思 |
| **市场** | Marketplace, Marketplace Detail | 插件浏览、安装、更新 |
| **可视化** | Topology | 网络拓扑图（React Flow + dagre） |
| **管理** | Settings, Admin, Developers | 用户设置、管理员面板、开发者文档 |
| **认证** | Login, GitHub OAuth | 登录、OAuth 回调 |

**国际化**：8 种语言 × 511 个翻译键 = **4088 条翻译**

**UI 组件库**：Shadcn/UI + Tailwind CSS

---

### 3.2 后端（FastAPI + SQLAlchemy Async）

**16 个 API 模块**：

| 模块 | 端点数 | 功能 |
|------|--------|------|
| `auth.py` | 7 | 注册、登录、JWT、GitHub OAuth |
| `passkey.py` | 6 | WebAuthn 免密登录 |
| `marketplace.py` | 25+ | 插件市场全功能 |
| `ai.py` | 5 | AI 分析、对话、Agent |
| `knowledge.py` | 8 | 会话持久化、知识提取、RAG 搜索 |
| `workflows.py` | 5 | 工作流 CRUD、SSE 回放 + AI 反思 |
| `plugin_sessions.py` | 4+WS | 插件会话管理 + WebSocket |
| `tasks.py` | 4 | 任务创建、查询、日志 |
| `plugins.py` | 4 | 插件上传、启用/禁用、删除 |
| `topology.py` | 2 | 网络拓扑数据 |
| `reports.py` | 1 | 报告导出（HTML/PDF） |
| `whitelist.py` | CRUD | 授权目标管理 |
| `admin.py` | 多个 | 用户管理、配额、统计 |
| `terminal.py` | WebSocket | 实时终端 |
| `tools.py` | 2 | 工具列表 |

**数据库**：PostgreSQL 16 + pgvector 扩展

**缓存**：Redis 7

---

### 3.3 插件系统

**16 个内置插件**：

| 类别 | 插件 | 说明 |
|------|------|------|
| **Recon** | dir_scan, subdomain_enum, dns_lookup, ssl_check, http_request | 信息收集 |
| **Vuln** | sql_inject, file_upload, backup_scan, brute_force, git_leak, svn_leak, hg_leak, webshell | 漏洞检测 |
| **Utils** | http_request | HTTP 调试 |
| **Community** | community/ | 社区插件（Git submodule） |

**双引擎 + 双模式支持**：
- **Python 引擎**：基于 `PluginBase` 异步生成器
- **Go 引擎**：独立二进制，JSON stdio 通信
- **Oneshot 模式**：单次执行，request-response
- **Session 模式**：持久会话，WebSocket 双向通信

**SDK**：`netkitx_sdk` 已发布到 PyPI

---

### 3.4 认证系统（三种方式）

| 方式 | 技术 | 说明 |
|------|------|------|
| **账号密码** | JWT + bcrypt | 传统认证 |
| **GitHub OAuth** | OAuth 2.0 | 一键授权登录 |
| **Passkey (WebAuthn)** | FIDO2 | 指纹/Face ID 免密登录 |

**目标白名单**：
- 非管理员用户必须授权目标才能执行工具
- 支持域名、IP、CIDR 范围
- 子域名自动匹配

---

### 3.5 测试覆盖

**335 项单元测试**：

| 模块 | 测试数 | 覆盖率 |
|------|--------|--------|
| Agent 服务 | 68 | 66% |
| 知识库 | 36 | 46% |
| 插件会话 | 24 | 23% |
| 版本管理 | 24 | 91% |
| 工作流 | 25 | 74% |
| 管理员 | 22 | 15% |
| 白名单 | 16 | 19% |
| 市场 | 18 | — |
| 依赖解析 | 15 | — |
| 报告 | 10 | 90% |
| 拓扑 | 8 | 100% |
| 其他 | 69 | — |

**总覆盖率**：44%（核心模块 60%+）

---

### 3.6 CI/CD

**GitHub Actions 工作流**：

| 工作流 | 触发条件 | 任务 |
|--------|----------|------|
| `ci.yml` | Push/PR | ruff format, ruff check, pytest, eslint, tsc, Trivy 安全扫描 |
| `docker.yml` | Push to main | 构建并推送到 ghcr.io |
| `release.yml` | 版本标签 | 自动生成 Changelog 和 GitHub Release |

**部署脚本**：
- `deploy.sh` — 一键部署到生产（push + pull + rebuild + migrate）
- `backup-db.sh` — 数据库备份（保留最近 7 份）
- `logs.sh`, `restart.sh`, `status.sh` — 运维工具

---

## 四、技术栈

### 前端
- **框架**：Next.js 16 (App Router)
- **语言**：TypeScript
- **UI**：Shadcn/UI + Tailwind CSS + Radix UI
- **状态管理**：Zustand
- **图表**：React Flow (拓扑图), Recharts (统计图)
- **终端**：xterm.js
- **i18n**：自研翻译系统（8 种语言）

### 后端
- **框架**：FastAPI
- **ORM**：SQLAlchemy (async)
- **数据库**：PostgreSQL 16 + pgvector
- **缓存**：Redis 7
- **任务队列**：Celery
- **认证**：JWT + WebAuthn (py_webauthn)
- **报告**：Jinja2 + WeasyPrint (PDF)
- **AI**：httpx (流式 SSE)

### 基础设施
- **容器化**：Docker + Docker Compose
- **反向代理**：Nginx (生产环境)
- **SSL**：Let's Encrypt (Certbot 自动续期)
- **CI/CD**：GitHub Actions
- **镜像仓库**：GitHub Container Registry (ghcr.io)

---

## 五、数据统计

| 指标 | 数值 |
|------|------|
| **代码行数** | 后端 ~10,400 行，前端 ~12,000 行 |
| **前端页面** | 22 个路由 |
| **后端 API** | 16 个模块，70+ 端点 |
| **插件数量** | 16 个内置 + 社区插件 |
| **插件模式** | 2 种（oneshot + session） |
| **AI 提供商** | 4 个（Claude, DeepSeek, GLM, OpenAI-compatible） |
| **AI 模式** | 3 种执行模式 × 2 种安全模式 = 6 种组合 |
| **国际化** | 8 种语言 × 511 键 = 4088 条翻译 |
| **认证方式** | 3 种（密码、OAuth、Passkey） |
| **单元测试** | 335 项 |
| **市场阶段** | 7 阶段全部完成 |
| **知识库阶段** | 3 阶段全部完成（RAG 增强） |
| **插件引擎** | 2.0 三阶段全部完成（会话 + 自定义 UI + 工作流） |
| **数据库表** | 20+ 张表 |
| **Docker 服务** | 5 个（backend, worker, frontend, db, redis） |

---

## 六、核心文档索引

| 文档 | 路径 | 说明 |
|------|------|------|
| **系统架构** | `docs/architecture.md` | 整体架构设计 |
| **RAG 架构** | `docs/rag-architecture.md` | 知识库向量检索架构 |
| **插件开发** | `docs/plugin-development.md` | 插件开发指南 |
| **市场设计** | `docs/plugin-marketplace-design.md` | 插件市场设计文档 |
| **市场使用** | `docs/marketplace-usage.md` | 插件市场使用指南 |
| **工具规划** | `docs/tools-roadmap.md` | 安全工具开发规划 |
| **Roadmap** | `docs/roadmap.md` | 项目路线图（含引擎 2.0） |
| **CI/CD** | `docs/ci-cd.md` | CI/CD 配置说明 |

---

## 七、未来规划

### 短期（1-2 个月）

1. **高级市场功能**
   - 插件包签名（GPG/cosign）
   - CDN 分发（S3/R2）

### 中期（3-6 个月）

2. **网安专用模型微调**
   - 基于积累的攻防数据 fine-tune
   - 等数据量足够后启动

### 长期（6-12 个月）

3. **企业级功能**
   - 多租户支持
   - 审计日志完善
   - RBAC 细粒度权限

---

## 八、总结

NetKitX 是一个**工程完整度极高**的网络安全集成平台，核心创新点包括：

1. **AI 自主执行引擎** — 网安领域深度集成的 AI Agent 自主调用工具 + 自我纠错
2. **攻防知识库 + RAG** — 让 AI 从历史经验中学习，不再失忆
3. **完整插件市场** — PubGrub 依赖解析 + 安全扫描 + 自动更新
4. **插件引擎 2.0** — 会话模式 + 自定义 UI + 工作流编排（三阶段全部完成）
5. **工作流可视化** — DAG 图 + 逐步回放 + AI 逐步反思
6. **沙箱终端** — Docker 容器隔离 + 黑名单过滤

**技术栈现代化**：Next.js 16 + FastAPI + PostgreSQL + pgvector + Redis + Docker

**测试覆盖充分**：234 项单元测试，核心模块 60%+ 覆盖率

**国际化完善**：8 种语言，4088 条翻译

**部署成熟**：Docker Compose + GitHub Actions + 一键部署脚本

**在线演示**：https://wql.me
