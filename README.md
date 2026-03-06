# NetKitX

可扩展的网络安全集成工具平台，支持插件化工具管理、实时任务执行和 Web UI 操作。

## 特性

- **插件化架构** — Python 和 Go 双引擎支持，热加载无需重启
- **Web UI 管理** — 拖拽上传插件、实时启用/禁用、一键删除
- **实时任务执行** — WebSocket 推送进度和结果，支持并发任务
- **AI 助手** — 集成 Claude/DeepSeek，支持防御/进攻模式，自主执行插件和命令（半自动/全自动/终端模式）
- **全局 AI 面板** — 侧边栏可拖拽调宽面板（`Cmd+Shift+I` 切换），任意页面快速访问 AI 对话
- **报告导出** — 任务结果一键导出为 PDF 或 HTML，包含参数、统计和结果表格
- **内嵌终端** — xterm.js 实时展示执行日志，支持历史日志回溯
- **网络拓扑可视化** — 扫描结果自动生成交互式网络关系图（React Flow + dagre 自动布局）
- **插件市场** — 发布、搜索、安装插件，内置依赖解析（PubGrub 算法）和安全扫描
- **多种输出格式** — 表格、JSON、终端、图表
- **用户认证** — JWT 认证，基于角色的权限控制
- **高性能引擎** — Go 编译的独立二进制，适合大规模扫描
- **国际化支持** — 8 种语言（中文简繁、英语、日语、韩语、德语、法语、俄语）

## 快速开始

### 环境要求

- Python 3.11+
- Node.js 18+
- PostgreSQL 14+
- Redis 6+
- Go 1.21+ (仅开发 Go 插件时需要)

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

# 查看日志
tail -f backend.log
tail -f frontend.log
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

# 创建虚拟环境并安装依赖
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e .

# 运行数据库迁移
alembic upgrade head

# 启动服务
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

#### 3. 启动前端

```bash
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

访问 http://localhost:3000

## 核心功能

### AI 助手

1. **配置 AI**
   - 访问 `/settings` 页面
   - 选择提供商（Claude / DeepSeek）
   - 输入 API 密钥和模型名称
   - 保存配置

2. **使用 AI 对话**
   - **全页面模式**：点击侧边栏「AI 对话」进入 `/ai-chat`
   - **面板模式**：点击顶栏 Bot 图标或按 `Cmd+Shift+I`（Windows: `Ctrl+Shift+I`）打开右侧面板
   - 面板可拖拽左边缘调整宽度（320-800px）

3. **AI 模式**
   - **对话模式**：普通聊天，AI 只回答问题
   - **半自动模式**：AI 提议执行插件/命令 → 用户确认 → 执行 → AI 分析结果
   - **全自动模式**：AI 自动执行插件（无需确认），最多 N 轮
   - **终端模式**：AI 可执行 shell 命令 + 插件（沙箱保护，黑名单过滤）

4. **防御/进攻模式**
   - **防御模式**：AI 提供防御建议、加固方案、安全最佳实践
   - **进攻模式**：AI 提供精确命令、payload、攻击链、下一步侦察建议

5. **任务结果 AI 分析**
   - 在任务详情页点击「AI 分析」按钮
   - AI 自动分析扫描结果并给出建议

### 插件市场

1. **搜索插件**：访问 `/marketplace`，按名称/分类/标签搜索
2. **查看详情**：点击插件卡片查看版本、依赖、权限、安全评分
3. **安装插件**：点击「安装」，系统自动解析依赖并安装
4. **发布插件**：使用 CLI 工具 `python -m app.marketplace.cli publish plugin.zip`

### 网络拓扑

- 执行扫描任务后，访问 `/topology` 或任务详情页的「拓扑图」标签
- 自动生成交互式网络关系图（扫描器居中，主机节点环绕）
- 支持拖拽、缩放、节点详情查看

### 报告导出

- 任务完成后，点击「导出」按钮
- 选择格式（HTML / PDF）
- 报告包含任务参数、执行统计、结果表格

## 插件开发

### 创建 Python 插件

```python
# plugins/my-plugin/main.py
from typing import Any, AsyncIterator
from app.plugins.base import PluginBase, PluginEvent

class MyPlugin(PluginBase):
    async def execute(self, params: dict[str, Any]) -> AsyncIterator[PluginEvent]:
        yield PluginEvent(type="progress", data={"percent": 0, "msg": "开始..."})

        # 执行任务
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
# 打包
cd plugins
zip -r my-plugin.zip my-plugin/

