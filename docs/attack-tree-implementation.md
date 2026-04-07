# 攻击树约束系统 (Attack Tree Constraint System)

## 概述

攻击树约束系统为 AI Agent 提供了基于 Cyber Kill Chain 的阶段感知引导机制，确保 Agent 的行为遵循专业的渗透测试流程，同时具备危险命令拦截能力。

## 架构总览

```
┌─────────────────────────────────────────────────────────┐
│                    agent_service.py                      │
│                   (主循环 run_agent_loop)                 │
│                                                         │
│  每轮 turn:                                              │
│  1. 重建 system prompt (phase + role)                    │
│  2. 流式获取 AI 响应                                     │
│  3. 检测 phase 关键词 → 自动推进阶段                      │
│  4. 解析 action → 执行 → 注入结果                        │
│  5. 上下文压缩 (>50K chars)                              │
│  6. RAG 重查 (每 3 轮)                                   │
│  7. 停滞检测                                             │
└──────────┬──────────────────┬───────────────────────────┘
           │                  │
           ▼                  ▼
┌──────────────────┐ ┌──────────────────┐
│ agent_prompts.py  │ │  agent_utils.py   │
│ - prompt 常量     │ │ - action 解析     │
│ - plugin catalog  │ │ - 输出压缩        │
│ - system prompt   │ │ - 错误分类        │
│   组装            │ │ - 停滞检测        │
└────────┬─────────┘ │ - 上下文压缩      │
         │           └──────────────────┘
         ▼
┌──────────────────────┐
│ attack_tree_service   │
│ - 阶段引导 prompt     │
│ - 插件推荐            │
│ - 危险命令检测        │
│ - phase-aware catalog │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ app/data/attack_tree  │
│ - KILL_CHAIN_PHASES   │
│ - ATTACK_TREE dict    │
│ - DANGEROUS_PATTERNS  │
└──────────────────────┘
```

## 核心组件

### 1. 攻击树数据 (`app/data/attack_tree.py`)

定义了 7 个 Kill Chain 阶段及其对应的插件和工具映射：

| 阶段 | 说明 | 推荐插件 | Shell 工具 |
|------|------|---------|-----------|
| `reconnaissance` | 信息收集 | port-scan, dir-scan, subdomain-enum, dns-lookup, ssl-check, http-request | curl, nmap, dig, whois, wget |
| `initial_access` | 初始入侵 | sql-inject, file-upload, brute-force, backup-scan, git-leak | curl, sqlmap, hydra, nikto |
| `execution` | 代码执行 | webshell | curl, python, php, nc |
| `persistence` | 持久化 | — | curl, wget, crontab, ssh |
| `privilege_escalation` | 权限提升 | — | sudo, find, cat, python |
| `lateral_movement` | 横向移动 | port-scan, dns-lookup | ssh, curl, nmap, scp |
| `exfiltration` | 数据窃取 | — | curl, wget, base64, cat |

全局危险命令模式（任何阶段都会拦截）：

| 模式 | 说明 |
|------|------|
| `rm -rf /` | 递归删除根目录 |
| `mkfs` | 格式化文件系统 |
| `dd if=` | 磁盘覆写 |
| `:(){:|:&};:` | Fork 炸弹 |
| `shutdown` / `reboot` / `poweroff` | 系统关机/重启 |

### 2. 攻击树服务 (`app/services/attack_tree_service.py`)

提供 5 个核心函数：

```python
get_all_phases() -> list[str]
# 返回所有阶段的有序列表

get_next_phase(current: str) -> str | None
# 返回当前阶段的下一个阶段

get_phase_info(phase: str) -> dict | None
# 获取阶段的完整信息（plugins, shell_patterns, description）

get_recommended_plugins(phase: str) -> list[str]
# 获取当前阶段的推荐插件列表

is_command_dangerous(command: str) -> tuple[bool, str]
# 检查命令是否匹配全局危险模式，返回 (是否危险, 原因)

build_phase_guidance_prompt(phase: str) -> str
# 构建当前阶段的引导 prompt，包含：
#   - 阶段名称和描述
#   - 推荐插件列表
#   - 可用 shell 工具
#   - 下一阶段提示

build_phase_catalog_for_prompt(phase: str) -> str
# 构建带阶段标注的插件目录，当前阶段推荐插件标记 [RECOMMENDED]
```

