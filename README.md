# NetKitX

可扩展的网络安全集成工具平台，支持插件化工具管理、AI 自主执行、实时任务执行和 Web UI 操作。

**在线演示**: https://wql.me

## 特性

- **插件化架构** — Python 和 Go 双引擎支持，热加载无需重启
- **Web UI 管理** — 拖拽上传插件、实时启用/禁用、一键删除
- **实时任务执行** — WebSocket 推送进度和结果，支持并发任务
- **AI 自主执行** — 集成 Claude/DeepSeek/GLM，支持半自动/全自动/终端三种执行模式
- **防御/进攻双模式** — AI 可切换防御建议或精确攻击 payload
- **攻防知识库** — 自动提取会话知识，生成学习报告，RAG 向量检索增强
- **工作流可视化** — Agent 会话自动转换为 DAG 工作流，逐步回放 + AI 逐步反思分析
- **沙箱终端** — 每用户 Docker 容器隔离，黑名单命令过滤
- **报告导出** — 任务结果一键导出为 PDF 或 HTML
- **内嵌终端** — xterm.js 实时展示执行日志，支持历史回溯
- **网络拓扑可视化** — 扫描结果自动生成交互式网络关系图（React Flow + dagre）
- **插件市场** — 发布、搜索、安装插件，内置依赖解析（PubGrub）和安全扫描
- **插件会话模式** — 持久 WebSocket 双向通信，支持交互式终端等高级场景
- **多种认证方式** — 账号密码、GitHub OAuth、Passkey (WebAuthn) 免密登录
- **高性能引擎** — Go 编译的独立二进制，适合大规模扫描
- **国际化** — 8 种语言（中文简繁、英语、日语、韩语、德语、法语、俄语）

## 快速开始

### 环境要求

- Python 3.11+
- Node.js 18+
- PostgreSQL 14+
- Redis 6+
- Docker（用于沙箱终端）
- Go 1.21+（仅开发 Go 插件时需要）

### 使用 Docker Compose（推荐）

```bash
# 克隆仓库
git clone https://github.com/Cass-ette/NetKitX.git
cd NetKitX

# 启动所有服务
docker compose up -d

# 访问应用
# Frontend: http://localhost:3000
# Backend API: http://localhost:8000
# API Docs: http://localhost:8000/docs
```

### 使用启动脚本

```bash
# 启动（自动处理依赖安装、数据库迁移）
./scripts/start.sh

# 停止
./scripts/stop.sh
```

### 手动启动

#### 1. 启动依赖服务

```bash
# PostgreSQL
createdb netkitx
psql netkitx -c "CREATE USER netkitx WITH PASSWORD 'netkitx';"

# Redis
redis-server
```

#### 2. 启动后端

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e .
alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

#### 3. 启动前端

```bash
cd frontend
npm install
npm run dev
```

访问 http://localhost:3000

## 核心功能

### 认证系统

- **账号密码登录** — 传统用户名密码认证
- **GitHub OAuth** — 一键 GitHub 授权登录，自动创建/关联账户
- **Passkey (WebAuthn)** — 指纹/Face ID 免密登录，在 Settings 页面管理密钥

### AI 助手

1. **配置 AI** — 访问 `/settings`，选择提供商（Claude / DeepSeek / GLM），输入 API 密钥
2. **AI 对话** — `/ai-chat` 全页面模式，或 `Cmd+Shift+I` 打开侧边面板
3. **执行模式**
   - **对话模式**：普通聊天，AI 只回答问题
   - **半自动模式**：AI 提议执行 → 用户确认 → 执行 → AI 分析结果
   - **全自动模式**：AI 自动执行插件（无需确认），最多 N 轮
   - **终端模式**：AI 可执行 shell 命令 + 插件（沙箱保护，黑名单过滤）
4. **防御/进攻模式** — 切换 AI 视角：防御建议 vs 攻击 payload
5. **任务结果分析** — 在任务详情页点击「AI 分析」按钮

