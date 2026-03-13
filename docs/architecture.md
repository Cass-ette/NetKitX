# NetKitX 架构设计文档

## 1. 项目概述

NetKitX 是一个可扩展的网络安全集成工具 Web 应用，支持插件化工具管理、AI 自主执行、攻防知识库、实时任务执行和用户自定义扩展。

### 技术栈

| 层 | 技术 |
|---|------|
| 前端 | Next.js 16 + TypeScript + Shadcn/UI + Tailwind CSS |
| 后端 | Python FastAPI + SQLAlchemy async |
| 高性能引擎 | Go (独立二进制，subprocess 调用) |
| 数据库 | PostgreSQL (asyncpg, JSONB) |
| 缓存/队列 | Redis |
| 任务队列 | Celery |
| 认证 | JWT + GitHub OAuth + WebAuthn (Passkey) |
| AI | Claude (Anthropic) / DeepSeek / GLM (智谱 AI) |
| 沙箱 | Docker per-user containers |
| 部署 | Docker Compose + Nginx + Let's Encrypt |

## 2. 系统架构

```
                      ┌──────────────────────────────────┐
                      │            Browser               │
                      │   (Passkey / GitHub OAuth / JWT)  │
                      └──────────────┬───────────────────┘
                                     │ HTTPS
                      ┌──────────────▼───────────────────┐
                      │     Nginx (SSL Termination)      │
                      │     Let's Encrypt + Certbot      │
                      └───┬──────────────────────────┬───┘
                          │ /api/*                   │ /*
               ┌──────────▼──────────┐   ┌───────────▼──────────┐
               │ FastAPI Backend     │   │ Next.js Frontend     │
               │ (Port 8000)        │   │ (Port 3000)          │
               │                    │   │                      │
               │ ┌────────────────┐ │   │ ┌──────────────────┐ │
               │ │  Auth Layer    │ │   │ │ Dashboard        │ │
               │ │ JWT+OAuth+     │ │   │ │ AI Chat/Agent    │ │
               │ │ WebAuthn       │ │   │ │ Sessions/KB      │ │
               │ └───────┬────────┘ │   │ │ Tools/Tasks      │ │
               │         │          │   │ │ Marketplace      │ │
               │ ┌───────▼────────┐ │   │ │ Topology         │ │
               │ │ Plugin Manager │ │   │ │ Terminal (xterm)  │ │
               │ │ + AI Agent     │ │   │ └──────────────────┘ │
               │ └─┬───┬───┬───┬─┘ │   └──────────────────────┘
               │   │   │   │   │   │
               │ ┌─▼─┐│┌──▼┐┌─▼──┐│
               │ │Py ││ │Go││Sand││
               │ │   ││ │  ││box ││
               │ └───┘│└──┘│└────┘│
               │      │    │      │
               │ ┌────▼────▼────┐ │
               │ │ Celery Worker│ │
               │ └──────────────┘ │
               └────────┬─────────┘
                        │
          ┌─────────────▼──────────────┐
          │  PostgreSQL    │    Redis   │
          │  (Data + KB)   │   (Cache)  │
          └────────────────────────────┘
```

## 3. 目录结构

