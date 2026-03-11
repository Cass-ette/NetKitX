# NetKitX 开发路线图

**更新时间**: 2024-03-10

## 当前状态

### ✅ 已完成功能

- [x] 核心插件系统 (加载、注册、执行)
- [x] 插件市场 (7 个阶段全部完成)
  - [x] Phase 1: 基础设施
  - [x] Phase 2: 依赖解析 (PubGrub)
  - [x] Phase 3: 安装器
  - [x] Phase 4: 前端 UI
  - [x] Phase 5: 发布系统
  - [x] Phase 6: 安全扫描
  - [x] Phase 7: 更新系统
- [x] AI 功能
  - [x] AI 分析 (右侧抽屉)
  - [x] AI 聊天页面
  - [x] 攻防模式切换
  - [x] 多语言支持
- [x] AI Agent 自主执行
  - [x] Mode A: 半自动 (用户确认)
  - [x] Mode B: 全自动 (插件执行)
  - [x] Mode C: 终端模式 (Shell 命令)
  - [x] 自我纠错机制
- [x] 知识库系统
  - [x] Phase 1: 会话持久化
  - [x] Phase 2: 知识提取 + 学习报告
  - [x] Phase 3: RAG 向量检索增强
- [x] 插件引擎 2.0 Phase 1: 会话模式
  - [x] SessionPlugin 基类 + SDK
  - [x] Redis 会话状态管理
  - [x] WebSocket 双向通信
  - [x] WebShell 2.1.0 改造为会话插件
  - [x] 前端 xterm.js 交互终端
  - [x] 24 项单元测试
- [x] 插件仓库隔离
  - [x] NetKitX-Plugins 独立仓库
  - [x] Git Submodule 集成
  - [x] 部署脚本更新
- [x] 官方插件 (15+)
  - [x] port-scan, sql-inject, webshell
  - [x] subdomain-enum, dir-scan, file-upload
  - [x] 等等...

### 🔧 待修复

- [ ] 2 个 Agent 测试失败
  - `test_retryable_error_continues_loop`
  - `test_successful_action_resets_error_counter`

---

## 短期计划 (本周)

### 1. 修复测试 ⚡ (优先级: P0)

**时间**: 30 分钟
**负责人**: 立即处理

**任务**:
```bash
cd backend
pytest tests/test_agent.py::test_retryable_error_continues_loop -v
pytest tests/test_agent.py::test_successful_action_resets_error_counter -v
```

**目标**:
- 修复 2 个失败的测试
- 确保 CI 通过
- 保持代码质量

---

### 2. 完善 WebShell 插件 🐚 (优先级: P1)

**时间**: 1-2 天
**状态**: 待开始

#### 当前功能
- ✅ PHP eval/assert/base64 支持
- ✅ 连接测试
- ✅ 命令执行
- ✅ 文件管理 (列目录、读文件、写文件)
- ✅ 系统信息收集

#### 待添加功能

**2.1 完整的 Shell 类型支持**
- [ ] ASP eval/execute 完整实现
- [ ] JSP eval/reflection 完整实现
- [ ] 自动检测 Shell 类型

**2.2 文件管理增强**
- [ ] 文件上传 (分块上传大文件)
- [ ] 文件下载
- [ ] 文件编辑器
- [ ] 文件权限修改
- [ ] 文件搜索

**2.3 数据库管理**
- [ ] MySQL 连接和查询
- [ ] MSSQL 连接和查询
- [ ] 数据库列表
- [ ] 表结构查看
- [ ] SQL 执行

**2.4 高级功能**
- [ ] 反弹 Shell 生成
- [ ] 权限提升检测
- [ ] 内网扫描 (端口、主机发现)
- [ ] 进程管理
- [ ] 服务管理

**2.5 用户体验**
- [ ] 命令历史记录
- [ ] 自动补全
- [ ] 快捷命令 (cd, ls, pwd)
- [ ] 多标签页支持

**验收标准**:
- WebShell 插件功能完整,可实际使用
- 支持 PHP/ASP/JSP 三种类型
- 文件管理、数据库管理可用
- 代码质量良好,有测试覆盖

---

### 3. 添加新插件 🔌 (优先级: P2)

**时间**: 1-2 天
**状态**: 待开始

#### 3.1 CMS 识别插件

**功能**:
- 识别 WordPress, Joomla, Drupal, Typecho 等
- 版本检测
- 插件/主题识别
- 已知漏洞匹配

**参数**:
- `url`: 目标 URL
- `deep_scan`: 是否深度扫描

**输出**:
- CMS 类型
- 版本号
- 已安装插件列表
- 潜在漏洞

---

