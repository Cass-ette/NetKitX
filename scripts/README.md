# NetKitX Deployment Scripts

生产环境部署和管理脚本集合。

## 脚本列表

### 🚀 deploy.sh - 部署到生产环境
完整的部署流程：推送代码 → 服务器拉取 → 重建容器

```bash
./scripts/deploy.sh              # 标准部署
./scripts/deploy.sh --migrate    # 部署 + 数据库迁移
```

**流程**:
1. 推送代码到 GitHub (develop 分支)
2. SSH 到服务器拉取最新代码
3. 重建并重启 Docker 容器
4. (可选) 运行数据库迁移

---

### 📊 status.sh - 查看生产环境状态
快速检查生产环境健康状况

```bash
./scripts/status.sh
```

**显示内容**:
- 容器运行状态
- 磁盘使用情况
- SSL 证书状态
- 站点可访问性
- 最近的后端日志

---

### 📝 logs.sh - 查看日志
查看生产环境日志

```bash
./scripts/logs.sh                # 所有服务，最近 50 行
./scripts/logs.sh backend        # 仅后端，最近 50 行
./scripts/logs.sh backend -f     # 后端，实时跟踪模式
./scripts/logs.sh frontend --follow  # 前端，实时跟踪
```

**可用服务**: backend, frontend, db, redis, worker

---

### 💾 backup-db.sh - 数据库备份
备份生产数据库到本地

```bash
./scripts/backup-db.sh
```

**功能**:
- 创建 PostgreSQL 数据库转储
- 自动压缩 (gzip)
- 保存到 `./backups/` 目录
- 自动清理，仅保留最近 7 个备份

**备份文件**: `backups/netkitx_backup_YYYYMMDD_HHMMSS.sql.gz`

---

### 🔄 restart.sh - 重启服务
快速重启生产环境服务

```bash
./scripts/restart.sh             # 重启所有服务
./scripts/restart.sh backend     # 仅重启后端
./scripts/restart.sh frontend    # 仅重启前端
```

**注意**: 重启不会重建容器，仅重启现有容器。如需重建请使用 `deploy.sh`。

---

## 生产环境信息

- **服务器**: 156.225.20.57
- **域名**: https://wql.me
- **项目路径**: /opt/NetKitX
- **Compose 文件**: docker-compose.prod.yml

## 环境配置文件

### backend/.env
```bash
DOMAIN=wql.me
GITHUB_CLIENT_ID=Ov23lin5UCuWeISY6bfq
GITHUB_CLIENT_SECRET=8d8772f5bdebc0b6e2b6ad5ff068e09e69bcc5ac
POSTGRES_PASSWORD=netkitx_prod_2024
```

### docker-compose.prod.yml 关键配置
```yaml
backend:
  environment:
    - ALLOWED_ORIGINS=["https://wql.me"]
    - GITHUB_CLIENT_ID=${GITHUB_CLIENT_ID}
    - GITHUB_CLIENT_SECRET=${GITHUB_CLIENT_SECRET}

frontend:
  build:
    args:
      NEXT_PUBLIC_API_URL: https://wql.me
```

## HTTPS 配置

- **证书**: Let's Encrypt (免费)
- **工具**: Certbot
- **自动续期**: 已启用 (systemd timer)
- **Nginx 配置**: /etc/nginx/conf.d/netkitx.conf

## 常见操作

### 完整部署流程
```bash
# 1. 本地测试
cd backend && source .venv/bin/activate
ruff format .
ruff check --fix .
pytest -v

# 2. 提交代码
git add .
git commit -m "feat: your changes"

# 3. 部署
./scripts/deploy.sh --migrate
```

### 查看实时日志
```bash
./scripts/logs.sh backend -f
```

### 检查服务状态
```bash
./scripts/status.sh
```

### 数据库备份
```bash
./scripts/backup-db.sh
```

### 紧急重启
```bash
./scripts/restart.sh backend
```

## 手动操作 (不推荐)

如需手动操作，可直接 SSH 到服务器：

```bash
ssh root@156.225.20.57

# 进入项目目录
cd /opt/NetKitX

# 查看容器状态
docker compose -f docker-compose.prod.yml ps

# 查看日志
docker compose -f docker-compose.prod.yml logs -f backend

# 重启服务
docker compose -f docker-compose.prod.yml restart backend

# 数据库迁移
docker compose -f docker-compose.prod.yml exec backend alembic upgrade head

# 数据库操作
docker compose -f docker-compose.prod.yml exec db psql -U netkitx -d netkitx
```

## 注意事项

⚠️ **重要提醒**:
- 本地 Mac 是开发机，`./scripts/start.sh` 和 `./scripts/stop.sh` 仅用于本地开发
- 生产环境操作必须通过 SSH 或使用这些部署脚本
- 部署前务必运行本地 CI 检查 (ruff format + ruff check + pytest)
- 数据库迁移需要在部署后手动执行或使用 `--migrate` 参数
- 备份数据库后再进行重大变更