### 3. PEP 角色轮转 (`agent_prompts.py`)

Planner-Perceptor 交替机制，每轮自动切换：

| Turn | 角色 | 职责 |
|------|------|------|
| 奇数轮 | **Planner** | 分析已收集信息，确定下一步最优行动，关注全局策略 |
| 偶数轮 | **Perceptor** | 仔细观察最新结果，提取有用信号，识别异常模式 |

角色 prompt 通过 `get_agent_system_prompt()` 的 `role` 参数注入到 system prompt 末尾。

### 4. System Prompt 组装流程

每轮 turn 会重新构建 system prompt：

```
┌─────────────────────────────────────────────┐
│ 1. 基础安全 prompt (defense/offense + 语言)   │
│                                             │
│ 2. 模式指令 (semi_auto / full_auto / terminal)│
│                                             │
│ 3. 错误处理指南                               │
│                                             │
│ 4. 策略指南 (RIGHT TOOL, RECON FIRST 等)      │
│                                             │
│ 5. 阶段引导 (当前 phase 的插件推荐 + 工具列表)  │ ← attack_tree_service
│                                             │
│ 6. 阶段感知插件目录 (带 [RECOMMENDED] 标记)    │ ← attack_tree_service
│                                             │
│ 7. PEP 角色 prompt (Planner / Perceptor)     │ ← 奇偶轮切换
│                                             │
│ 8. RAG 知识上下文 (如有)                      │ ← embedding_service
└─────────────────────────────────────────────┘
```

## 运行时流程

### Agent Loop 主循环

```
用户发送消息
       │
       ▼
初始化 current_phase = "reconnaissance"
       │
       ▼
┌─── turn 1 (Planner) ───────────────────────────┐
│ 1. 重建 system prompt (phase=reconnaissance)    │
│ 2. 流式调用 AI                                   │
│ 3. 检查 AI 响应中的 phase 关键词                  │
│    → 如果出现 "initial access" 等关键词           │
│      且是下一阶段 → 推进 current_phase            │
│ 4. 解析 <action> 块                              │
│ 5. 执行 action (plugin/shell)                    │
│    → shell 命令先通过 is_command_dangerous() 检查 │
│    → 再通过 sandbox is_command_safe() 检查        │
│ 6. 注入结果到对话                                 │
│ 7. 上下文压缩检查 (>50K chars)                    │
│ 8. RAG 重查 (每 3 轮)                            │
│ 9. 停滞检测 (相似度 >70%)                         │
└─────────────────────────────────────────────────┘
       │
       ▼
┌─── turn 2 (Perceptor) ──────────────────────────┐
│ 同上，但 role=perceptor，关注观察和模式识别         │
└─────────────────────────────────────────────────┘
       │
       ▼
    ... 继续循环直到 max_turns / done / stagnation
```

### 阶段自动推进

Agent 通过关键词检测自动推进阶段：

```python
phase_keywords = {
    "initial_access": ["initial access", "gain access", "exploit", "vulnerability found"],
    "execution": ["execute", "code execution", "rce", "command execution"],
    "persistence": ["persist", "backdoor", "maintain access", "persistence"],
    "privilege_escalation": ["privilege escalation", "privesc", "escalate", "root access"],
    "lateral_movement": ["lateral movement", "pivot", "internal network", "lateral"],
    "exfiltration": ["exfiltrat", "data extraction", "steal data", "download data"],
}
```

推进条件：AI 响应中包含目标阶段关键词 **且** 该目标是当前阶段的下一阶段（`get_next_phase()` 验证）。

**这是一个软约束**：AI 不会被强制限制在某个阶段，而是通过 prompt 引导自然推进。

### 硬约束：危险命令拦截

在 `_execute_action()` 中，所有 shell 命令经过两层检查：