```
NetKitX/
├── backend/                   # Python FastAPI
│   ├── app/
│   │   ├── main.py            # FastAPI 入口
│   │   ├── api/v1/
│   │   │   ├── auth.py        # 认证 (登录/注册/GitHub OAuth)
│   │   │   ├── passkey.py     # WebAuthn Passkey 认证
│   │   │   ├── tools.py       # 工具列表
│   │   │   ├── tasks.py       # 任务管理 + 日志
│   │   │   ├── plugins.py     # 插件管理
│   │   │   ├── marketplace.py # 插件市场
│   │   │   ├── ai.py          # AI 对话/Agent/分析
│   │   │   ├── knowledge.py   # 知识库 API
│   │   │   ├── reports.py     # 报告导出
│   │   │   ├── topology.py    # 网络拓扑
│   │   │   ├── admin.py       # 管理员接口
│   │   │   └── terminal.py    # 沙箱终端
│   │   ├── core/
│   │   │   ├── config.py      # 全局配置 (Settings)
│   │   │   ├── database.py    # 数据库连接
│   │   │   ├── security.py    # JWT 生成/验证
│   │   │   └── deps.py        # 依赖注入 (get_current_user, get_admin_user)
│   │   ├── models/
│   │   │   ├── user.py        # 用户 (github_id, avatar_url)
│   │   │   ├── task.py        # 任务
│   │   │   ├── plugin.py      # 插件
│   │   │   ├── ai_settings.py # AI 配置 (加密 API key)
│   │   │   ├── passkey.py     # WebAuthn 凭证
│   │   │   ├── knowledge.py   # 知识库 (AgentSession, SessionTurn, KnowledgeEntry)
│   │   │   └── marketplace.py # 市场 (Package, Version, Review...)
│   │   ├── services/
│   │   │   ├── ai_service.py       # AI 调用 (Claude/DeepSeek/GLM)
│   │   │   ├── agent_service.py    # AI Agent 自主执行
│   │   │   ├── passkey_service.py  # WebAuthn 注册/认证
│   │   │   ├── knowledge_service.py # 知识提取/学习报告
│   │   │   ├── sandbox_service.py  # Docker 沙箱管理
│   │   │   ├── report_service.py   # HTML/PDF 报告渲染
│   │   │   ├── topology_service.py # 扫描结果 → 拓扑图
│   │   │   └── auth_service.py     # 用户认证逻辑
│   │   ├── marketplace/       # 插件市场核心
│   │   │   ├── version.py     # SemVer 版本管理
│   │   │   ├── resolver.py    # PubGrub 依赖解析
│   │   │   ├── installer.py   # 插件安装/验证
│   │   │   └── scanner.py     # 安全扫描
│   │   ├── plugins/           # 插件系统核心
│   │   │   ├── base.py        # PluginBase 抽象类
│   │   │   ├── loader.py      # 动态加载器
│   │   │   └── registry.py    # 插件注册表
│   │   ├── templates/         # Jinja2 报告模板
│   │   └── workers/           # Celery 异步任务
│   ├── migrations/            # Alembic 数据库迁移
│   └── tests/                 # 单元测试 (70+ tests)
│
├── frontend/                  # Next.js 16 + TypeScript
│   ├── src/
│   │   ├── app/               # App Router 页面
│   │   │   ├── (auth)/        # 登录 (含 Passkey/GitHub)
│   │   │   ├── auth/github/   # GitHub OAuth 回调
│   │   │   ├── dashboard/     # 仪表盘
│   │   │   ├── tools/[slug]/  # 工具执行页
│   │   │   ├── tasks/         # 任务管理
│   │   │   ├── plugins/       # 插件管理
│   │   │   ├── marketplace/   # 插件市场
│   │   │   ├── ai-chat/       # AI 对话/Agent
│   │   │   ├── sessions/      # Agent 会话历史
│   │   │   ├── knowledge/     # 攻防知识库
│   │   │   ├── topology/      # 网络拓扑可视化
│   │   │   ├── settings/      # 系统设置 (AI/Passkey)
│   │   │   ├── admin/         # 管理员面板
│   │   │   └── developers/    # 开发者页面
│   │   ├── components/
│   │   │   ├── ui/            # Shadcn/UI 基础组件
│   │   │   ├── layout/        # Shell / Sidebar / Header
│   │   │   ├── ai/            # AI 对话/分析组件
│   │   │   ├── terminal/      # xterm.js 终端
│   │   │   ├── topology/      # React Flow 拓扑图
│   │   │   └── tools/         # 工具通用组件
│   │   ├── hooks/             # 自定义 hooks (use-ai-chat, use-translations)
│   │   ├── lib/               # API client, 状态管理 (zustand)
│   │   ├── i18n/              # 国际化 (8 语言 × 多命名空间)
│   │   └── types/             # TypeScript 类型定义
│   └── public/                # 静态资源
│
├── plugins/                   # 用户自定义插件目录
│   ├── example_ping/
│   ├── example_portscan/
│   ├── sql_inject/            # SQL 注入测试 v2.0.0
│   └── ...                    # 14+ 内置插件
│
├── engines/                   # Go 高性能引擎
│   ├── cmd/                   # Go 命令入口
│   ├── pkg/                   # 共享库
│   └── bin/                   # 编译后的二进制
│
├── scripts/                   # 运维脚本
│   ├── start.sh / stop.sh     # 本地开发
│   ├── deploy.sh              # 生产部署
│   ├── status.sh / logs.sh    # 监控
│   ├── restart.sh             # 重启
│   └── backup-db.sh           # 数据库备份
│
├── docs/                      # 项目文档
├── docker-compose.yml         # 本地开发
└── docker-compose.prod.yml    # 生产部署
```

## 4. 插件系统设计

插件系统是 NetKitX 扩展性的核心。添加新工具只需编写 `plugin.yaml` + Python/Go 文件，前端自动渲染表单和结果。

### 4.1 插件声明 (plugin.yaml)

```yaml
name: nmap-scanner
version: 1.0.0
description: Nmap 端口与服务扫描
category: recon          # recon | vuln | exploit | utils
author: NetKitX
engine: python           # python | go | cli

params:
  - name: target
    label: 目标地址
    type: string
    required: true
    placeholder: "192.168.1.0/24"

output:
  type: table            # table | json | terminal | chart
  columns:
    - { key: "host", label: "主机" }
    - { key: "port", label: "端口" }
    - { key: "state", label: "状态" }
```