### 攻防知识库

- **会话持久化** — 所有 Agent 对话自动保存，支持回放
- **知识提取** — AI 从会话中提取结构化攻防知识（技术、漏洞、工具、难度等）
- **学习报告** — AI 生成 Markdown 格式的学习报告
- **RAG 向量检索** — pgvector 存储 embedding，Agent 启动时自动注入历史经验
- **全文搜索** — PostgreSQL tsvector + GIN 索引，快速检索历史知识

### 工作流可视化

- **自动生成** — Agent 会话自动转换为 DAG 工作流（start → actions → end）
- **智能去重** — 跨 turn 相同命令/插件+参数自动去重，避免重试导致的重复节点
- **逐步回放** — 节点依次执行，实时展示进度、结果摘要
- **模拟模式** — 按 DAG 展示攻击路径 + 历史结果，不发送真实请求（适用于不可重演的攻击）
- **AI 逐步反思** — 每步执行后 AI 分析发现/意义/下一步（可选）
- **节点详情面板** — 点击节点查看参数、原因、完整结果、AI 反思（Markdown）
- **可视化状态** — running 蓝色脉冲，done 绿色，simulated 琥珀色，failed 红色

### 插件市场

1. **搜索插件** — 按名称/分类/标签搜索
2. **查看详情** — 版本、依赖、权限、安全评分
3. **安装插件** — 自动解析依赖并安装
4. **一键更新** — 检查更新、批量更新、破坏性变更警告
5. **发布插件** — 使用 CLI 工具 `python -m app.marketplace.cli publish plugin.zip`

### 网络拓扑

- 执行扫描任务后，访问 `/topology`
- 自动生成交互式网络关系图（扫描器居中，主机节点环绕）
- 支持拖拽、缩放、节点详情查看

### 报告导出

- 任务完成后，点击「导出」按钮
- 选择格式（HTML / PDF），包含任务参数、执行统计、结果表格

## 插件开发

### 社区插件仓库

