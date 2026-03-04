#!/bin/bash

# NetKitX 插件市场启动脚本

set -e

echo "🚀 启动 NetKitX 插件市场..."

# 检查是否在项目根目录
if [ ! -d "backend" ] || [ ! -d "frontend" ]; then
    echo "❌ 错误: 请在项目根目录运行此脚本"
    exit 1
fi

# 启动后端
echo ""
echo "📦 启动后端服务..."
cd backend

# 检查虚拟环境
if [ ! -d ".venv" ]; then
    echo "⚠️  虚拟环境不存在，正在创建..."
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -e .
else
    source .venv/bin/activate
fi

# 运行迁移
echo "🔄 运行数据库迁移..."
alembic upgrade head

# 启动后端（后台运行）
echo "✅ 启动 FastAPI 服务 (http://localhost:8000)..."
uvicorn app.main:app --host 0.0.0.0 --port 8000 > ../backend.log 2>&1 &
BACKEND_PID=$!
echo "   后端 PID: $BACKEND_PID"

cd ..

# 启动前端
echo ""
echo "🎨 启动前端服务..."
cd frontend

# 检查依赖
if [ ! -d "node_modules" ]; then
    echo "⚠️  依赖未安装，正在安装..."
    npm install
fi

# 启动前端（后台运行）
echo "✅ 启动 Next.js 服务 (http://localhost:3000)..."
npm run dev > ../frontend.log 2>&1 &
FRONTEND_PID=$!
echo "   前端 PID: $FRONTEND_PID"

cd ..

# 保存 PID
echo "$BACKEND_PID" > .backend.pid
echo "$FRONTEND_PID" > .frontend.pid

echo ""
echo "✨ NetKitX 插件市场已启动！"
echo ""
echo "📍 访问地址:"
echo "   - 前端: http://localhost:3000"
echo "   - 后端 API: http://localhost:8000"
echo "   - API 文档: http://localhost:8000/docs"
echo "   - 插件市场: http://localhost:3000/marketplace"
echo ""
echo "📝 日志文件:"
echo "   - 后端: backend.log"
echo "   - 前端: frontend.log"
echo ""
echo "🛑 停止服务: ./scripts/stop.sh"
echo ""
