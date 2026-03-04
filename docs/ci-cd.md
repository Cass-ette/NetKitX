# CI/CD 配置文档

## 概述

NetKitX 使用 GitHub Actions 实现完整的 CI/CD 流程，包括：

- **持续集成 (CI)** — 自动测试、代码检查、安全扫描
- **持续部署 (CD)** — Docker 镜像构建和发布
- **自动发布** — 版本标签自动创建 GitHub Release

---

## Workflows

### 1. CI Pipeline (`.github/workflows/ci.yml`)

**触发条件**：
- Push 到 `main` 分支
- Pull Request 到 `main` 分支

**Jobs**：

#### Backend Tests
- Python 3.11
- PostgreSQL 16 + Redis 7 服务
- 步骤：
  1. Ruff format 检查
  2. Ruff lint 检查
  3. Pytest 运行测试
  4. 上传覆盖率到 Codecov

#### Frontend Tests
- Node.js 20
- 步骤：
  1. ESLint 检查
  2. TypeScript 类型检查
  3. Next.js 构建验证

#### Security Scan
- Trivy 漏洞扫描
- 结果上传到 GitHub Security

---

### 2. Docker Build (`.github/workflows/docker.yml`)

**触发条件**：
- Push 到 `main` 分支
- Push 版本标签 (`v*`)
- Release 发布

**Jobs**：

#### Build Backend Image
- 多阶段构建优化镜像大小
- 推送到 GitHub Container Registry (ghcr.io)
- 标签策略：
  - `main` — 最新开发版
  - `v1.2.3` — 语义化版本
  - `v1.2` — 主次版本
  - `main-abc1234` — commit SHA

#### Build Frontend Image
- Next.js standalone 模式
- 支持 `NEXT_PUBLIC_API_URL` 构建参数
- 相同的标签策略

---

### 3. Release (`.github/workflows/release.yml`)

**触发条件**：
- Push 版本标签 (`v*`)

**功能**：
- 自动生成 changelog（基于 git log）
- 创建 GitHub Release
- 包含 Docker 镜像拉取命令
- 预发布版本检测（alpha/beta/rc）

---

## 使用指南

### 本地测试

#### 后端测试

```bash
cd backend

# 启动测试数据库
docker run -d --name netkitx-test-db \
  -e POSTGRES_USER=netkitx \
  -e POSTGRES_PASSWORD=netkitx \
  -e POSTGRES_DB=netkitx_test \
  -p 5432:5432 \
  postgres:16

# 启动 Redis
docker run -d --name netkitx-test-redis \
  -p 6379:6379 \
  redis:7-alpine

# 运行测试
pytest

# 查看覆盖率
pytest --cov-report=html
open htmlcov/index.html
```

#### 前端测试

```bash
cd frontend

# Lint
npm run lint

# 类型检查
npx tsc --noEmit

# 构建
npm run build
```

### Docker 本地构建

```bash
# 后端
docker build -t netkitx-backend:local ./backend

# 前端
docker build -t netkitx-frontend:local \
  --build-arg NEXT_PUBLIC_API_URL=http://localhost:8000 \
  ./frontend

# 运行
docker run -p 8000:8000 netkitx-backend:local
docker run -p 3000:3000 netkitx-frontend:local
```

### 发布新版本

```bash
# 1. 更新版本号
# backend/pyproject.toml: version = "1.2.3"
# frontend/package.json: "version": "1.2.3"

# 2. 提交更改
git add .
git commit -m "chore: bump version to 1.2.3"
git push

# 3. 创建标签
git tag v1.2.3
git push origin v1.2.3

# 4. GitHub Actions 自动：
#    - 运行 CI 测试
#    - 构建 Docker 镜像
#    - 创建 GitHub Release
```

---

## 环境变量配置

### GitHub Secrets

需要在 GitHub 仓库设置中配置以下 Secrets：

| Secret | 用途 | 必需 |
|--------|------|------|
| `CODECOV_TOKEN` | Codecov 上传 token | 可选 |
| `NEXT_PUBLIC_API_URL` | 前端 API 地址（生产环境） | 可选 |

**配置路径**：Settings → Secrets and variables → Actions

### GitHub Packages 权限