#### 3.2 WAF 检测插件

**功能**:
- 检测 WAF 类型 (CloudFlare, Akamai, 阿里云盾等)
- 检测 WAF 规则
- 绕过建议

**参数**:
- `url`: 目标 URL
- `test_payloads`: 测试 payload 列表

**输出**:
- WAF 类型
- 防护等级
- 绕过建议

---

#### 3.3 JWT 工具插件

**功能**:
- JWT 解析
- JWT 伪造 (弱密钥)
- JWT 爆破
- 算法混淆攻击

**参数**:
- `token`: JWT token
- `operation`: parse/forge/crack/attack
- `secret`: 密钥 (可选)

**输出**:
- 解析结果
- 伪造的 token
- 爆破结果

---

## 中期计划 (下周)

### 4. 知识库 Phase 3 - RAG 检索 🧠 (优先级: P1)

**时间**: 2-3 天
**状态**: 设计中

#### 目标
让 AI Agent 能够从历史会话中学习,减少重复错误,提升攻击成功率。

#### 技术方案

**4.1 向量化存储**
- [ ] 安装 pgvector 扩展
- [ ] 创建 embedding 表
- [ ] 实现 embedding 生成 (OpenAI/DeepSeek API)
- [ ] 批量向量化现有知识

**4.2 相似度搜索**
- [ ] 实现余弦相似度搜索
- [ ] 实现混合搜索 (向量 + 关键词)
- [ ] 搜索结果排序和过滤

**4.3 Prompt 注入**
- [ ] Agent 执行前检索相关知识
- [ ] 构建增强 prompt
- [ ] 知识相关性评分

**4.4 前端展示**
- [ ] 显示使用的知识条目
- [ ] 知识来源追溯
- [ ] 知识反馈机制

#### 数据库设计

```sql
-- 向量表
CREATE TABLE knowledge_embeddings (
    id SERIAL PRIMARY KEY,
    knowledge_id INTEGER REFERENCES knowledge_entries(id),
    embedding vector(1536),  -- OpenAI embedding 维度
    created_at TIMESTAMP DEFAULT NOW()
);

-- 向量索引
CREATE INDEX ON knowledge_embeddings
USING ivfflat (embedding vector_cosine_ops);
```

#### API 设计

```python
# 检索相关知识
GET /api/v1/knowledge/search
{
    "query": "如何绕过 WAF",
    "limit": 5,
    "threshold": 0.7
}

# 响应
{
    "results": [
        {
            "knowledge_id": 123,
            "title": "WAF 绕过技巧",
            "content": "...",
            "similarity": 0.85,
            "source_session": "session_456"
        }
    ]
}
```

#### 验收标准
- [ ] 知识条目自动向量化
- [ ] 相似度搜索准确率 > 80%
- [ ] Agent 能够使用检索到的知识
- [ ] 前端可以查看知识来源

---

## 长期计划 (下下周开始)

### 5. Plugin Engine 2.0 - Phase 1: 会话模式 ✅ (已完成)

**完成时间**: 2024-03-11

#### 已实现功能

**5.1 会话生命周期管理**
- [x] `PluginSessionManager` (Redis 存储)
- [x] 会话创建/销毁/列表
- [x] 会话超时管理 (1h TTL)

**5.2 WebSocket 双向通信**
- [x] `/api/v1/ws/plugin-sessions/{id}` 端点
- [x] 消息协议 (message/ping/close → event/pong/error/session_end)
- [x] Token 鉴权 + 心跳保活

**5.3 Redis 会话持久化**
- [x] JSON 状态序列化
- [x] 用户会话索引
- [x] 自动过期清理

**5.4 SDK**
- [x] `SessionPlugin` 基类 + `PluginMeta.mode`
- [x] `execute()` one-shot 回退

**5.5 WebShell 2.1.0**
- [x] xterm.js 交互终端
- [x] 命令历史 (上下箭头)
- [x] cwd 跟踪

**测试**: 24 项单元测试

---

### 6. Plugin Engine 2.0 - Phase 2: 自定义 UI (优先级: P2)

**时间**: 3-4 天
**状态**: 设计完成

#### 目标
插件可以注册自定义前端组件,不再局限于表格输出。

#### 核心功能

**6.1 UI 组件注册表**
```typescript
export const PluginUIRegistry = {
    "default": DefaultTableUI,
    "webshell-terminal": WebShellTerminalUI,
    "network-graph": NetworkGraphUI,
    "dashboard": DashboardUI,
};
```

**6.2 自定义 UI 组件**
- [ ] WebShell 终端 UI (xterm.js)
- [ ] 网络拓扑 UI (React Flow)
- [ ] 监控仪表盘 UI (echarts)

