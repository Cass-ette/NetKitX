# NetKitX 架构设计文档

## 1. 项目概述

NetKitX 是一个可扩展的网络安全集成工具 Web 应用，支持插件化工具管理、实时任务执行和用户自定义扩展。

### 技术栈

| 层 | 技术 |
|---|------|
| 前端 | Next.js 15 + TypeScript + Shadcn/UI + Tailwind CSS |
| 后端 | Python FastAPI |
| 高性能引擎 | Go (独立二进制，subprocess 调用) |
| 数据库 | PostgreSQL (JSONB) |
| 缓存/队列 | Redis |
| 任务队列 | Celery |
| 部署 | Docker Compose |

## 2. 系统架构

```
                          ┌──────────────────────────────┐
                          │          Browser             │
                          └──────────────┬───────────────┘
                                         │
                          ┌──────────────▼───────────────┐
                          │   Next.js Frontend (3000)    │
                          │   Shadcn/UI + Tailwind       │
                          │                              │
                          │  ┌─────────┐ ┌────────────┐  │
                          │  │Dashboard│ │ Tool Pages  │  │
                          │  └─────────┘ └────────────┘  │
                          │  ┌─────────┐ ┌────────────┐  │
                          │  │Terminal │ │Config Editor│  │
                          │  │(xterm)  │ │(Monaco)     │  │
                          │  └─────────┘ └────────────┘  │
                          └──────────────┬───────────────┘
                                         │ REST + WebSocket
                          ┌──────────────▼───────────────┐
                          │  Python FastAPI (8000)        │
                          │                              │
                          │  ┌──────────────────────┐    │
                          │  │     API Gateway       │    │
                          │  │  Auth / Rate Limit    │    │
                          │  └──────────┬───────────┘    │
                          │             │                │
                          │  ┌──────────▼───────────┐    │
                          │  │   Plugin Manager      │    │
                          │  │  动态加载 / 生命周期    │    │
                          │  └──┬───────┬────────┬──┘    │
                          │     │       │        │       │
                          │  ┌──▼──┐ ┌──▼───┐ ┌──▼──┐   │
                          │  │ Py  │ │ Go   │ │ Ext │   │
                          │  │Tools│ │Engine│ │ CLI │   │
                          │  └─────┘ └──────┘ └─────┘   │
                          │             │                │
                          │  ┌──────────▼───────────┐    │
                          │  │   Task Scheduler      │    │
                          │  │   Celery + Redis      │    │
                          │  └──────────────────────┘    │
                          └──────────────┬───────────────┘
                                         │
                          ┌──────────────▼───────────────┐
                          │     PostgreSQL + Redis       │
                          └──────────────────────────────┘
```

## 3. 目录结构

```
NetKitX/
├── frontend/                  # Next.js 15 + TypeScript
│   ├── src/
│   │   ├── app/               # App Router 页面
│   │   │   ├── (auth)/        # 登录/注册
│   │   │   ├── dashboard/     # 仪表盘
│   │   │   ├── tools/         # 工具页面 (动态路由)
│   │   │   │   └── [slug]/    # /tools/portscan, /tools/subdomain ...
│   │   │   ├── tasks/         # 任务管理
│   │   │   ├── plugins/       # 插件市场/管理
│   │   │   └── settings/      # 系统设置
│   │   ├── components/
│   │   │   ├── ui/            # Shadcn/UI 基础组件
│   │   │   ├── layout/        # Shell / Sidebar / Header
│   │   │   ├── tools/         # 工具通用组件 (参数表单, 结果表格)
│   │   │   └── viz/           # 可视化 (网络图, 图表)
│   │   ├── lib/
│   │   │   ├── api.ts         # API client (fetch wrapper)
│   │   │   └── ws.ts          # WebSocket 实时推送
│   │   ├── hooks/             # 自定义 hooks
│   │   └── types/             # 全局类型定义
│   └── ...
│
├── backend/                   # Python FastAPI
│   ├── app/
│   │   ├── main.py            # FastAPI 入口
│   │   ├── api/
│   │   │   └── v1/
│   │   │       ├── auth.py
│   │   │       ├── tools.py
│   │   │       ├── tasks.py
│   │   │       └── plugins.py
│   │   ├── core/
│   │   │   ├── config.py      # 全局配置
│   │   │   ├── security.py    # JWT / RBAC
│   │   │   ├── deps.py        # 依赖注入
│   │   │   └── events.py      # WebSocket 事件
│   │   ├── models/            # SQLAlchemy ORM
│   │   ├── schemas/           # Pydantic 请求/响应模型
│   │   ├── services/          # 业务逻辑层
│   │   ├── plugins/           # 插件系统核心
│   │   │   ├── base.py        # PluginBase 抽象类
│   │   │   ├── loader.py      # 动态加载器
│   │   │   └── registry.py    # 插件注册表
│   │   └── workers/           # Celery 异步任务
│   └── ...
│
├── engines/                   # Go 高性能引擎
│   ├── cmd/
│   │   ├── portscan/          # 端口扫描
│   │   ├── subdomain/         # 子域名枚举
│   │   └── fingerprint/       # 指纹识别
│   ├── pkg/                   # 共享库
│   │   ├── output/            # 统一 JSON 输出格式
│   │   └── netutil/           # 网络工具函数
│   ├── go.mod
│   └── Makefile
│
├── plugins/                   # 用户自定义插件目录
│   └── example_plugin/
│       ├── plugin.yaml        # 插件声明
│       └── main.py            # 插件逻辑
│
├── docs/                      # 项目文档
├── docker-compose.yml
└── Makefile                   # 顶层构建/开发命令
```

## 4. 插件系统设计

