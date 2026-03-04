# NetKitX 插件开发指南

## 概述

NetKitX 支持两种类型的插件：

1. **Python 插件** — 使用 Python 编写，适合快速开发和原型验证
2. **Go 引擎插件** — 使用 Go 编译为独立二进制，适合高性能场景（端口扫描、大规模探测等）

所有插件通过 Web UI 上传、启用/禁用、删除，无需重启服务器。

---

## 插件结构

### 基本目录结构

```
my-plugin/
├── plugin.yaml      # 插件元数据（必需）
└── main.py          # Python 插件入口（Python 插件必需）
```

### plugin.yaml 格式

```yaml
name: my-plugin              # 插件唯一标识（kebab-case）
version: 1.0.0               # 语义化版本号
description: 插件功能描述     # 简短描述
category: recon              # 分类：recon | vuln | exploit | utils
engine: python               # 引擎类型：python | go | cli

# 参数定义
params:
  - name: target             # 参数名
    label: 目标地址          # 显示标签
    type: string             # 类型：string | number | select | boolean
    required: true           # 是否必填
    placeholder: "192.168.1.1"  # 占位符
  - name: timeout
    label: 超时时间（秒）
    type: number
    default: 30

# 输出格式定义
output:
  type: table                # 输出类型：table | json | terminal | chart
  columns:                   # 表格列定义（type=table 时）
    - key: host
      label: 主机
    - key: status
      label: 状态
```

---

## Python 插件开发

### 1. 创建插件类

```python
from typing import Any, AsyncIterator
from app.plugins.base import PluginBase, PluginEvent, PluginMeta


class MyPlugin(PluginBase):
    meta = PluginMeta(
        name="my-plugin",
        version="1.0.0",
        description="示例插件",
        category="utils",
        engine="python",
    )

    async def execute(self, params: dict[str, Any]) -> AsyncIterator[PluginEvent]:
        """
        插件执行入口。

        Args:
            params: 用户输入的参数字典

        Yields:
            PluginEvent: 进度更新、结果数据、错误信息
        """
        target = params["target"]
        timeout = params.get("timeout", 30)

        # 发送进度更新
        yield PluginEvent(
            type="progress",
            data={"percent": 0, "msg": "开始扫描..."}
        )

        # 执行任务逻辑
        result = await self._do_scan(target, timeout)

        # 发送结果数据
        yield PluginEvent(
            type="result",
            data={"host": target, "status": result}
        )

        # 完成
        yield PluginEvent(
            type="progress",
            data={"percent": 100, "msg": "扫描完成"}
        )

    async def _do_scan(self, target: str, timeout: int):
        # 实现扫描逻辑
        import asyncio
        await asyncio.sleep(1)
        return "online"
```

### 2. PluginEvent 类型

| type | 用途 | data 字段 |
|------|------|-----------|
| `progress` | 进度更新 | `percent` (0-100), `msg` (描述) |
| `result` | 结果数据 | 任意 JSON 对象（匹配 output 定义） |
| `error` | 错误信息 | `error` (错误描述) |
| `log` | 日志输出 | `msg` (日志内容) |

### 3. 参数验证（可选）

```python
async def validate_params(self, params: dict[str, Any]) -> dict[str, Any]:
    """自定义参数验证"""
    if "target" not in params:
        raise ValueError("缺少 target 参数")

    # 规范化参数
    params["target"] = params["target"].strip()
    return params
```

### 4. 资源清理（可选）

```python
async def cleanup(self) -> None:
    """插件执行后的清理工作"""
    # 关闭连接、删除临时文件等
    pass
```

---

## Go 引擎插件开发

### 1. 创建 Go 程序

```go
package main

import (
    "encoding/json"
    "fmt"
    "os"
)

type Params struct {
    Target  string `json:"target"`
    Timeout int    `json:"timeout"`
}

type Event struct {
    Type string                 `json:"type"`
    Data map[string]interface{} `json:"data"`
}

func main() {
    // 从 stdin 读取参数
    var params Params
    if err := json.NewDecoder(os.Stdin).Decode(&params); err != nil {
        emitError(err.Error())
        os.Exit(1)
    }

    // 发送进度
    emitProgress(0, "开始扫描...")

    // 执行扫描
    result := scan(params.Target, params.Timeout)

    // 发送结果
    emitResult(map[string]interface{}{
        "host":   params.Target,
        "status": result,
    })

    emitProgress(100, "完成")
}

func emitProgress(percent int, msg string) {
    emit("progress", map[string]interface{}{
        "percent": percent,
        "msg":     msg,
    })
}

func emitResult(data map[string]interface{}) {
    emit("result", data)
}

func emitError(msg string) {
    emit("error", map[string]interface{}{"error": msg})
}

func emit(eventType string, data map[string]interface{}) {
    event := Event{Type: eventType, Data: data}
    json.NewEncoder(os.Stdout).Encode(event)
}

func scan(target string, timeout int) string {
    // 实现扫描逻辑
    return "online"
}
```

### 2. 编译二进制

```bash
# 编译为独立二进制
go build -o engines/bin/my-plugin main.go

# 跨平台编译
GOOS=linux GOARCH=amd64 go build -o engines/bin/my-plugin-linux main.go
```

### 3. plugin.yaml 配置

```yaml
name: my-plugin
version: 1.0.0
description: Go 引擎插件示例
category: recon
engine: go
binary: engines/bin/my-plugin  # 二进制路径（相对项目根目录）

params:
  - name: target
    label: 目标地址
    type: string
    required: true

output:
  type: table
  columns:
    - key: host
      label: 主机
    - key: status
      label: 状态
```

