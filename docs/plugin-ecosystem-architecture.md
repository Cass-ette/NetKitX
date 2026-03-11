# NetKitX 插件生态系统架构

## 仓库结构

```
NetKitX (主仓库)
├── backend/          # 核心后端
├── frontend/         # 核心前端
├── sdk/              # 插件 SDK
└── plugins/          # 官方插件 (内置)
    ├── port-scan/
    ├── sql-inject/
    └── webshell/

NetKitX-Plugins (插件仓库)
├── community/        # 社区插件
│   ├── subdomain-enum/
│   ├── cms-detect/
│   └── ...
├── experimental/     # 实验性插件
│   ├── ai-vuln-analyzer/
│   └── ...
└── templates/        # 插件模板
    ├── basic/
    ├── session/
    └── ui/
```

---

## 部署架构

### 方案 A: Git Submodule (推荐)

```bash
# 主仓库
NetKitX/
├── .gitmodules
└── plugins/
    ├── official/     # 官方插件 (主仓库)
    └── community/    # 社区插件 (submodule)

# .gitmodules
[submodule "plugins/community"]
    path = plugins/community
    url = https://github.com/Cass-ette/NetKitX-Plugins.git
    branch = main
```

**部署流程**:
```bash
# 服务器上
cd /opt/NetKitX
git pull origin main
git submodule update --init --recursive --remote

# 重启服务
docker compose -f docker-compose.prod.yml restart backend
```

**优点**:
- ✅ 插件仓库独立维护
- ✅ 主仓库可以锁定插件版本
- ✅ 部署简单,一条命令更新

**缺点**:
- ⚠️ Submodule 操作稍复杂
- ⚠️ 需要两次 commit (插件仓库 + 主仓库)

---

### 方案 B: 独立部署 + 符号链接

```bash
# 服务器上
/opt/NetKitX/              # 主应用
/opt/NetKitX-Plugins/      # 插件仓库

# 创建符号链接
ln -s /opt/NetKitX-Plugins/community /opt/NetKitX/plugins/community
```

**部署脚本**:
```bash
#!/bin/bash
# scripts/deploy-with-plugins.sh

# 更新主仓库
cd /opt/NetKitX
git pull origin main

# 更新插件仓库
cd /opt/NetKitX-Plugins
git pull origin main

# 重启服务
cd /opt/NetKitX
docker compose -f docker-compose.prod.yml restart backend
```

**优点**:
- ✅ 插件仓库完全独立
- ✅ 可以单独更新插件
- ✅ 不需要 submodule

**缺点**:
- ⚠️ 需要手动管理两个仓库
- ⚠️ 符号链接在 Docker 中可能有问题

---

### 方案 C: 插件市场 + 远程加载 (未来)

```yaml
# config/plugins.yaml
plugins:
  - name: subdomain-enum
    source: github://NetKitX-Plugins/community/subdomain-enum
    version: 1.0.0
    enabled: true

  - name: cms-detect
    source: github://NetKitX-Plugins/community/cms-detect
    version: 2.1.0
    enabled: true
```

**加载流程**:
```python
# backend/app/plugins/remote_loader.py

async def load_remote_plugin(config: dict):
    """从远程仓库加载插件"""
    source = config["source"]
    version = config["version"]

    # 解析 source
    if source.startswith("github://"):
        repo, path = parse_github_url(source)
        # 下载插件
        plugin_dir = await download_from_github(repo, path, version)
    elif source.startswith("http://") or source.startswith("https://"):
        # 从 HTTP URL 下载
        plugin_dir = await download_from_url(source)

    # 加载插件
    plugin = load_plugin(plugin_dir)
    registry.register(plugin)
```

**优点**:
- ✅ 插件完全解耦
- ✅ 支持版本管理
- ✅ 支持多个插件源

**缺点**:
- ⚠️ 实现复杂
- ⚠️ 需要网络访问
- ⚠️ 安全风险(需要签名验证)

---

## 推荐方案:Git Submodule

### 实施步骤

#### 1. 创建插件仓库