社区和官方插件统一维护在独立仓库 [NetKitX-Plugins](https://github.com/Cass-ette/NetKitX-Plugins)，通过 Git submodule 集成到主项目：

```bash
# 添加社区插件（已作为 submodule 配置）
git submodule update --init --recursive

# 手动添加
git submodule add https://github.com/Cass-ette/NetKitX-Plugins.git plugins/community
```

仓库结构：
- `community/` — 经过审核的稳定插件
- `experimental/` — 实验性插件（使用需谨慎）
- `templates/` — 插件开发模板

欢迎向插件仓库提交 PR 贡献你的插件。

### 创建 Python 插件

```python
# plugins/my-plugin/main.py
from typing import Any, AsyncIterator
from app.plugins.base import PluginBase, PluginEvent

class MyPlugin(PluginBase):
    async def execute(self, params: dict[str, Any]) -> AsyncIterator[PluginEvent]:
        yield PluginEvent(type="progress", data={"percent": 0, "msg": "开始..."})
        result = await do_something(params["target"])
        yield PluginEvent(type="result", data={"target": params["target"], "result": result})
        yield PluginEvent(type="progress", data={"percent": 100, "msg": "完成"})
```

```yaml
# plugins/my-plugin/plugin.yaml
name: my-plugin
version: 1.0.0
description: 示例插件
category: utils
engine: python

params:
  - name: target
    label: 目标
    type: string
    required: true

output:
  type: table
  columns:
    - key: target
      label: 目标
    - key: result
      label: 结果
```

### 上传插件

```bash
cd plugins && zip -r my-plugin.zip my-plugin/
# 通过 Web UI 上传：访问 /plugins 页面，拖拽 zip 文件到上传区域
```

详细文档：[插件开发指南](./docs/plugin-development.md)

## 项目结构

```
NetKitX/
├── backend/              # Python FastAPI 后端
│   ├── app/
│   │   ├── api/v1/       # API 路由（auth, tools, tasks, ai, marketplace, passkey...）
│   │   ├── core/         # 核心功能（数据库、认证、配置）
│   │   ├── models/       # SQLAlchemy 模型（user, task, plugin, knowledge, passkey...）
│   │   ├── plugins/      # 插件系统（加载器、注册表、基类）
│   │   ├── marketplace/  # 插件市场（版本管理、依赖解析、安全扫描）
│   │   ├── schemas/      # Pydantic 模式
│   │   ├── services/     # 业务逻辑（AI、Agent、知识库、沙箱、报告、拓扑...）
│   │   └── templates/    # Jinja2 报告模板
│   ├── migrations/       # Alembic 数据库迁移
│   └── tests/            # 单元测试
├── frontend/             # Next.js 16 前端
│   ├── src/
│   │   ├── app/          # 页面路由（ai-chat, sessions, knowledge, marketplace, workflows...）
│   │   ├── components/   # UI 组件（ai, terminal, topology, workflow, layout...）
│   │   ├── hooks/        # 自定义 React hooks
│   │   ├── lib/          # 工具函数和状态管理
│   │   ├── i18n/         # 国际化（8 种语言 × 多个命名空间）
│   │   └── types/        # TypeScript 类型
│   └── package.json
├── plugins/              # 插件目录
│   ├── community/        # 社区插件（Git submodule → NetKitX-Plugins）
│   ├── example_ping/
│   ├── example_portscan/
│   └── sql_inject/       # SQL 注入测试插件（v2.0.0）
├── engines/              # Go 引擎
│   ├── bin/              # 编译后的二进制
│   ├── cmd/              # Go 命令入口
│   └── pkg/              # Go 包
├── scripts/              # 运维脚本
│   ├── start.sh          # 本地启动
│   ├── stop.sh           # 本地停止
│   ├── deploy.sh         # 生产环境部署
│   ├── status.sh         # 检查生产状态
│   ├── logs.sh           # 查看生产日志
│   ├── restart.sh        # 重启生产服务
│   └── backup-db.sh      # 数据库备份
├── docs/                 # 文档
├── docker-compose.yml    # 本地开发
└── docker-compose.prod.yml  # 生产部署
```

## API 文档

启动后端后访问：
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

主要端点：

| 端点 | 方法 | 描述 |
|------|------|------|
| `/api/v1/auth/register` | POST | 用户注册 |
| `/api/v1/auth/login` | POST | 用户登录 |
| `/api/v1/auth/github` | GET | GitHub OAuth 登录 |
| `/api/v1/auth/me` | GET | 获取当前用户信息 |
| `/api/v1/auth/passkey/register/begin` | POST | 开始 Passkey 注册 |
| `/api/v1/auth/passkey/login/begin` | POST | 开始 Passkey 登录 |
| `/api/v1/auth/passkey/credentials` | GET | 列出 Passkey 密钥 |
| `/api/v1/plugins` | GET | 列出所有插件 |
| `/api/v1/plugins/upload` | POST | 上传插件 zip |
| `/api/v1/tools` | GET | 列出可用工具 |
| `/api/v1/tasks` | POST | 创建任务 |
| `/api/v1/tasks/{id}` | GET | 获取任务状态 |
| `/api/v1/tasks/{id}/logs` | GET | 获取任务历史日志 |
| `/api/v1/reports/{id}/export` | GET | 导出报告（`?format=html\|pdf`） |
| `/api/v1/topology/tasks/{id}` | GET | 获取拓扑图数据 |
| `/api/v1/ai/chat` | POST | AI 对话（流式） |
| `/api/v1/ai/agent` | POST | AI 自主执行（SSE） |
| `/api/v1/ai/settings` | GET/PUT/DELETE | AI 配置管理 |
| `/api/v1/sessions` | GET | 列出 Agent 会话 |
| `/api/v1/sessions/{id}` | GET | 获取会话详情 |
| `/api/v1/sessions/{id}/extract` | POST | 提取会话知识 |
| `/api/v1/knowledge` | GET | 搜索知识库 |
| `/api/v1/marketplace/packages` | GET | 搜索插件市场 |
| `/api/v1/marketplace/install` | POST | 安装插件 |
| `/api/v1/marketplace/updates` | GET | 检查更新 |
| `/api/v1/marketplace/update-all` | POST | 批量更新 |
| `/api/v1/workflows` | GET | 列出工作流 |
| `/api/v1/workflows/{id}` | GET | 获取工作流详情 |
| `/api/v1/workflows/from-session/{id}` | POST | 从会话生成工作流 |
| `/api/v1/workflows/{id}/run` | POST | 回放/模拟工作流（SSE + AI 反思，`?simulate=true` 模拟模式） |
| `/api/v1/ws/tasks/{id}` | WS | 实时任务更新 |

## 开发

### 后端

```bash
cd backend
pip install -e ".[dev]"

# 代码格式化（必须在 check 之前）
ruff format .

# 代码检查
ruff check --fix .

# 运行测试
pytest tests/test_registry.py tests/test_version.py tests/test_reports.py tests/test_topology.py tests/test_agent.py tests/test_knowledge.py tests/test_workflows.py -v
```

### 前端

```bash
cd frontend
npm run dev     # 开发服务器
npm run build   # 构建生产版本
npm run lint    # 代码检查
```

### 数据库迁移

```bash
cd backend
alembic revision --autogenerate -m "描述"
alembic upgrade head
```

## 部署

### 生产环境配置

```bash
# backend/.env
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/netkitx
REDIS_URL=redis://host:6379/0
SECRET_KEY=<生成强密钥>
DOMAIN=yourdomain.com
GITHUB_CLIENT_ID=<your-client-id>
GITHUB_CLIENT_SECRET=<your-client-secret>
DEBUG=false
ALLOWED_ORIGINS=["https://yourdomain.com"]
```

### Docker 生产部署

```bash
# 使用部署脚本（推荐）
./scripts/deploy.sh --migrate

# 或手动部署
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml exec backend alembic upgrade head
```

### HTTPS 配置

```bash
# 安装 Certbot
apt install certbot python3-certbot-nginx

# 获取 Let's Encrypt 证书（免费）
certbot --nginx -d yourdomain.com

# 自动续期已默认启用
```

### 运维脚本

```bash
./scripts/deploy.sh             # 部署（push + pull + rebuild）
./scripts/deploy.sh --migrate   # 部署 + 数据库迁移
./scripts/status.sh             # 检查生产状态
./scripts/logs.sh backend -f    # 查看后端实时日志
./scripts/restart.sh backend    # 重启后端
./scripts/backup-db.sh          # 备份数据库
```

## CI/CD

- **CI**: GitHub Actions — ruff format/lint, pytest, ESLint, TypeScript, Trivy 安全扫描
- **Docker**: 自动构建并推送到 GitHub Container Registry
- **Release**: 版本标签自动生成 Changelog 和 GitHub Release

详见 [CI/CD 文档](./docs/ci-cd.md)

## 贡献

欢迎提交 Issue 和 Pull Request！

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feat/amazing-feature`)
3. 提交更改 (`git commit -m 'feat: add amazing feature'`)
4. 推送到分支 (`git push origin feat/amazing-feature`)
5. 创建 Pull Request

## 许可证

MIT License

## 相关链接

- [插件专用仓库（NetKitX-Plugins）](https://github.com/Cass-ette/NetKitX-Plugins)
- [架构设计文档](./docs/architecture.md)
- [插件开发指南](./docs/plugin-development.md)
- [CI/CD 配置](./docs/ci-cd.md)
- [插件市场设计](./docs/plugin-marketplace-design.md)
- [市场使用指南](./docs/marketplace-usage.md)
- [问题反馈](https://github.com/Cass-ette/NetKitX/issues)