---

## 插件上传与管理

### 1. 打包插件

```bash
# 从 plugins/ 目录打包（推荐）
cd plugins
zip -r my-plugin.zip my-plugin/

# 或从项目根目录打包
zip -r my-plugin.zip plugins/my-plugin/
```

**注意**：
- 系统会自动跳过 `__pycache__`、`.git`、`.mypy_cache`、`.ruff_cache` 目录
- 只允许 `.py`、`.yaml`、`.yml`、`.json`、`.txt` 文件
- 压缩包大小限制 10 MB，解压后限制 50 MB

### 2. 通过 Web UI 上传

1. 访问 `/plugins` 页面
2. 拖拽 `.zip` 文件到上传区域，或点击选择文件
3. 上传成功后插件立即可用，无需重启

### 3. 启用/禁用插件

- 在插件卡片上切换开关
- 禁用的插件不会出现在工具列表中，但保留在系统中

### 4. 删除插件

- 点击删除按钮并确认
- 插件目录和注册信息会被完全移除

---

## 示例插件

### 示例 1：Ping 扫描（Python）

参考 `plugins/example_ping/`：

```python
import asyncio
import platform
from typing import Any, AsyncIterator
from app.plugins.base import PluginBase, PluginEvent


class PingSweep(PluginBase):
    async def execute(self, params: dict[str, Any]) -> AsyncIterator[PluginEvent]:
        targets = [t.strip() for t in params["targets"].split(",")]
        count = params.get("count", 3)
        total = len(targets)

        yield PluginEvent(type="progress", data={"percent": 0, "msg": f"Pinging {total} hosts..."})

        for i, host in enumerate(targets):
            alive, latency = await self._ping(host, count)
            yield PluginEvent(
                type="result",
                data={"host": host, "alive": alive, "latency_ms": latency},
            )
            pct = (i + 1) * 100 // total
            yield PluginEvent(type="progress", data={"percent": pct, "msg": f"Pinged {i+1}/{total}"})

        yield PluginEvent(type="progress", data={"percent": 100, "msg": "Ping sweep complete"})

    async def _ping(self, host: str, count: int) -> tuple[bool, float | None]:
        flag = "-n" if platform.system().lower() == "windows" else "-c"
        try:
            proc = await asyncio.create_subprocess_exec(
                "ping", flag, str(count), "-W", "2", host,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10)
            if proc.returncode == 0:
                return True, None
            return False, None
        except (asyncio.TimeoutError, OSError):
            return False, None
```

### 示例 2：端口扫描（Go）

参考 `plugins/example_portscan/` 和 `engines/cmd/portscan/`。

---

## 最佳实践

### 1. 错误处理

```python
try:
    result = await risky_operation()
    yield PluginEvent(type="result", data=result)
except Exception as e:
    yield PluginEvent(type="error", data={"error": str(e)})
```

### 2. 进度反馈

- 对于长时间运行的任务，定期发送 `progress` 事件
- `percent` 应该单调递增（0 → 100）
- 提供有意义的 `msg` 描述当前阶段

### 3. 批量处理

```python
for i, item in enumerate(items):
    result = await process(item)
    yield PluginEvent(type="result", data=result)

    # 每 10 个更新一次进度
    if (i + 1) % 10 == 0:
        pct = (i + 1) * 100 // len(items)
        yield PluginEvent(type="progress", data={"percent": pct, "msg": f"Processed {i+1}/{len(items)}"})
```

### 4. 超时控制

```python
import asyncio

async def execute(self, params):
    timeout = params.get("timeout", 300)
    try:
        async with asyncio.timeout(timeout):
            # 执行任务
            pass
    except asyncio.TimeoutError:
        yield PluginEvent(type="error", data={"error": "Task timeout"})
```

### 5. 资源限制

- 避免无限循环或递归
- 限制内存使用（大数据集分批处理）
- 使用 `asyncio.Semaphore` 控制并发数

---

## 调试技巧

### 1. 本地测试

```bash
# 启动后端
cd backend
.venv/bin/uvicorn app.main:app --reload

# 查看日志
tail -f logs/app.log
```

### 2. 手动加载插件

```python
from pathlib import Path
from app.plugins.loader import load_single_plugin

plugin_dir = Path("plugins/my-plugin")
success = load_single_plugin(plugin_dir)
print(f"Loaded: {success}")
```

### 3. 测试插件执行

```python
import asyncio
from app.plugins.registry import registry

async def test():
    plugin = registry.get("my-plugin")
    params = {"target": "127.0.0.1", "timeout": 10}

    async for event in plugin.execute(params):
        print(f"{event.type}: {event.data}")

asyncio.run(test())
```

---

## 常见问题

### Q: 插件上传失败，提示 "Disallowed file type"

A: 检查 zip 包中是否包含不允许的文件类型（如 `.pyc`、`.so`）。系统会自动跳过 `__pycache__` 目录，但其他二进制文件需要手动排除。

### Q: Go 插件找不到二进制文件

A: 确保 `plugin.yaml` 中的 `binary` 路径相对于项目根目录，且文件有执行权限（`chmod +x`）。

### Q: 插件执行卡住不返回

A: 检查是否忘记 `yield` 最终的 `progress` 事件（`percent: 100`），或者任务中有阻塞操作未使用 `await`。

### Q: 如何在插件间共享数据？

A: 插件应该是无状态的。如需共享数据，使用 Redis 或数据库，通过 `app.core.database` 或 `app.core.cache` 访问。

---

## 参考资料

- [架构设计文档](./architecture.md)
- [API 文档](./api.md)
- [示例插件源码](../plugins/)