```bash
# 创建新仓库
gh repo create NetKitX-Plugins --public --description "NetKitX Community Plugins"

# 初始化结构
mkdir -p NetKitX-Plugins/{community,experimental,templates}
cd NetKitX-Plugins

# 创建 README
cat > README.md << 'EOF'
# NetKitX Plugins

Community-contributed plugins for NetKitX.

## Structure

- `community/` - Stable community plugins
- `experimental/` - Experimental plugins (use at your own risk)
- `templates/` - Plugin templates for developers

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.
EOF

git init
git add .
git commit -m "Initial commit"
git remote add origin git@github.com:Cass-ette/NetKitX-Plugins.git
git push -u origin main
```

#### 2. 添加 Submodule 到主仓库

```bash
cd /path/to/NetKitX

# 添加 submodule
git submodule add https://github.com/Cass-ette/NetKitX-Plugins.git plugins/community

# 提交
git add .gitmodules plugins/community
git commit -m "Add community plugins as submodule"
git push origin develop
```

#### 3. 修改插件加载器

```python
# backend/app/plugins/loader.py

PLUGIN_DIRS = [
    Path(__file__).parent.parent.parent / "plugins" / "official",  # 官方插件
    Path(__file__).parent.parent.parent / "plugins" / "community",  # 社区插件
]

def load_all_plugins():
    """加载所有插件"""
    for plugin_dir in PLUGIN_DIRS:
        if not plugin_dir.exists():
            logger.warning(f"Plugin directory not found: {plugin_dir}")
            continue

        for subdir in plugin_dir.iterdir():
            if subdir.is_dir() and (subdir / "plugin.yaml").exists():
                try:
                    load_single_plugin(subdir)
                    logger.info(f"Loaded plugin: {subdir.name}")
                except Exception as e:
                    logger.error(f"Failed to load plugin {subdir.name}: {e}")
```

#### 4. 更新部署脚本

```bash
# scripts/deploy.sh

#!/bin/bash
set -e

echo "🚀 Starting NetKitX deployment..."

# 推送主仓库
echo "📤 Pushing main repo..."
git push origin develop

# 更新服务器
echo "🔄 Pulling latest code on server..."
ssh root@156.225.20.57 "cd /opt/NetKitX && \
    git pull && \
    git submodule update --init --recursive --remote"

# 重建容器
echo "🐳 Building and restarting containers..."
ssh root@156.225.20.57 "cd /opt/NetKitX && \
    docker compose -f docker-compose.prod.yml up -d --build"

echo "✅ Deployment complete!"
```

#### 5. 插件开发工作流

```bash
# 开发者工作流

# 1. Fork 插件仓库
gh repo fork Cass-ette/NetKitX-Plugins

# 2. Clone 到本地
git clone git@github.com:YOUR_USERNAME/NetKitX-Plugins.git
cd NetKitX-Plugins

# 3. 创建新插件
mkdir community/my-plugin
cd community/my-plugin

# 4. 开发插件
cat > plugin.yaml << 'EOF'
name: my-plugin
version: 1.0.0
description: My awesome plugin
category: recon
engine: python
EOF

cat > main.py << 'EOF'
from netkitx_sdk import PluginBase, PluginEvent, PluginMeta

class MyPlugin(PluginBase):
    meta = PluginMeta(
        name="my-plugin",
        version="1.0.0",
        description="My awesome plugin",
        category="recon",
        engine="python",
    )

    async def execute(self, params):
        yield PluginEvent(type="result", data={...})

plugin = MyPlugin()
EOF

# 5. 测试插件
cd ../../..
ln -s $(pwd)/NetKitX-Plugins/community /path/to/NetKitX/plugins/community
cd /path/to/NetKitX
./scripts/start.sh

# 6. 提交 PR
cd /path/to/NetKitX-Plugins
git add community/my-plugin
git commit -m "Add my-plugin"
git push origin main
gh pr create --title "Add my-plugin" --body "Description..."
```

---

## 插件审核流程

### 自动化检查

