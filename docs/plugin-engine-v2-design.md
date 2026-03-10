# Plugin Engine 2.0 设计方案

## 目标

打造一个**渐进式插件引擎**,让插件可以:
- ✅ **简单场景**: 5 分钟写一个单次执行的工具(保持现有体验)
- ✅ **中等场景**: 支持多步骤交互、状态保持、会话管理
- ✅ **复杂场景**: 自定义 UI、实时双向通信、插件编排、工作流
- ✅ **极限场景**: 插件即服务(Plugin as a Service),长期运行的守护进程

## 核心理念

### 1. 渐进式增强 (Progressive Enhancement)

```python
# Level 0: 最简单 - 单次执行(现有模式)
class SimplePlugin(PluginBase):
    async def execute(self, params):
        yield PluginEvent(type="result", data={...})

# Level 1: 会话模式 - 多次交互
class SessionPlugin(PluginBase):
    mode = "session"  # 声明为会话模式

    async def on_session_start(self, params):
        return {"session_id": "xxx", "state": {}}

    async def on_message(self, session_id, message):
        # 接收用户消息,返回响应
        yield PluginEvent(...)

# Level 2: UI 模式 - 自定义前端
class UIPlugin(PluginBase):
    mode = "ui"
    ui_component = "webshell-terminal"  # 前端组件名

    async def on_ui_action(self, action, data):
        # 处理前端交互
        yield PluginEvent(...)

# Level 3: 服务模式 - 长期运行
class ServicePlugin(PluginBase):
    mode = "service"

    async def on_start(self):
        # 插件启动时执行
        self.server = await self._start_server()

    async def on_stop(self):
        # 插件停止时执行
        await self.server.close()
```

### 2. 统一的通信协议

所有模式都使用同一套事件系统:

```typescript
// 前端 → 后端
{
  type: "execute" | "message" | "action" | "cancel",
  plugin: "webshell",
  session_id?: "xxx",
  data: {...}
}

// 后端 → 前端
{
  type: "progress" | "result" | "log" | "error" | "ui_update" | "request_input",
  data: {...}
}
```

### 3. 插件能力矩阵

| 能力 | Level 0<br>单次执行 | Level 1<br>会话模式 | Level 2<br>UI 模式 | Level 3<br>服务模式 |
|------|---------------------|---------------------|-------------------|---------------------|
| 执行时间 | 一次性 | 多次交互 | 持续连接 | 长期运行 |
| 状态保持 | ❌ | ✅ Redis | ✅ 内存 | ✅ 内存+持久化 |
| 用户输入 | 表单参数 | 消息交互 | UI 事件 | API 调用 |
| 前端 UI | 固定表格 | 固定表格 | 自定义组件 | 自定义页面 |
| 生命周期 | execute() | start/message/end | start/action/end | start/stop/restart |
| 资源占用 | 低 | 中 | 中 | 高 |
| 适用场景 | 扫描器、信息收集 | WebShell、数据库客户端 | 可视化工具、监控面板 | 代理服务器、持续监控 |

---

## 架构设计

### 1. 插件生命周期管理器

```python
# backend/app/plugins/lifecycle.py

class PluginLifecycleManager:
    """插件生命周期管理器"""

    def __init__(self):
        self.sessions: dict[str, PluginSession] = {}
        self.services: dict[str, PluginService] = {}

    async def execute_once(self, plugin: PluginBase, params: dict):
        """Level 0: 单次执行"""
        async for event in plugin.execute(params):
            yield event

    async def create_session(self, plugin: PluginBase, params: dict) -> str:
        """Level 1: 创建会话"""
        session_id = str(uuid.uuid4())
        session = PluginSession(
            id=session_id,
            plugin=plugin,
            state=await plugin.on_session_start(params),
            created_at=datetime.utcnow(),
        )
        self.sessions[session_id] = session
        return session_id

    async def send_message(self, session_id: str, message: dict):
        """Level 1: 发送消息到会话"""
        session = self.sessions.get(session_id)
        if not session:
            raise ValueError("Session not found")

        async for event in session.plugin.on_message(session_id, message):
            yield event

    async def start_service(self, plugin: PluginBase, config: dict):
        """Level 3: 启动服务"""
        service_id = str(uuid.uuid4())
        service = PluginService(
            id=service_id,
            plugin=plugin,
            config=config,
        )
        await plugin.on_start()
        self.services[service_id] = service
        return service_id
```

