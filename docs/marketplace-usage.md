# NetKitX 插件市场使用指南

## 启动服务

插件市场已集成到 NetKitX 主系统中，按以下步骤启动：

### 1. 启动后端服务

```bash
cd backend

# 激活虚拟环境
source .venv/bin/activate

# 运行数据库迁移（首次启动或更新后）
alembic upgrade head

# 启动 FastAPI 服务
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

后端 API 将在 `http://localhost:8000` 运行

### 2. 启动前端服务

```bash
cd frontend

# 安装依赖（首次启动）
npm install

# 启动开发服务器
npm run dev
```

前端将在 `http://localhost:3000` 运行

### 3. 访问插件市场

在浏览器中打开：
- 市场列表页: `http://localhost:3000/marketplace`
- 我的插件: `http://localhost:3000/plugins`

## 使用功能

### 浏览和安装插件

1. 访问 `/marketplace` 查看所有可用插件
2. 使用搜索框、分类筛选、验证筛选来查找插件
3. 点击插件卡片查看详情
4. 在详情页选择版本并点击"Install Plugin"
5. 等待安装完成，系统会自动解析和安装依赖

### 发布插件

使用 CLI 工具发布插件：

```bash
# 进入后端目录
cd backend
source .venv/bin/activate

# 打包插件
python -m app.cli.publish pack /path/to/your/plugin

# 发布到市场（需要先登录）
python -m app.cli.publish publish /path/to/your/plugin

# 撤回版本
python -m app.cli.publish yank plugin-name 1.0.0
```

### 举报插件

如果发现恶意插件：
1. 访问插件详情页
2. 点击"Report"按钮
3. 选择举报原因（malware/spam/copyright/other）
4. 填写详细描述
5. 提交举报

## API 端点

插件市场提供以下 API 端点：

### 浏览和搜索
- `GET /api/v1/marketplace/plugins` - 列出插件
- `GET /api/v1/marketplace/plugins/{name}` - 获取插件详情
- `GET /api/v1/marketplace/categories` - 获取分类列表
- `GET /api/v1/marketplace/plugins/{name}/versions` - 列出版本
- `GET /api/v1/marketplace/plugins/{name}/versions/{version}/dependencies` - 获取依赖

### 安装和管理
- `POST /api/v1/marketplace/install` - 安装插件
- `GET /api/v1/marketplace/installed` - 列出已安装插件

### 评价
- `POST /api/v1/marketplace/plugins/{name}/reviews` - 创建评价
- `GET /api/v1/marketplace/plugins/{name}/reviews` - 获取评价列表

### 发布（需要认证）
- `POST /api/v1/marketplace/publish` - 发布插件
- `DELETE /api/v1/marketplace/plugins/{name}/versions/{version}` - 撤回版本

### 举报
- `POST /api/v1/marketplace/plugins/{name}/report` - 举报插件
- `GET /api/v1/marketplace/reports` - 查看我的举报

## 安全特性

发布插件时会自动进行安全扫描：
- 检测危险代码模式（eval、exec、subprocess）
- 验证许可证
- 检查权限声明
- 防止路径遍历攻击
- 计算安全评分（0-100）

只有通过安全扫描（无严重问题且评分 ≥ 70）的插件才能发布。

## 开发测试

运行测试：

```bash
cd backend
source .venv/bin/activate

# 运行所有测试
pytest

# 运行市场相关测试
pytest tests/test_version.py tests/test_resolver.py tests/test_installer.py tests/test_publish.py tests/test_scanner.py

# 查看测试覆盖率
pytest --cov=app/marketplace
```

## 故障排查

### 数据库连接失败
确保 PostgreSQL 正在运行，检查 `.env` 文件中的数据库配置。

### 前端无法连接后端
检查 `frontend/.env.local` 中的 `NEXT_PUBLIC_API_URL` 是否正确。

### 插件安装失败
查看后端日志，可能是依赖解析失败或网络问题。

### 发布失败
检查插件结构是否正确，是否包含 `plugin.yaml` 和主入口文件。