# 通过 Web UI 上传
# 访问 /plugins 页面，拖拽 zip 文件到上传区域
```

详细文档：[插件开发指南](./docs/plugin-development.md)

## 项目结构

```
NetKitX/
├── backend/              # Python FastAPI 后端
│   ├── app/
│   │   ├── api/v1/      # API 路由
│   │   ├── core/        # 核心功能（数据库、认证、配置）
│   │   ├── models/      # SQLAlchemy 模型
│   │   ├── plugins/     # 插件系统
│   │   ├── marketplace/ # 插件市场（版本管理、依赖解析、安全扫描）
│   │   ├── schemas/     # Pydantic 模式
│   │   ├── services/    # 业务逻辑（AI、报告导出、拓扑构建、沙箱）
│   │   └── templates/   # Jinja2 报告模板
│   └── pyproject.toml
├── frontend/            # Next.js 前端
│   ├── src/
│   │   ├── app/         # 页面路由（含 /ai-chat、/topology、/marketplace）
│   │   ├── components/  # UI 组件（含 ai、terminal、topology）
│   │   ├── hooks/       # 自定义 React hooks（含 use-ai-chat）
│   │   ├── lib/         # 工具函数（含 ai-chat-store）
│   │   ├── i18n/        # 国际化（8 种语言）
│   │   └── types/       # TypeScript 类型
│   └── package.json
├── plugins/             # 插件目录
│   ├── example_ping/
│   ├── example_portscan/
│   └── sql_inject/      # SQL 注入测试插件（v2.0.0）
├── engines/             # Go 引擎
│   ├── bin/             # 编译后的二进制
│   ├── cmd/             # Go 命令入口
│   └── pkg/             # Go 包
├── scripts/             # 启动/停止脚本
├── docs/                # 文档
│   ├── architecture.md
│   ├── plugin-development.md
│   ├── ci-cd.md
│   ├── plugin-marketplace-design.md
│   └── marketplace-usage.md
└── docker-compose.yml
```

## API 文档

启动后端后访问：
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

主要端点：

| 端点 | 方法 | 描述 |
|------|------|------|
| `/api/v1/auth/login` | POST | 用户登录 |
| `/api/v1/plugins` | GET | 列出所有插件 |
| `/api/v1/plugins/upload` | POST | 上传插件 zip |
| `/api/v1/plugins/{name}` | PATCH | 启用/禁用插件 |
| `/api/v1/plugins/{name}` | DELETE | 删除插件 |
| `/api/v1/tools` | GET | 列出可用工具（已启用插件） |
| `/api/v1/tasks` | POST | 创建任务 |
| `/api/v1/tasks/{id}` | GET | 获取任务状态 |
| `/api/v1/tasks/{id}/logs` | GET | 获取任务历史日志 |
| `/api/v1/reports/{id}/export` | GET | 导出报告（`?format=html\|pdf`） |
| `/api/v1/topology/tasks/{id}` | GET | 获取任务拓扑图数据 |
| `/api/v1/ai/chat` | POST | AI 对话（流式响应） |
| `/api/v1/ai/agent` | POST | AI 自主执行（SSE 流） |
| `/api/v1/ai/settings` | GET/POST | AI 配置管理 |
| `/api/v1/marketplace/packages` | GET | 搜索插件市场 |
| `/api/v1/marketplace/packages/{name}` | GET | 获取插件详情 |
| `/api/v1/marketplace/install` | POST | 安装插件 |
| `/api/v1/ws/tasks/{id}` | WS | 实时任务更新 |

## 开发

### 后端开发

```bash
cd backend

# 安装开发依赖
pip install -e ".[dev]"

# 运行测试（需要 PostgreSQL）
pytest tests/test_registry.py tests/test_version.py tests/test_reports.py tests/test_topology.py tests/test_agent.py -v

# 代码格式化（必须在 check 之前运行）
ruff format .

# 代码检查
ruff check --fix .

# 类型检查
mypy app
```

### 前端开发

```bash
cd frontend

# 开发服务器
npm run dev

# 构建生产版本
npm run build

# 代码检查
npm run lint
```

### 添加数据库迁移

```bash
cd backend
alembic revision --autogenerate -m "描述"
alembic upgrade head
```

## 部署

### 生产环境配置

```bash
# 后端 .env
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/netkitx
REDIS_URL=redis://host:6379/0
SECRET_KEY=<生成强密钥>
DEBUG=false

# 前端 .env.production
NEXT_PUBLIC_API_URL=https://api.yourdomain.com
```

### Docker 部署

```bash
# 构建镜像
docker compose build

# 启动服务
docker compose up -d

# 查看日志
docker compose logs -f backend
```

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

- [架构设计文档](./docs/architecture.md)
- [插件开发指南](./docs/plugin-development.md)
- [CI/CD 配置](./docs/ci-cd.md)
- [插件市场设计](./docs/plugin-marketplace-design.md)
- [市场使用指南](./docs/marketplace-usage.md)
- [问题反馈](https://github.com/Cass-ette/NetKitX/issues)
