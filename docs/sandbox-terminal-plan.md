# NetKitX 用户沙箱终端 — 实现计划

## 目标

每个登录用户拥有一个隔离的 Docker 容器作为专属终端：
- 容器内有完整 shell 环境 + 预装工具
- 预装 `netkitx` CLI，通过 API 调用后端插件
- AI terminal 模式的 shell 命令发到该容器执行
- 宿主机敏感内容完全隔离

---

## 架构

```
用户浏览器
    │
    ▼
NetKitX Backend (FastAPI)
    ├── 收到 AI agent terminal 命令
    ├── docker exec → 用户专属容器
    │       ├── Ubuntu + 安全工具
    │       ├── netkitx CLI（已登录用户 token）
    │       └── 可访问 internet + NetKitX API
    └── 返回执行结果

宿主机隔离（容器看不到）：
    ├── backend/.env
    ├── PostgreSQL / Redis
    └── 其他用户容器
```

---

## 实现步骤

### Step 1 — 沙箱基础镜像 (`netkitx-sandbox`)

**文件**: `sandbox/Dockerfile`

预装内容：
- 基础：`ubuntu:22.04`（测试环境，生产见下方说明）
- 工具：`nmap curl wget python3 pip git netcat-openbsd whois dnsutils traceroute sqlmap hydra gobuster`
- Python 库：`httpx requests`
- `netkitx` CLI（从 `/opt/NetKitX/cli/netkitx` 复制）

> **生产环境升级建议**：服务器内存 ≥ 4GB 时，建议将基础镜像切换为 `kalilinux/kali-rolling`，
> 并安装 `kali-tools-top10`，可获得完整渗透测试工具集。
> 当前测试服务器（1.8GB RAM）资源有限，暂用 Ubuntu 精简版。
>
> 切换方式（生产时）：
> ```dockerfile
> FROM kalilinux/kali-rolling
> RUN apt-get update && apt-get install -y kali-tools-top10 \
>     && rm -rf /var/lib/apt/lists/*
> ```

启动脚本：
- 接收环境变量 `NETKITX_TOKEN` + `NETKITX_API`
- 自动写入 `~/.netkitx/config.json`

**预期结果**: `docker build -t netkitx-sandbox ./sandbox` 可构建成功

---

### Step 2 — 后端：容器生命周期管理

**新文件**: `backend/app/services/container_service.py`

```python
# 核心接口
create_user_container(user_id, token, api_url) -> container_id
get_user_container(user_id) -> container_id | None
exec_in_container(container_id, command) -> {stdout, stderr, exit_code}
destroy_user_container(user_id)
cleanup_idle_containers(idle_minutes=30)  # 定时清理
```

使用 `docker` Python SDK（`docker` 包）调用 Docker daemon。

容器参数：
- 镜像：`netkitx-sandbox`
- CPU 限制：0.5 核
- 内存限制：512 MB
- 网络：可访问 internet + 宿主机 API，**不能访问** db/redis
- 无 host volume 挂载
- 自动命名：`netkitx-user-{user_id}`

---

### Step 3 — 后端：新 API 端点

**新文件**: `backend/app/api/v1/terminal.py`

```
POST   /api/v1/terminal/session    创建/获取用户容器
DELETE /api/v1/terminal/session    销毁容器
GET    /api/v1/terminal/session    查询容器状态
```

---

### Step 4 — 修改 agent_service.py

terminal 模式改为：
1. 调 `get_user_container(user_id)` 获取容器
2. 若不存在，自动调 `create_user_container()` 创建
3. 用 `exec_in_container(container_id, command)` 替代原 `execute_shell(command)`

原 `sandbox.py` 的黑名单逻辑保留，作为二次校验。

---

### Step 5 — 前端：终端会话状态

**修改**: `frontend/src/app/ai-chat/page.tsx`

terminal 模式下显示：
- 容器状态指示（运行中 / 未启动）
- "启动沙箱" / "销毁沙箱" 按钮
- 容器 ID（短）

---

### Step 6 — netkitx CLI 更新

容器启动时通过环境变量自动配置：
```bash
NETKITX_TOKEN=xxx NETKITX_API=http://156.225.20.57 netkitx ...
```

CLI 读取顺序：env var → config file

---

### Step 7 — docker-compose 更新

backend 容器需要访问 Docker daemon：
```yaml
backend:
  volumes:
    - /var/run/docker.sock:/var/run/docker.sock
  environment:
    - SANDBOX_IMAGE=netkitx-sandbox
    - SANDBOX_API_URL=http://156.225.20.57
```

先在 `docker-compose.prod.yml` 加，本地开发用 `docker-compose.yml`。

---

### Step 8 — 单元测试

**新文件**: `backend/tests/test_sandbox_container.py`

覆盖：
- 容器创建 / 销毁
- exec 命令执行
- 黑名单仍然有效
- 空闲超时清理

---

## 文件变更清单

| 文件 | 操作 |
|------|------|
| `sandbox/Dockerfile` | 新建 |
| `sandbox/entrypoint.sh` | 新建 |
| `backend/app/services/container_service.py` | 新建 |
| `backend/app/api/v1/terminal.py` | 新建 |
| `backend/app/api/v1/__init__.py` 或 main | 注册路由 |
| `backend/app/services/agent_service.py` | 修改 terminal 模式 |
| `backend/app/services/sandbox.py` | 保留，作为二次校验 |
| `backend/pyproject.toml` | 添加 `docker` 依赖 |
| `cli/netkitx` | 支持环境变量配置 |
| `docker-compose.prod.yml` | 挂载 docker.sock |
| `frontend/src/app/ai-chat/page.tsx` | 容器状态 UI |
| `backend/tests/test_sandbox_container.py` | 新建 |

---

## 安全边界

| 能做 | 不能做 |
|------|--------|
| apt install 任意工具 | 访问宿主机文件系统 |
| 调 netkitx CLI 跑插件 | 看到其他用户容器 |
| 访问 internet | 访问 db:5432 / redis:6379 |
| 安装 python 库 | 超过资源限制 |
| 全部 shell 命令 | 无限制使用资源 |

---

## 实现顺序

1. Step 1 — sandbox 镜像（可独立测试）
2. Step 7 — docker-compose 挂载 socket
3. Step 2 — container_service.py
4. Step 4 — agent_service.py 修改
5. Step 3 — terminal API
6. Step 6 — CLI 更新
7. Step 5 — 前端 UI
8. Step 8 — 测试