Docker 镜像推送到 GitHub Container Registry 需要：

1. 仓库设置 → Actions → General
2. Workflow permissions → Read and write permissions
3. 勾选 "Allow GitHub Actions to create and approve pull requests"

---

## Docker 镜像使用

### 拉取镜像

```bash
# 最新版本
docker pull ghcr.io/cass-ette/netkitx-backend:main
docker pull ghcr.io/cass-ette/netkitx-frontend:main

# 特定版本
docker pull ghcr.io/cass-ette/netkitx-backend:v1.2.3
docker pull ghcr.io/cass-ette/netkitx-frontend:v1.2.3
```

### 运行容器

```bash
# 后端
docker run -d \
  --name netkitx-backend \
  -p 8000:8000 \
  -e DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/netkitx \
  -e REDIS_URL=redis://host:6379/0 \
  -e SECRET_KEY=your-secret-key \
  ghcr.io/cass-ette/netkitx-backend:v1.2.3

# 前端
docker run -d \
  --name netkitx-frontend \
  -p 3000:3000 \
  ghcr.io/cass-ette/netkitx-frontend:v1.2.3
```

### Docker Compose

```yaml
version: '3.8'

services:
  backend:
    image: ghcr.io/cass-ette/netkitx-backend:v1.2.3
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: postgresql+asyncpg://netkitx:netkitx@postgres:5432/netkitx
      REDIS_URL: redis://redis:6379/0
      SECRET_KEY: ${SECRET_KEY}
    depends_on:
      - postgres
      - redis

  frontend:
    image: ghcr.io/cass-ette/netkitx-frontend:v1.2.3
    ports:
      - "3000:3000"
    depends_on:
      - backend

  postgres:
    image: postgres:16
    environment:
      POSTGRES_USER: netkitx
      POSTGRES_PASSWORD: netkitx
      POSTGRES_DB: netkitx
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine

volumes:
  postgres_data:
```

---

## 故障排查

### CI 失败

#### 后端测试失败
```bash
# 检查日志
gh run view <run-id> --log

# 本地复现
cd backend
pytest -v
```

#### 前端构建失败
```bash
# 检查类型错误
cd frontend
npx tsc --noEmit

# 检查 lint
npm run lint
```

### Docker 构建失败

```bash
# 本地构建查看详细日志
docker build --progress=plain -t test ./backend

# 检查 .dockerignore
cat backend/.dockerignore
```

### 镜像推送失败

1. 检查 GitHub Packages 权限
2. 确认 GITHUB_TOKEN 有 `packages:write` 权限
3. 查看 Actions 日志中的认证错误

---

## 最佳实践

### 1. 分支策略

- `main` — 稳定分支，所有 PR 合并到这里
- `feat/*` — 功能分支
- `fix/*` — 修复分支
- `chore/*` — 杂项分支

### 2. Commit 规范

遵循 Conventional Commits：

```
feat: add new feature
fix: resolve bug
docs: update documentation
chore: update dependencies
test: add tests
refactor: refactor code
```

### 3. PR 流程

1. 创建分支并开发
2. 推送后自动触发 CI
3. CI 通过后请求 Review
4. Merge 到 main 后自动构建镜像

### 4. 版本发布

- 遵循语义化版本 (SemVer)
- `v1.0.0` — 主版本（不兼容变更）
- `v1.1.0` — 次版本（新功能）
- `v1.1.1` — 补丁版本（bug 修复）

---

## 监控和告警

### GitHub Actions 通知

在 Settings → Notifications 中配置：
- Email 通知
- Slack/Discord webhook

### 覆盖率监控

Codecov 提供：
- PR 覆盖率变化
- 覆盖率趋势图
- 未覆盖代码高亮

### 安全扫描

Trivy 扫描结果在：
- Security → Code scanning alerts
- 自动创建 Issue（如果发现高危漏洞）

---

## 参考资料

- [GitHub Actions 文档](https://docs.github.com/en/actions)
- [Docker 多阶段构建](https://docs.docker.com/build/building/multi-stage/)
- [Next.js Standalone 模式](https://nextjs.org/docs/advanced-features/output-file-tracing)
- [Codecov 集成](https://docs.codecov.com/docs/github-actions)