```yaml
# .github/workflows/plugin-check.yml (插件仓库)

name: Plugin Check

on:
  pull_request:
    paths:
      - 'community/**'
      - 'experimental/**'

jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Check plugin structure
        run: |
          # 检查必需文件
          for plugin in community/*; do
            if [ ! -f "$plugin/plugin.yaml" ]; then
              echo "❌ Missing plugin.yaml in $plugin"
              exit 1
            fi
            if [ ! -f "$plugin/main.py" ]; then
              echo "❌ Missing main.py in $plugin"
              exit 1
            fi
          done

      - name: Lint plugin code
        run: |
          pip install ruff
          ruff check community/ experimental/

      - name: Security scan
        run: |
          pip install bandit
          bandit -r community/ experimental/

      - name: Test plugin loading
        run: |
          # 尝试加载插件
          python scripts/test_plugin_load.py
```

### 人工审核清单

- [ ] 插件功能描述清晰
- [ ] 代码无明显安全问题
- [ ] 无恶意代码(网络请求、文件操作合理)
- [ ] 遵循插件开发规范
- [ ] 有基本的错误处理
- [ ] 参数验证完整

---

## 插件分类

### 官方插件 (Official)

**位置**: `NetKitX/plugins/official/`
**维护**: 官方团队
**质量**: 高质量,经过充分测试
**示例**:
- port-scan
- sql-inject
- webshell
- http-request

### 社区插件 (Community)

**位置**: `NetKitX-Plugins/community/`
**维护**: 社区贡献者
**质量**: 经过审核,基本可用
**示例**:
- subdomain-enum
- cms-detect
- waf-detect
- api-fuzzer

### 实验性插件 (Experimental)

**位置**: `NetKitX-Plugins/experimental/`
**维护**: 个人开发者
**质量**: 未经充分测试,可能不稳定
**示例**:
- ai-vuln-analyzer
- blockchain-scanner
- iot-scanner

---

## 插件元数据

```yaml
# plugin.yaml 扩展字段

name: subdomain-enum
version: 1.0.0
description: Subdomain enumeration tool
category: recon
engine: python

# 新增字段
author: username
repository: https://github.com/username/plugin-repo
license: MIT
tags: [subdomain, dns, recon]
dependencies:
  - dnspython>=2.0.0
  - aiohttp>=3.8.0

# 插件来源
source:
  type: community  # official | community | experimental
  verified: true   # 是否经过官方验证
  last_updated: 2024-03-10
```

---

## 插件市场 UI

### 插件列表页

```typescript
// frontend/src/app/marketplace/page.tsx

export default function MarketplacePage() {
  const [plugins, setPlugins] = useState<Plugin[]>([]);
  const [filter, setFilter] = useState<"all" | "official" | "community">("all");

  return (
    <div>
      <Tabs value={filter} onValueChange={setFilter}>
        <TabsList>
          <TabsTrigger value="all">All</TabsTrigger>
          <TabsTrigger value="official">Official</TabsTrigger>
          <TabsTrigger value="community">Community</TabsTrigger>
        </TabsList>
      </Tabs>

      <div className="grid grid-cols-3 gap-4">
        {plugins.map(plugin => (
          <PluginCard
            key={plugin.name}
            plugin={plugin}
            badge={plugin.source.type}  // 显示来源标签
            verified={plugin.source.verified}  // 显示验证标记
          />
        ))}
      </div>
    </div>
  );
}
```

---

## 总结

### 推荐架构

```
NetKitX (主仓库)
├── plugins/
│   ├── official/          # 官方插件 (主仓库维护)
│   └── community/         # 社区插件 (submodule)
│       └── → NetKitX-Plugins/community/

NetKitX-Plugins (插件仓库)
├── community/             # 稳定的社区插件
├── experimental/          # 实验性插件
└── templates/             # 插件模板
```

### 优势

1. **隔离开发**: 官方插件和社区插件分开维护
2. **独立迭代**: 插件仓库可以独立发版
3. **降低风险**: 社区插件问题不影响主仓库
4. **易于贡献**: 开发者只需 fork 插件仓库
5. **灵活部署**: 可以选择性加载插件

### 下一步

1. [ ] 创建 NetKitX-Plugins 仓库
2. [ ] 添加 submodule 到主仓库
3. [ ] 迁移现有插件到 official/
4. [ ] 更新部署脚本
5. [ ] 编写插件开发文档
6. [ ] 设置 CI/CD 自动检查
