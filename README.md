# NetKitX

可扩展的网络安全集成工具平台，支持插件化工具管理、实时任务执行和 Web UI 操作。

## 特性

- **插件化架构** — Python 和 Go 双引擎支持，热加载无需重启
- **Web UI 管理** — 拖拽上传插件、实时启用/禁用、一键删除
- **实时任务执行** — WebSocket 推送进度和结果，支持并发任务
- **多种输出格式** — 表格、JSON、终端、图表
- **用户认证** — JWT 认证，基于角色的权限控制
- **高性能引擎** — Go 编译的独立二进制，适合大规模扫描

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
│   │   ├── schemas/     # Pydantic 模式
│   │   └── services/    # 业务逻辑
│   └── pyproject.toml
├── frontend/            # Next.js 前端
│   ├── src/
│   │   ├── app/         # 页面路由
│   │   ├── components/  # UI 组件
│   │   ├── lib/         # 工具函数
│   │   └── types/       # TypeScript 类型
│   └── package.json
├── plugins/             # 插件目录
│   ├── example_ping/
│   └── example_portscan/
├── engines/             # Go 引擎
│   ├── bin/             # 编译后的二进制
│   ├── cmd/             # Go 命令入口
│   └── pkg/             # Go 包
├── docs/                # 文档
│   ├── architecture.md
│   └── plugin-development.md
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
| `/api/v1/ws/tasks/{id}` | WS | 实时任务更新 |

## 开发

### 后端开发

```bash
cd backend

# 安装开发依赖
pip install -e ".[dev]"

# 运行测试
pytest

# 代码格式化
ruff format .

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
- [问题反馈](https://github.com/Cass-ette/NetKitX/issues)
