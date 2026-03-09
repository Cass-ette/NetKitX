# NetKitX Frontend

基于 Next.js 16 的网络安全工具平台前端。

## 技术栈

- **框架**: Next.js 16 (App Router, Turbopack)
- **语言**: TypeScript
- **UI**: Shadcn/UI + Tailwind CSS
- **状态管理**: Zustand
- **终端**: xterm.js
- **拓扑图**: React Flow + dagre
- **国际化**: 自定义 i18n (8 语言)
- **认证**: JWT + WebAuthn API

## 开发

```bash
npm install
npm run dev     # 开发服务器 http://localhost:3000
npm run build   # 生产构建
npm run lint    # ESLint 检查
```

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | 后端 API 地址，生产环境设为空字符串（使用相对路径） |

## 页面路由

| 路由 | 说明 |
|------|------|
| `/login` | 登录页（账号密码 / GitHub / Passkey） |
| `/dashboard` | 仪表盘 |
| `/tools` | 工具列表 |
| `/tools/[slug]` | 工具执行页 |
| `/tasks` | 任务管理 |
| `/plugins` | 插件管理 |
| `/marketplace` | 插件市场 |
| `/ai-chat` | AI 对话 / Agent |
| `/sessions` | Agent 会话历史 |
| `/knowledge` | 攻防知识库 |
| `/topology` | 网络拓扑可视化 |
| `/settings` | 系统设置（AI 配置 / Passkey 管理） |
| `/admin` | 管理员面板 |