### 2. 会话存储

```python
# backend/app/plugins/session.py

class PluginSession:
    """插件会话"""

    def __init__(self, id: str, plugin: PluginBase, state: dict, created_at: datetime):
        self.id = id
        self.plugin = plugin
        self.state = state  # 会话状态
        self.created_at = created_at
        self.last_activity = datetime.utcnow()
        self.messages: list[dict] = []  # 消息历史

    async def send_message(self, message: dict):
        """发送消息"""
        self.messages.append({
            "timestamp": datetime.utcnow(),
            "direction": "user",
            "data": message,
        })
        self.last_activity = datetime.utcnow()

        async for event in self.plugin.on_message(self.id, message):
            self.messages.append({
                "timestamp": datetime.utcnow(),
                "direction": "plugin",
                "data": event.data,
            })
            yield event

    async def save_to_redis(self, redis):
        """持久化到 Redis"""
        await redis.setex(
            f"plugin:session:{self.id}",
            3600,  # 1 小时过期
            json.dumps({
                "plugin": self.plugin.meta.name,
                "state": self.state,
                "messages": self.messages[-100:],  # 只保留最近 100 条
            })
        )
```

### 3. WebSocket 双向通信

```python
# backend/app/api/v1/plugins_ws.py

@router.websocket("/ws/plugins/{plugin_name}/session/{session_id}")
async def plugin_session_ws(
    websocket: WebSocket,
    plugin_name: str,
    session_id: str,
):
    """插件会话 WebSocket 端点"""
    await websocket.accept()

    session = lifecycle_manager.sessions.get(session_id)
    if not session:
        await websocket.send_json({"type": "error", "data": {"error": "Session not found"}})
        await websocket.close()
        return

    try:
        while True:
            # 接收用户消息
            message = await websocket.receive_json()

            # 发送给插件处理
            async for event in session.send_message(message):
                await websocket.send_json({
                    "type": event.type,
                    "data": event.data,
                })

    except WebSocketDisconnect:
        # 会话保持,等待重连
        pass
```

### 4. 前端自定义 UI 组件

```typescript
// frontend/src/components/plugins/registry.tsx

// 插件 UI 组件注册表
export const PluginUIRegistry = {
  // 默认 UI: 表格
  "default": DefaultTableUI,

  // 自定义 UI 组件
  "webshell-terminal": WebShellTerminalUI,
  "network-graph": NetworkGraphUI,
  "dashboard": DashboardUI,
};

// 动态加载插件 UI
export function PluginUI({ plugin, sessionId }: Props) {
  const Component = PluginUIRegistry[plugin.ui_component || "default"];
  return <Component plugin={plugin} sessionId={sessionId} />;
}
```

```typescript
// frontend/src/components/plugins/webshell-terminal.tsx

export function WebShellTerminalUI({ plugin, sessionId }: Props) {
  const [ws, setWs] = useState<WebSocket | null>(null);
  const [history, setHistory] = useState<Message[]>([]);

  useEffect(() => {
    // 连接 WebSocket
    const socket = new WebSocket(
      `wss://wql.me/api/v1/ws/plugins/${plugin.name}/session/${sessionId}`
    );

    socket.onmessage = (event) => {
      const msg = JSON.parse(event.data);
      setHistory(prev => [...prev, msg]);
    };

    setWs(socket);
    return () => socket.close();
  }, [sessionId]);

  const sendCommand = (command: string) => {
    ws?.send(JSON.stringify({
      type: "command",
      data: { command }
    }));
  };

  return (
    <div className="terminal">
      <Terminal
        history={history}
        onCommand={sendCommand}
      />
    </div>
  );
}
```

### 5. 插件编排引擎

```python
# backend/app/plugins/workflow.py