插件系统是 NetKitX 扩展性的核心，用户添加新工具只需编写一个 `plugin.yaml` + 一个 Python 文件，前端自动渲染。

### 4.1 插件声明 (plugin.yaml)

```yaml
name: nmap-scanner
version: 1.0.0
description: Nmap 端口与服务扫描
category: recon          # recon | vuln | exploit | utils
author: NetKitX
engine: python           # python | go | cli

# 用户可配置的参数 → 自动生成前端表单
params:
  - name: target
    label: 目标地址
    type: string
    required: true
    placeholder: "192.168.1.0/24"
  - name: scan_type
    label: 扫描类型
    type: select
    options: ["-sS", "-sT", "-sU", "-sV"]
    default: "-sS"
  - name: ports
    label: 端口范围
    type: string
    default: "1-10000"

# 结果展示配置
output:
  type: table            # table | json | terminal | chart
  columns:
    - { key: "host", label: "主机" }
    - { key: "port", label: "端口" }
    - { key: "state", label: "状态" }
    - { key: "service", label: "服务" }
```

### 4.2 插件基类 (Python)

```python
from abc import ABC, abstractmethod
from typing import AsyncIterator
from dataclasses import dataclass

@dataclass
class PluginEvent:
    type: str   # "progress" | "result" | "error" | "log"
    data: dict

class PluginBase(ABC):
    name: str
    version: str

    @abstractmethod
    async def execute(self, params: dict) -> AsyncIterator[PluginEvent]:
        """执行插件，通过 yield 实时推送进度和结果"""
        ...
```

### 4.3 前端动态渲染

```
plugin.yaml 的 params  →  自动生成参数表单 (Shadcn Form + zod 校验)
plugin.yaml 的 output  →  自动选择结果展示组件 (Table / JSON / Chart)
```

### 4.4 Go 引擎集成

Go 模块编译为独立二进制，Python 通过 subprocess 调用：

- 输入：JSON 通过 stdin 传入
- 输出：JSON 通过 stdout 输出，每行一个 event
- 格式与 PluginEvent 一致

```
Python                          Go Binary
  │                                │
  │── stdin: {"target":"..."}  ──►│
  │                                │
  │◄── stdout: {"type":"progress","data":{...}}
  │◄── stdout: {"type":"result","data":{...}}
  │                                │
```

## 5. 数据库设计

```
┌─────────────┐     ┌─────────────────┐     ┌──────────────┐
│    users     │     │     projects    │     │   plugins    │
├─────────────┤     ├─────────────────┤     ├──────────────┤
│ id (PK)      │────<│ owner_id (FK)   │     │ id (PK)      │
│ username     │     │ id (PK)         │     │ name         │
│ email        │     │ name            │     │ version      │
│ hashed_pwd   │     │ description     │     │ category     │
│ role         │     │ created_at      │     │ config (JSON)│
│ created_at   │     │ updated_at      │     │ enabled      │
└─────────────┘     └────────┬────────┘     │ created_at   │
                             │              └──────────────┘
                    ┌────────▼────────┐
                    │     tasks       │
                    ├─────────────────┤
                    │ id (PK)         │
                    │ project_id (FK) │
                    │ plugin_name     │
                    │ status          │  pending / running / done / failed
                    │ params (JSONB)  │  ← 用户输入的参数
                    │ result (JSONB)  │  ← 扫描结果
                    │ started_at      │
                    │ finished_at     │
                    │ created_at      │
                    └─────────────────┘
```

- `params` 和 `result` 使用 PostgreSQL JSONB 类型，不同插件不同结构无需改表
- 后续可按需添加 `scan_logs`、`vulnerabilities` 等表

## 6. 数据流

```
用户点击"开始扫描"
       │
       ▼
 POST /api/v1/tasks  { plugin: "portscan", params: {...} }
       │
       ▼
 FastAPI → 验证参数 → 写入 tasks 表 (status=pending)
       │
       ▼
 Celery worker 拉取任务
       │
       ▼
 Plugin Manager 加载插件 → 执行
       │                        │
       │ (Python 插件)           │ (Go 引擎)
       │ 直接调用               │ subprocess + stdin/stdout JSON
       │                        │
       ▼                        ▼
 yield PluginEvent ──→ WebSocket 实时推送到前端
       │
       ▼
 执行完成 → 更新 tasks 表 (status=done, result=...)
```

## 7. 关键设计决策

| 决策 | 选择 | 理由 |
|------|------|------|
| 后端语言 | Python + Go 混合 | Python 管编排和插件，Go 管高性能扫描 |
| Go 集成方式 | subprocess + JSON stdio | 最简单可靠，Go 侧无需 HTTP server |
| 实时推送 | WebSocket | 扫描进度需要实时反馈 |
| 前端工具页 | 动态路由 + YAML 驱动 | 新增工具不改前端代码 |
| 认证 | JWT + RBAC | 轻量，支持多用户权限 |
| 数据存储 | PostgreSQL JSONB | 结构化 + 半结构化统一存储 |
| 部署 | Docker Compose | 一键启动所有服务 |

## 8. 迭代计划

### Phase 1: 基础骨架
- 前后端项目初始化、Docker Compose 环境
- 用户认证 (JWT)
- 插件系统核心 (加载、执行、注册)
- 一个示例插件 (端口扫描)

### Phase 2: 核心功能
- 任务管理 (创建、查看、取消)
- WebSocket 实时进度推送
- Go 引擎集成
- Dashboard 仪表盘

### Phase 3: 扩展增强
- 插件市场 / 管理页面
- 报告导出 (PDF / HTML)
- 内嵌终端 (xterm.js)
- 网络拓扑可视化