### 4.2 插件基类 (Python)

```python
class PluginBase(ABC):
    @abstractmethod
    async def execute(self, params: dict) -> AsyncIterator[PluginEvent]:
        """执行插件，通过 yield 实时推送进度和结果"""
        ...
```

### 4.3 Go 引擎集成

Go 模块编译为独立二进制，Python 通过 subprocess 调用，JSON stdio 通信。

## 5. 认证系统

```
┌─────────────────────────────────────────┐
│            认证方式                       │
├─────────────┬──────────────┬────────────┤
│ 账号密码     │ GitHub OAuth │ Passkey    │
│ POST /login │ GET /github  │ WebAuthn   │
│             │ → callback   │ FIDO2      │
├─────────────┴──────────────┴────────────┤
│         create_access_token(username)    │
│              ↓ JWT Token                 │
│         get_current_user(token)          │
│              ↓ User object               │
│         Bearer Authorization             │
└─────────────────────────────────────────┘
```

- **JWT** — 所有认证方式最终都生成 JWT token，subject 为 username
- **GitHub OAuth** — 自动创建/关联用户，获取 avatar
- **Passkey (WebAuthn)** — py-webauthn 库，challenge 存储在 Redis（支持多 worker）
- **RBAC** — `user` / `admin` 角色，`get_admin_user` 依赖注入

## 6. AI Agent 架构

```
用户选择模式 → AI Agent Service
    │
    ├── 对话模式: AI 只回答问题
    │
    ├── 半自动 (semi_auto):
    │   AI 提议 → SSE event "waiting" → 用户确认 → 执行 → 结果 → AI 继续
    │
    ├── 全自动 (full_auto):
    │   AI 分析 → 解析 <action> XML → 执行插件 → 结果注入 → 循环 (max N 轮)
    │
    └── 终端 (terminal):
        AI 分析 → 执行 shell + 插件 → Docker 沙箱隔离 → 黑名单过滤 → 循环

SSE Events: text, turn, action, action_status, action_result, action_error,
            session_start, waiting, done
```

### 自我纠错

Agent 具备错误分类和重试能力：
- 恢复格式错误的 XML action
- 分类错误类型（网络、权限、超时、参数错误等）
- 自动重试可恢复错误
- **精准错误反馈**：多 action 并行部分失败时，逐条报告 OK/FAILED，AI 只重试失败的

### 知识提取

```
Agent 会话 → finalize_session() → build_session_digest()
    → AI Call 1: 结构化 JSON (技术、漏洞、工具、难度...)
    → AI Call 2: Markdown 学习报告
    → 存入 KnowledgeEntry
```

## 7. 数据库设计

```
┌──────────────┐  ┌──────────────┐  ┌───────────────────┐
│    users     │  │    tasks     │  │   plugins         │
├──────────────┤  ├──────────────┤  ├───────────────────┤
│ id           │  │ id           │  │ id                │
│ username     │  │ user_id (FK) │  │ name              │
│ email        │  │ plugin_name  │  │ version           │
│ hashed_pwd   │  │ status       │  │ category          │
│ role         │  │ params (JSON)│  │ config (JSON)     │
│ github_id    │  │ result (JSON)│  │ enabled           │
│ avatar_url   │  │ created_at   │  └───────────────────┘
└──────┬───────┘  └──────────────┘
       │
       │  ┌──────────────────┐  ┌──────────────────────┐
       ├──│ passkey_creds    │  │ ai_settings          │
       │  ├──────────────────┤  ├──────────────────────┤
       │  │ id               │  │ id                   │
       │  │ user_id (FK)     │  │ user_id (FK)         │
       │  │ credential_id    │  │ provider             │
       │  │ public_key       │  │ api_key (encrypted)  │
       │  │ sign_count       │  │ model                │
       │  │ name             │  │ base_url             │
       │  └──────────────────┘  └──────────────────────┘
       │
       │  ┌──────────────────┐  ┌──────────────────────┐
       ├──│ agent_sessions   │  │ knowledge_entries    │
       │  ├──────────────────┤  ├──────────────────────┤
       │  │ id (UUID)        │  │ id                   │
       │  │ user_id (FK)     │  │ session_id (FK)      │
       │  │ mode             │  │ user_id (FK)         │
       │  │ model            │  │ category             │
       │  │ total_turns      │  │ title                │
       │  │ status           │  │ summary              │
       │  └───────┬──────────┘  │ techniques (JSON)    │
       │          │             │ learning_report      │
       │  ┌───────▼──────────┐  │ search_vector (ts)   │
       │  │ session_turns    │  └──────────────────────┘
       │  ├──────────────────┤
       │  │ id               │  ┌──────────────────────┐
       │  │ session_id (FK)  │  │ marketplace tables   │
       │  │ turn_number      │  ├──────────────────────┤
       │  │ role             │  │ packages             │
       │  │ content          │  │ package_versions     │
       │  │ action_type      │  │ package_dependencies │
       │  │ action_result    │  │ user_installs        │
       │  └──────────────────┘  │ package_reviews      │
       │                        │ security_reports     │
       │                        └──────────────────────┘
```