class PluginWorkflow:
    """插件工作流"""

    def __init__(self, definition: dict):
        self.nodes = definition["nodes"]  # 节点列表
        self.edges = definition["edges"]  # 连接关系

    async def execute(self, initial_params: dict):
        """执行工作流"""
        context = {"params": initial_params, "results": {}}

        # 拓扑排序,按依赖顺序执行
        for node in self._topological_sort():
            plugin = registry.get(node["plugin"])

            # 从上游节点获取输入
            params = self._build_params(node, context)

            # 执行插件
            results = []
            async for event in plugin.execute(params):
                if event.type == "result":
                    results.append(event.data)
                yield event

            # 保存结果供下游使用
            context["results"][node["id"]] = results

        yield PluginEvent(type="workflow_complete", data=context["results"])
```

```yaml
# 工作流定义示例
workflow:
  name: "端口扫描 + 漏洞检测"
  nodes:
    - id: "scan"
      plugin: "port-scan"
      params:
        target: "{{input.target}}"

    - id: "vuln_check"
      plugin: "vuln-scanner"
      params:
        target: "{{input.target}}"
        ports: "{{scan.results.open_ports}}"  # 使用上游结果

  edges:
    - from: "scan"
      to: "vuln_check"
```

---

## 实现计划

### Phase 1: 会话模式 (2-3 天)

**目标**: 支持多次交互的插件

**任务**:
- [ ] 实现 `PluginLifecycleManager`
- [ ] 实现 `PluginSession` 和 Redis 持久化
- [ ] 添加 WebSocket 端点 `/ws/plugins/{name}/session/{id}`
- [ ] 扩展 `PluginBase` 支持 `on_session_start()` 和 `on_message()`
- [ ] 前端添加会话管理 UI
- [ ] 改造 WebShell 插件为会话模式

**验收标准**:
- WebShell 插件可以保持会话,连续执行多个命令
- 刷新页面后会话不丢失
- 支持多个并发会话

### Phase 2: 自定义 UI (3-4 天)

**目标**: 插件可以自定义前端界面

**任务**:
- [ ] 创建插件 UI 组件注册表
- [ ] 实现 `WebShellTerminalUI` 组件(xterm.js)
- [ ] 实现 `NetworkGraphUI` 组件(React Flow)
- [ ] 实现 `DashboardUI` 组件(echarts)
- [ ] 插件 manifest 支持 `ui_component` 字段
- [ ] 动态加载插件 UI 组件

**验收标准**:
- WebShell 插件有类似蚁剑的终端界面
- 网络拓扑插件有交互式图形界面
- 监控插件有实时更新的仪表盘

### Phase 3: 插件编排 (4-5 天)

**目标**: 插件可以组合成工作流

**任务**:
- [ ] 实现 `PluginWorkflow` 引擎
- [ ] 实现工作流 YAML 解析器
- [ ] 实现节点间数据传递(模板语法 `{{node.result}}`)
- [ ] 前端可视化工作流编辑器(React Flow)
- [ ] 工作流执行进度可视化
- [ ] 工作流保存和分享

**验收标准**:
- 可以创建"端口扫描 → 漏洞检测 → 报告生成"工作流
- 可以在 UI 上拖拽节点创建工作流
- 工作流可以保存为模板复用

### Phase 4: 服务模式 (5-7 天)

**目标**: 插件可以长期运行

**任务**:
- [ ] 实现 `PluginService` 管理器
- [ ] 插件支持 `on_start()` 和 `on_stop()` 生命周期
- [ ] 服务健康检查和自动重启
- [ ] 服务日志收集和查看
- [ ] 服务资源监控(CPU/内存)
- [ ] 前端服务管理页面

**验收标准**:
- 可以启动一个 HTTP 代理插件,持续运行
- 可以启动一个端口监听插件,实时告警
- 服务崩溃后自动重启
- 可以查看服务日志和资源占用

### Phase 5: 高级特性 (按需实现)

- [ ] 插件热更新(不重启服务)
- [ ] 插件权限控制(沙箱、白名单)
- [ ] 插件市场 2.0(支持 UI 组件、工作流模板)
- [ ] 插件调试工具(断点、日志、性能分析)
- [ ] 插件测试框架
- [ ] 插件文档生成器

---

## 技术选型

### 后端

| 组件 | 技术 | 理由 |
|------|------|------|
| 会话存储 | Redis | 快速、支持过期、分布式 |
| 消息队列 | Redis Streams | 轻量、与 Redis 集成 |
| 工作流引擎 | 自研 | 简单场景,无需 Airflow/Temporal |
| WebSocket | FastAPI WebSocket | 原生支持,性能好 |

### 前端

| 组件 | 技术 | 理由 |
|------|------|------|
| 终端 UI | xterm.js | 成熟、功能完整 |
| 图形编辑器 | React Flow | 可视化工作流 |
| 图表 | echarts | 功能强大、中文友好 |
| 状态管理 | Zustand | 轻量、简单 |

---

## 示例:WebShell 插件 2.0

### 插件定义

```yaml
# plugins/webshell/plugin.yaml
name: webshell
version: 2.0.0
mode: session  # 声明为会话模式
ui_component: webshell-terminal  # 使用自定义 UI

