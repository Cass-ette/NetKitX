#!/bin/bash
set -euo pipefail

# =============================================
# NetKitX 阿里云部署脚本
# 服务器: 8.147.59.78 (wql.me)
# 运行方式: ssh root@8.147.59.78 'bash -s' < deploy/deploy.sh
# =============================================

REPO_URL="https://github.com/Cass-ette/NetKitX.git"
INSTALL_DIR="/opt/NetKitX"
DOMAIN="wql.me"

echo "=========================================="
echo " NetKitX 部署 → ${DOMAIN}"
echo "=========================================="

# ------------------------------------------
# Step 1: 系统基础环境
# ------------------------------------------
echo "[1/7] 安装基础依赖..."
yum install -y git nginx

# 添加 2GB swap (构建镜像需要)
if [ ! -f /swapfile ]; then
    echo "[1/7] 创建 2GB swap..."
    fallocate -l 2G /swapfile
    chmod 600 /swapfile
    mkswap /swapfile
    swapon /swapfile
    echo '/swapfile none swap sw 0 0' >> /etc/fstab
    echo "[1/7] Swap 已启用"
else
    echo "[1/7] Swap 已存在，跳过"
fi

# ------------------------------------------
# Step 2: 克隆代码
# ------------------------------------------
echo "[2/7] 克隆代码..."
if [ -d "${INSTALL_DIR}/.git" ]; then
    echo "[2/7] 仓库已存在，拉取最新代码..."
    cd "${INSTALL_DIR}" && git pull
else
    git clone "${REPO_URL}" "${INSTALL_DIR}"
fi
cd "${INSTALL_DIR}"

# ------------------------------------------
# Step 3: 生成 .env 文件
# ------------------------------------------
echo "[3/7] 生成配置文件..."
POSTGRES_PASSWORD=$(openssl rand -hex 16)
SECRET_KEY=$(openssl rand -hex 32)

# 如果 .env 已存在，读取已有密码（避免重建时丢失数据）
if [ -f backend/.env ]; then
    echo "[3/7] backend/.env 已存在，保留现有配置"
else
    cat > backend/.env << EOF
# Database
DATABASE_URL=postgresql+asyncpg://netkitx:${POSTGRES_PASSWORD}@db:5432/netkitx

# Redis
REDIS_URL=redis://redis:6379/0

# Security
SECRET_KEY=${SECRET_KEY}
DEBUG=false

# CORS
ALLOWED_ORIGINS=["https://${DOMAIN}"]
EOF
    echo "[3/7] backend/.env 已生成"
fi

# 从 .env 中提取 POSTGRES_PASSWORD 供 docker compose 使用
POSTGRES_PASSWORD=$(grep DATABASE_URL backend/.env | sed 's/.*netkitx:\(.*\)@db.*/\1/')

# 导出给 docker-compose.prod.yml 中的 ${POSTGRES_PASSWORD}
export POSTGRES_PASSWORD

# ------------------------------------------
# Step 4: 构建并启动容器
# ------------------------------------------
echo "[4/7] 构建并启动 Docker 容器..."
docker compose -f docker-compose.prod.yml up -d --build

# 等待后端就绪
echo "[4/7] 等待后端启动..."
for i in $(seq 1 30); do
    if curl -sf http://127.0.0.1:8000/api/health > /dev/null 2>&1; then
        echo "[4/7] 后端已就绪"
        break
    fi
    sleep 2
done

# ------------------------------------------
# Step 5: 运行数据库迁移
# ------------------------------------------
echo "[5/7] 运行数据库迁移..."
docker compose -f docker-compose.prod.yml exec backend alembic upgrade head

# ------------------------------------------
# Step 6: 配置 Nginx
# ------------------------------------------
echo "[6/7] 配置 Nginx..."
cp deploy/netkitx.conf /etc/nginx/conf.d/netkitx.conf

# 删除默认配置（如果存在）
rm -f /etc/nginx/conf.d/default.conf

# 先用 HTTP-only 配置启动（SSL 证书还没装）
cat > /etc/nginx/conf.d/netkitx.conf << 'NGINX'
server {
    listen 80;
    server_name wql.me;

    client_max_body_size 50M;

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 300s;
    }

    location /docs {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /openapi.json {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
    }

    location /ws/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 86400s;
    }

    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
NGINX

nginx -t && systemctl enable nginx && systemctl restart nginx
echo "[6/7] Nginx 已配置"

# ------------------------------------------
# Step 7: SSL 证书 (Let's Encrypt)
# ------------------------------------------
echo "[7/7] 安装 SSL 证书..."
if ! command -v certbot &> /dev/null; then
    yum install -y epel-release
    yum install -y certbot python3-certbot-nginx
fi

# 申请证书（需要 DNS 已指向本机）
certbot --nginx -d "${DOMAIN}" --non-interactive --agree-tos --email admin@${DOMAIN} || {
    echo ""
    echo "⚠  SSL 证书申请失败！"
    echo "   请确认 DNS A 记录 ${DOMAIN} → $(curl -s ifconfig.me) 已生效"
    echo "   然后手动运行: certbot --nginx -d ${DOMAIN}"
    echo ""
    echo "   当前 HTTP 访问已可用: http://${DOMAIN}"
}

# ------------------------------------------
# 完成
# ------------------------------------------
echo ""
echo "=========================================="
echo " 部署完成！"
echo "=========================================="
echo ""
echo " 访问地址:  https://${DOMAIN}"
echo " API 文档:  https://${DOMAIN}/docs"
echo " 健康检查:  curl https://${DOMAIN}/api/health"
echo ""
echo " 管理命令:"
echo "   cd ${INSTALL_DIR}"
echo "   docker compose -f docker-compose.prod.yml logs -f       # 查看日志"
echo "   docker compose -f docker-compose.prod.yml restart        # 重启服务"
echo "   docker compose -f docker-compose.prod.yml down           # 停止服务"
echo "   docker compose -f docker-compose.prod.yml up -d --build  # 重新构建"
echo ""
