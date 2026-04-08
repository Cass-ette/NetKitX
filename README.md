# NetKitX

面向**合法授权安全测试**的实验性网络安全 AI Agent 平台，支持插件化工具集成、AI 自主任务执行、攻防知识积累与检索。

**在线演示**: https://wql.me

---

## 产品定位

NetKitX 定位为**面向中国市场合法化**的网络安全实验工具平台，核心能力围绕：
1. **AI Agent 自主执行** — 支持半自动、全自动、终端三种执行模式，AI 自主调用安全插件完成渗透测试任务
2. **攻防知识库** — 自动提取安全测试会话中的技术要点，生成学习报告，支持向量检索增强后续分析

> 本作品参赛类别：**软件应用与开发类 / Web 应用与开发**

---

## 核心特性

### AI Agent 自主执行
- **多执行模式**：半自动（AI 提议→用户确认→执行）、全自动（AI 自动执行插件）、终端模式（AI 可执行插件 + 沙箱 shell 命令）
- **防御/进攻双模式**：AI 可切换防御建议或精确攻击 payload，匹配不同场景需求
- **多 Provider 支持**：支持 DeepSeek、智谱 AI (GLM)、阿里通义等合规 AI 服务商，用户可独立配置各服务商密钥和模型
- **流式交互**：WebSocket / SSE 实时推送执行进度、中间结果、错误信息

### 攻防知识库
- **会话持久化**：所有 Agent 对话自动保存，支持完整回放
- **知识提取**：AI 自动从会话中提取结构化攻防知识（技术、漏洞、工具、难度、关键发现等）
- **学习报告**：AI 生成 Markdown 格式学习报告，总结思路、技巧、踩坑经验
- **向量检索**：基于 pgvector 的向量检索，自动将相关历史知识注入 Agent system prompt

### 插件化工具系统
- **双引擎支持**：Python + Go 插件，热加载无需重启
- **本地插件管理**：拖拽上传 zip、实时启用/禁用、本地插件仓库管理
- **内置插件集**：端口扫描、目录扫描、SQL 注入检测等 12+ 安全测试插件
- **插件即 Skill**：插件是 AI Agent 可调用的工具，通过 XML action block 自主调用

### 其他功能
- **报告导出**：任务结果一键导出为 HTML / PDF
- **内嵌终端**：xterm.js 实时展示执行日志，支持历史回溯
- **沙箱终端**：每用户 Docker 容器隔离，黑名单命令过滤
- **多种认证**：账号密码、GitHub OAuth、Passkey (WebAuthn) 免密登录
- **国际化**：中文简繁、英语双语支持

---

## 快速开始

### 环境要求

- Python 3.11+
- Node.js 18+
- PostgreSQL 14+（需 pgvector 扩展）
- Redis 6+
- Docker（用于沙箱终端）

### Docker Compose 一键启动

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

### 本地开发启动

```bash
# 启动后端
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e .
alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 启动前端（新终端）
cd frontend
npm install
npm run dev
```

访问 http://localhost:3000

---

## 核心功能使用流程

### 1. 配置 AI 服务商
访问 `/settings`，选择 AI 服务商（DeepSeek / GLM / 阿里通义），配置 API 密钥和模型。

### 2. 启动 AI Agent
进入 `/ai-chat`，选择执行模式：
- **半自动模式**：AI 提议执行动作，用户确认后执行，适合需要人工把控的场景
- **全自动模式**：AI 自动执行插件，最多 N 轮，适合批量任务
- **终端模式**：AI 可执行插件 + shell 命令（沙箱保护），适合复杂渗透测试

### 3. 查看会话与知识
- 所有 Agent 会话自动保存，可在 `/sessions` 查看历史、回放、生成学习报告
- 提取的攻防知识可在 `/knowledge` 搜索、查看、管理

### 4. 导出报告
任务完成后，点击「导出」按钮，选择 HTML / PDF 格式导出结果报告。

---

## 技术架构

```
NetKitX/
├── backend/              # Python FastAPI 后端
│   ├── app/
│   │   ├── api/v1/       # API 路由（auth, ai, sessions, knowledge, plugins...）
│   │   ├── models/       # SQLAlchemy 模型（user, plugin, knowledge, ai_settings...）
│   │   ├── plugins/      # 插件系统（加载器、注册表、基类）
│   │   ├── services/     # 业务逻辑（AI、Agent、知识库、Embedding、沙箱...）
│   │   └── templates/    # Jinja2 报告模板
│   └── tests/            # 单元测试
├── frontend/             # Next.js 16 + TypeScript + Tailwind
│   └── src/
│       ├── app/          # 页面路由（ai-chat, sessions, knowledge, settings...）
│       └── components/   # UI 组件（ai, terminal, layout...）
├── plugins/              # 内置插件（端口扫描、SQL注入检测等）
├── scripts/              # 启动/部署脚本
└── docs/                 # 文档
```

---

## API 端点

| 端点 | 方法 | 描述 |
|------|------|------|
| `/api/v1/auth/*` | - | 账号密码 / GitHub OAuth / Passkey 认证 |
| `/api/v1/ai/settings` | GET/PUT | AI 服务商配置（多 Provider 独立配置） |
| `/api/v1/ai/chat` | POST | AI 对话（流式） |
| `/api/v1/ai/agent` | POST | AI Agent 自主执行（SSE） |
| `/api/v1/sessions` | GET | 列出 Agent 会话历史 |
| `/api/v1/sessions/{id}/extract` | POST | 提取会话知识、生成学习报告 |
| `/api/v1/knowledge` | GET | 搜索攻防知识库 |
| `/api/v1/plugins` | GET/POST | 插件列表、本地上传 |
| `/api/v1/tasks` | GET/POST | 任务列表、创建任务 |
| `/api/v1/reports/{id}/export` | GET | 导出报告（`?format=html\|pdf`） |

完整 API 文档：http://localhost:8000/docs

---

## 开发

### 后端

```bash
cd backend
source .venv/bin/activate

# 格式化（必须在 lint 之前）
ruff format .

# 代码检查
ruff check --fix .

# 运行测试
pytest tests/test_agent.py tests/test_knowledge.py tests/test_registry.py -v
```

### 前端

```bash
cd frontend
npm run dev     # 开发服务器
npm run build   # 构建生产版本
npm run lint    # 代码检查
```

---

## 部署

### Docker 生产部署

```bash
# 使用部署脚本
./scripts/deploy.sh --migrate

# 或手动部署
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml exec backend alembic upgrade head
```

### 环境变量

```bash
# backend/.env
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/netkitx
REDIS_URL=redis://host:6379/0
RAG_ENABLED=true
SECRET_KEY=<强密钥>
DOMAIN=yourdomain.com
DEBUG=false
```

---

## 许可证

MIT License

---

## 相关链接

- [问题反馈](https://github.com/Cass-ette/NetKitX/issues)