params:
  - name: url
    label: WebShell URL
    type: string
    required: true
  - name: password
    label: 连接密码
    type: string
    required: true
  - name: shell_type
    label: Shell 类型
    type: select
    options: ["php_eval", "php_assert", "asp_eval"]
```

### 插件实现

```python
# plugins/webshell/main.py

class WebShellPlugin(PluginBase):
    mode = "session"

    async def on_session_start(self, params: dict) -> dict:
        """会话启动"""
        url = params["url"]
        password = params["password"]
        shell_type = params["shell_type"]

        # 测试连接
        if await self._test_connection(url, password, shell_type):
            return {
                "url": url,
                "password": password,
                "shell_type": shell_type,
                "cwd": "/",  # 当前工作目录
                "connected": True,
            }
        else:
            raise ValueError("连接失败")

    async def on_message(self, session_id: str, message: dict):
        """处理用户消息"""
        session = await self._get_session(session_id)
        command = message.get("command", "").strip()

        if not command:
            return

        # 处理内置命令
        if command.startswith("cd "):
            path = command[3:].strip()
            session["cwd"] = await self._change_directory(session, path)
            yield PluginEvent(type="log", data={"msg": f"Changed directory to {session['cwd']}"})
            return

        # 执行系统命令
        yield PluginEvent(type="progress", data={"percent": 50, "msg": f"Executing: {command}"})

        output = await self._exec_command(session, command)

        yield PluginEvent(type="result", data={
            "command": command,
            "output": output,
            "cwd": session["cwd"],
        })
```

### 前端 UI

```typescript
// frontend/src/components/plugins/webshell-terminal.tsx