```
用户 shell 命令
       │
       ▼
1. is_command_dangerous()    ← attack_tree_service (全局危险模式)
   匹配 → 返回 {"error": "Command blocked: ..."}
       │
       ▼
2. is_command_safe()         ← sandbox 服务 (系统级黑名单)
   不安全 → 返回 {"error": "Command blocked: ..."}
       │
       ▼
3. 执行命令 (容器内 / 本地 sandbox)
```

### 上下文管理

| 机制 | 触发条件 | 行为 |
|------|---------|------|
| **上下文压缩** | 对话总字符 > 50,000 | 保留 system prompt + 首条用户消息 + 最近 4 条消息，中间内容压缩为摘要 |
| **RAG 重查** | 每 3 轮 | 用最近结果文本重新检索向量数据库，更新注入的 RAG 上下文 |
| **停滞检测** | 连续相似 action (相似度 >70%) | 3 次：软提醒；5 次：强制警告；7 次：终止 |

## 插件集成

每个插件的 `plugin.yaml` 中添加了 `kill_chain_phase` 字段：

```yaml
# plugins/port_scan/plugin.yaml
name: port-scan
version: "1.0.0"
kill_chain_phase: reconnaissance    # ← 新增字段
```

`PluginMeta` 数据class (`sdk/netkitx_sdk/base.py`) 已扩展：

```python
@dataclass
class PluginMeta:
    name: str
    version: str
    # ...
    kill_chain_phase: str | None = None  # ← 新增
```

加载器 (`app/plugins/loader.py`) 自动读取该字段。

## 文件清单

| 文件 | 行数 | 职责 |
|------|------|------|
| `app/data/attack_tree.py` | 75 | 攻击树数据定义 |
| `app/services/attack_tree_service.py` | 94 | 阶段引导、推荐、危险检测 |
| `app/services/agent_prompts.py` | 188 | Prompt 常量 + system prompt 组装 |
| `app/services/agent_utils.py` | 313 | Action 解析、压缩、错误分类、停滞检测 |
| `app/services/agent_service.py` | 435 | 主循环 + action 执行 |
| `sdk/netkitx_sdk/base.py` | — | PluginMeta 新增 kill_chain_phase |
| `app/plugins/loader.py` | — | 读取 kill_chain_phase |
| 14 个 `plugin.yaml` | — | 标注 kill_chain_phase |

## 配置项

```python
# app/core/config.py
AUTO_EXTRACT_KNOWLEDGE: bool = True    # 自动提取知识（会话结束后）
AUTO_EXTRACT_MIN_TURNS: int = 5        # 最少 turn 数才触发提取
```

## SSE 事件格式

Agent 模式下的 SSE 事件：

```jsonc
// Turn 开始
{"event": "turn", "data": {"turn": 1, "max_turns": 0, "role": "planner", "phase": "reconnaissance"}}

// AI 文本流
{"event": "text", "data": {"content": "让我先扫描目标..."}}

// Action 提议
{"event": "action", "data": {"action": {"type": "plugin", "plugin": "port-scan", ...}}}

// Action 执行状态
{"event": "action_status", "data": {"status": "executing", "action": {...}}}

// Action 结果
{"event": "action_result", "data": {"result": {...}, "action": {...}}}

// Action 错误
{"event": "action_error", "data": {"error": "...", "error_type": "retryable|fatal|malformed"}}

// 等待用户确认 (semi_auto)
{"event": "waiting", "data": {}}

// 结束
{"event": "done", "data": {"reason": "complete|max_turns|stagnation|error|waiting"}}
```

## 设计决策

1. **软约束优先**：阶段推进通过 prompt 引导而非硬性限制，AI 可以灵活调整策略
2. **关键词触发**：阶段推进基于 AI 输出的语义分析，而非人工手动切换
3. **双层安全**：shell 命令经过攻击树（业务层）和 sandbox（系统层）双重过滤
4. **PEP 交替**：Planner/Perceptor 角色切换避免 AI 陷入"一直执行不观察"的盲区
5. **模块化拆分**：agent_service 从单文件 957 行拆为 3 个职责单一的模块