## 8. 迭代计划

### Phase 1: 基础骨架 ✅
- 前后端项目初始化、Docker Compose 环境
- 用户认证 (JWT)
- 插件系统核心 (加载、执行、注册)
- 示例插件 (端口扫描)

### Phase 2: 核心功能 ✅
- 任务管理 (创建、查看、取消)
- WebSocket 实时进度推送
- Go 引擎集成
- Dashboard 仪表盘

### Phase 3: 扩展增强 ✅
- 插件市场 — 7 阶段完成（基础设施 → 依赖解析 → 安装器 → UI → 发布 → 安全扫描 → 更新系统）
- 报告导出 — Jinja2 + WeasyPrint 生成 HTML/PDF
- 内嵌终端 — xterm.js 只读终端 + WebSocket 实时流
- 网络拓扑可视化 — React Flow + dagre 自动布局

### Phase 4: AI 集成 ✅
- AI 对话 — Claude/DeepSeek/GLM 多提供商支持
- 防御/进攻模式切换
- 语言感知响应
- AI 分析面板 + 全页面聊天

### Phase 5: AI Agent 自主执行 ✅
- 半自动/全自动/终端三种模式
- XML action 解析和执行
- 自我纠错（错误分类、重试、XML 恢复）
- SSE 事件流

### Phase 6: 安全隔离 ✅
- Per-user Docker 沙箱容器
- 命令黑名单过滤
- 容器生命周期管理

### Phase 7: 攻防知识库 ✅
- Phase 1: 会话持久化 (AgentSession, SessionTurn)
- Phase 2: 知识提取 + 学习报告 (KnowledgeEntry, AI 双调用)

### Phase 8: 认证增强 ✅
- GitHub OAuth 登录
- Passkey (WebAuthn) 免密登录
- HTTPS 配置 (Let's Encrypt)

### Phase 9: 工作流增强 ✅
- 工作流节点智能去重（跨 turn 相同命令/插件指纹去重）
- Agent 精准错误反馈（多 action 部分失败时逐条 OK/FAILED）
- 工作流模拟模式（按 DAG 展示攻击路径，不实际执行）

### Phase 10: Agent 停滞检测优化 + 靶场基础设施 ✅
- **双层停滞检测**：
  - 战术层：shell 指纹归一化（curl/wget/sqlmap 去 URL base），比较时去类型前缀
  - 战略层：reasoning 指纹检测连续相似推理，第 3 轮警告、第 5 轮终止
- **NULL 字节修复**：`finalize_session()` 写入前过滤 `\u0000`，防止 PostgreSQL 报错
- **靶场部署**：服务器 `/opt/targets` 下运行 Juice Shop (4001)、DVWA (4002)、WebGoat (4003)
- 新增 22 项单元测试（指纹归一化 13 项 + reasoning 停滞 6 项 + NULL 字节 7 项）

### Phase 11: Agent 健康监控 ✅
- **零 token 开销**：agent loop 每轮写 metrics 到 Redis，独立 FastAPI 读取
- **监控端口 9090**：JSON API + HTML Dashboard（2s 自动刷新）
- **健康分**：基线 50 分，正向（成功/新策略/无错误）加分，负向（停滞/错误/无效结果）扣分
- **停滞检测优化**：无 positive 信号 = 无进展，reasoning stagnation 在 STOP 级别绕过 negative gate

### 待定
- 网安专用模型微调
- 高级功能（包签名、CDN）

---

## 插件生态架构

### 仓库结构

```
NetKitX (主仓库)
├── plugins/
│   ├── port-scan/          # 官方内置插件
│   ├── sql-inject/
│   ├── dir-scan/
│   └── community/          # 社区插件 (Git Submodule)
│       └── → NetKitX-Plugins/community/

NetKitX-Plugins (独立仓库)
├── community/              # 稳定的社区插件
├── experimental/           # 实验性插件
└── templates/              # 插件开发模板
```

### 部署方式：Git Submodule

```bash
# 服务器更新
cd /opt/NetKitX
git pull origin main
git submodule update --init --recursive --remote
docker compose -f docker-compose.prod.yml restart backend
```

### 插件分类

| 类型 | 位置 | 维护 | 质量标准 |
|------|------|------|----------|
| 官方插件 | `NetKitX/plugins/` | 核心团队 | 充分测试 |
| 社区插件 | `NetKitX-Plugins/community/` | 社区贡献者 | 经过审核 |
| 实验性插件 | `NetKitX-Plugins/experimental/` | 个人开发者 | 未充分测试 |