export function WebShellTerminalUI({ sessionId }: Props) {
  const [terminal, setTerminal] = useState<Terminal | null>(null);
  const [ws, setWs] = useState<WebSocket | null>(null);

  useEffect(() => {
    // 初始化 xterm.js
    const term = new Terminal({
      theme: { background: '#1e1e1e' },
      fontSize: 14,
      fontFamily: 'Menlo, Monaco, monospace',
    });
    term.open(document.getElementById('terminal')!);
    setTerminal(term);

    // 连接 WebSocket
    const socket = new WebSocket(`wss://wql.me/api/v1/ws/plugins/webshell/session/${sessionId}`);

    socket.onmessage = (event) => {
      const msg = JSON.parse(event.data);
      if (msg.type === "result") {
        term.writeln(msg.data.output);
        term.write(`${msg.data.cwd}$ `);
      }
    };

    setWs(socket);

    // 监听用户输入
    let currentLine = '';
    term.onData((data) => {
      if (data === '\r') {  // Enter
        term.writeln('');
        socket.send(JSON.stringify({
          type: "command",
          data: { command: currentLine }
        }));
        currentLine = '';
      } else if (data === '\u007F') {  // Backspace
        if (currentLine.length > 0) {
          currentLine = currentLine.slice(0, -1);
          term.write('\b \b');
        }
      } else {
        currentLine += data;
        term.write(data);
      }
    });

    return () => {
      term.dispose();
      socket.close();
    };
  }, [sessionId]);

  return <div id="terminal" className="h-full w-full" />;
}
```

---

## 兼容性

### 向后兼容

所有现有插件(Level 0)无需修改,继续正常工作:

```python
# 现有插件
class OldPlugin(PluginBase):
    async def execute(self, params):
        yield PluginEvent(...)

# 自动识别为 Level 0,使用单次执行模式
```

### 渐进式迁移

插件可以逐步升级:

```python
# Step 1: 添加 mode 声明
class MyPlugin(PluginBase):
    mode = "session"  # 升级到 Level 1

# Step 2: 实现会话方法
async def on_session_start(self, params):
    return {"state": {}}

async def on_message(self, session_id, message):
    yield PluginEvent(...)

# Step 3: 添加自定义 UI
ui_component = "my-custom-ui"
```

---

## 风险评估

### 技术风险

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| WebSocket 连接不稳定 | 会话中断 | 自动重连 + 消息队列 |
| Redis 单点故障 | 会话丢失 | Redis 集群 + 持久化 |
| 插件内存泄漏 | 服务崩溃 | 资源监控 + 自动重启 |
| 恶意插件攻击 | 系统被破坏 | 沙箱隔离 + 权限控制 |

### 性能风险

| 场景 | 瓶颈 | 优化方案 |
|------|------|----------|
| 1000+ 并发会话 | 内存占用 | 会话过期 + LRU 淘汰 |
| 大量 WebSocket 连接 | CPU 占用 | 连接池 + 负载均衡 |
| 工作流嵌套过深 | 执行超时 | 深度限制 + 超时控制 |

---

## 成功指标

### Phase 1 (会话模式)
- ✅ WebShell 插件可以连续执行 100 个命令不断开
- ✅ 支持 50 个并发会话
- ✅ 会话恢复成功率 > 95%

### Phase 2 (自定义 UI)
- ✅ WebShell 终端体验接近蚁剑
- ✅ 网络拓扑可视化支持 1000+ 节点
- ✅ 仪表盘刷新延迟 < 100ms

### Phase 3 (插件编排)
- ✅ 可以创建 10+ 节点的复杂工作流
- ✅ 工作流执行成功率 > 90%
- ✅ 工作流可视化编辑器易用性评分 > 4/5

### Phase 4 (服务模式)
- ✅ 服务可以稳定运行 7 天不重启
- ✅ 服务崩溃后 5 秒内自动恢复
- ✅ 资源占用监控准确率 > 95%

---

## 下一步

1. **Review 设计方案** - 团队讨论,收集反馈
2. **创建 POC** - 实现 Phase 1 的最小可行版本
3. **性能测试** - 压测会话模式的并发能力
4. **用户测试** - 邀请用户试用 WebShell 2.0
5. **迭代优化** - 根据反馈调整设计

---

## 参考资料

- [Metasploit Framework Architecture](https://github.com/rapid7/metasploit-framework/wiki/Architecture)
- [Burp Suite Extension API](https://portswigger.net/burp/extender/api/)
- [n8n Workflow Automation](https://docs.n8n.io/workflows/)
- [VS Code Extension API](https://code.visualstudio.com/api)
- [Chrome Extension Architecture](https://developer.chrome.com/docs/extensions/mv3/architecture-overview/)