**6.3 插件 manifest 扩展**
```yaml
name: webshell
ui_component: webshell-terminal
```

#### 验收标准
- [ ] 3 个自定义 UI 组件可用
- [ ] 插件可以选择 UI 类型
- [ ] UI 组件开发文档完善

---

### 7. Plugin Engine 2.0 - Phase 3: 插件编排 (优先级: P3)

**时间**: 4-5 天
**状态**: 设计完成

#### 目标
插件可以组合成工作流,自动化复杂任务。

#### 核心功能

**7.1 工作流引擎**
- [ ] DAG 构建和验证
- [ ] 拓扑排序
- [ ] 并行执行
- [ ] 错误处理和重试

**7.2 可视化编辑器**
- [ ] React Flow 集成
- [ ] 拖拽节点
- [ ] 连线编辑
- [ ] 参数配置

**7.3 数据传递**
```yaml
workflow:
  nodes:
    - id: scan
      plugin: port-scan
    - id: vuln
      plugin: vuln-check
      params:
        ports: "{{scan.results.open_ports}}"
```

#### 验收标准
- [ ] 可以创建 10+ 节点的工作流
- [ ] 工作流执行成功率 > 90%
- [ ] 可视化编辑器易用

---

## 技术债务

### 代码质量
- [ ] 修复 2 个失败的测试
- [ ] 提升测试覆盖率到 60%
- [ ] 添加集成测试

### 性能优化
- [ ] 插件加载性能优化
- [ ] 数据库查询优化
- [ ] 前端打包优化

### 安全加固
- [ ] 插件沙箱隔离 (Docker)
- [ ] 细粒度权限控制
- [ ] 输入验证加强
- [ ] SQL 注入防护

### 运维改进
- [ ] 监控告警 (Prometheus + Grafana)
- [ ] 日志聚合 (Loki)
- [ ] 自动备份
- [ ] 灾难恢复方案

---

## 未来展望

### 插件生态
- [ ] 社区插件贡献机制
- [ ] 插件评分和评论
- [ ] 插件推荐算法
- [ ] 付费插件支持

### AI 增强
- [ ] 自动漏洞利用
- [ ] 智能 payload 生成
- [ ] 攻击路径规划
- [ ] 自动化渗透测试

### 企业功能
- [ ] 多租户支持
- [ ] 团队协作
- [ ] 权限管理
- [ ] 审计日志
- [ ] SSO 集成

### 商业化
- [ ] SaaS 版本
- [ ] 企业私有化部署
- [ ] 技术支持服务
- [ ] 培训和认证

---

## 里程碑

### M1: 插件系统完善 (本周完成)
- [x] 插件仓库隔离
- [ ] 测试修复
- [ ] WebShell 插件完善
- [ ] 3 个新插件

### M2: AI 能力增强 (下周完成)
- [ ] 知识库 RAG 检索
- [ ] Agent 学习能力提升

### M3: 插件引擎升级 (Phase 1 已完成)
- [x] Phase 1: 会话模式
- [ ] Phase 2: 自定义 UI
- [ ] Phase 3: 插件编排

### M4: 生态建设 (1-2 月)
- [ ] 社区插件 10+
- [ ] 用户文档完善
- [ ] 推广和运营

---

## 资源需求

### 开发资源
- 后端开发: 1 人
- 前端开发: 1 人 (部分时间)
- 测试: 自动化测试为主

### 基础设施
- Redis (会话存储)
- PostgreSQL + pgvector (向量搜索)
- 监控系统 (可选)

### 外部服务
- OpenAI/DeepSeek API (embedding)
- GitHub (代码托管)
- 服务器 (156.225.20.57)

---

## 风险和缓解

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|----------|
| Plugin Engine 2.0 开发周期长 | 高 | 中 | 分阶段实施,每个阶段独立可用 |
| 性能瓶颈 | 中 | 中 | 提前压测,优化关键路径 |
| 安全漏洞 | 高 | 低 | 代码审查,安全扫描 |
| 用户学习成本 | 中 | 中 | 完善文档,提供示例 |

---

## 更新日志

- **2024-03-11**: Plugin Engine 2.0 Phase 1 完成
  - SessionPlugin 基类 + SDK
  - Redis 会话管理 + WebSocket API
  - WebShell 2.1.0 会话模式
  - 前端 xterm.js 交互终端
  - 24 项单元测试
- **2024-03-10**: 创建开发路线图
  - 完成插件仓库隔离
  - 规划短期、中期、长期任务
  - 定义里程碑和验收标准

---

**下次更新**: 完成短期任务后更新进度
