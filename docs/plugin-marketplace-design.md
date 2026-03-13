# 插件市场设计方案

> **Status: All 7 phases implemented** (Infrastructure → Resolver → Installer → UI → Publishing → Security → Update System)

## 1. 架构概览

### 1.1 核心组件

```
┌─────────────────────────────────────────────────────────┐
│                    Plugin Marketplace                    │
├─────────────────────────────────────────────────────────┤
│                                                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │   Registry   │  │   Resolver   │  │   Installer  │  │
│  │              │  │              │  │              │  │
│  │ - Metadata   │  │ - Deps tree  │  │ - Download   │  │
│  │ - Versions   │  │ - Conflicts  │  │ - Verify     │  │
│  │ - Search     │  │ - Upgrade    │  │ - Extract    │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
│                                                           │
│  ┌──────────────────────────────────────────────────┐   │
│  │              Storage Backend                      │   │
│  │  - S3/MinIO (plugin packages)                    │   │
│  │  - PostgreSQL (metadata, versions, deps)         │   │
│  │  - Redis (cache, download stats)                 │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

### 1.2 数据模型

```sql
-- 插件元数据
CREATE TABLE marketplace_plugins (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) UNIQUE NOT NULL,
    display_name VARCHAR(255) NOT NULL,
    author VARCHAR(255) NOT NULL,
    description TEXT,
    category VARCHAR(50),
    tags TEXT[],
    homepage_url TEXT,
    repository_url TEXT,
    license VARCHAR(50),
    downloads INTEGER DEFAULT 0,
    rating DECIMAL(3,2),
    verified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 插件版本
CREATE TABLE marketplace_versions (
    id SERIAL PRIMARY KEY,
    plugin_id INTEGER REFERENCES marketplace_plugins(id) ON DELETE CASCADE,
    version VARCHAR(50) NOT NULL,
    changelog TEXT,
    package_url TEXT NOT NULL,
    package_hash VARCHAR(64) NOT NULL,
    package_size BIGINT,
    min_netkitx_version VARCHAR(50),
    max_netkitx_version VARCHAR(50),
    published_at TIMESTAMP DEFAULT NOW(),
    yanked BOOLEAN DEFAULT FALSE,
    UNIQUE(plugin_id, version)
);

-- 依赖关系
CREATE TABLE marketplace_dependencies (
    id SERIAL PRIMARY KEY,
    version_id INTEGER REFERENCES marketplace_versions(id) ON DELETE CASCADE,
    depends_on_plugin VARCHAR(255) NOT NULL,
    version_constraint VARCHAR(100) NOT NULL,
    optional BOOLEAN DEFAULT FALSE
);

-- 用户安装记录
CREATE TABLE user_installed_plugins (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    plugin_name VARCHAR(255) NOT NULL,
    version VARCHAR(50) NOT NULL,
    installed_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(user_id, plugin_name)
);

-- 评分和评论
CREATE TABLE marketplace_reviews (
    id SERIAL PRIMARY KEY,
    plugin_id INTEGER REFERENCES marketplace_plugins(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    rating INTEGER CHECK (rating >= 1 AND rating <= 5),
    comment TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(plugin_id, user_id)
);

-- 索引
CREATE INDEX idx_plugins_category ON marketplace_plugins(category);
CREATE INDEX idx_plugins_tags ON marketplace_plugins USING GIN(tags);
CREATE INDEX idx_versions_plugin ON marketplace_versions(plugin_id);
CREATE INDEX idx_deps_version ON marketplace_dependencies(version_id);
```

---

## 2. 版本管理

### 2.1 语义化版本 (SemVer)

遵循 `MAJOR.MINOR.PATCH` 格式：

```python
from packaging import version

class VersionManager:
    @staticmethod
    def parse(ver: str) -> version.Version:
        """解析版本号"""
        return version.parse(ver)

    @staticmethod
    def satisfies(ver: str, constraint: str) -> bool:
        """检查版本是否满足约束"""
        # 支持的约束格式：
        # - "1.2.3"      精确匹配
        # - ">=1.2.0"    大于等于
        # - "~1.2.0"     兼容版本 (1.2.x)
        # - "^1.2.0"     次版本兼容 (1.x.x)
        # - "1.2.x"      通配符
        # - ">=1.0.0,<2.0.0"  范围
        pass

    @staticmethod
    def latest_compatible(versions: list[str], constraint: str) -> str | None:
        """找到满足约束的最新版本"""
        compatible = [v for v in versions if VersionManager.satisfies(v, constraint)]
        return max(compatible, key=version.parse) if compatible else None
```

### 2.2 版本约束语法

| 约束 | 含义 | 示例 |
|------|------|------|
| `1.2.3` | 精确版本 | 只安装 1.2.3 |
| `>=1.2.0` | 最小版本 | 1.2.0 及以上 |
| `~1.2.0` | 补丁兼容 | 1.2.x (>=1.2.0, <1.3.0) |
| `^1.2.0` | 次版本兼容 | 1.x.x (>=1.2.0, <2.0.0) |
| `*` | 任意版本 | 最新版本 |
| `>=1.0.0,<2.0.0` | 范围 | 1.x.x |

---

## 3. 依赖解析

### 3.1 依赖声明

在 `plugin.yaml` 中声明依赖：

```yaml
name: advanced-scanner
version: 2.1.0
description: 高级扫描工具
category: recon
engine: python

# 依赖声明
dependencies:
  # 必需依赖
  - name: base-scanner
    version: "^1.0.0"
  - name: network-utils
    version: ">=2.3.0,<3.0.0"

  # 可选依赖
  - name: geo-ip
    version: "~1.5.0"
    optional: true

# NetKitX 版本要求
requires:
  netkitx: ">=0.2.0"
```

### 3.2 依赖解析算法

使用改进的 PubGrub 算法：

```python
from dataclasses import dataclass
from typing import Dict, List, Set

@dataclass
class Dependency:
    name: str
    constraint: str
    optional: bool = False

@dataclass
class Package:
    name: str
    version: str
    dependencies: List[Dependency]

class DependencyResolver:
    def __init__(self, registry: PluginRegistry):
        self.registry = registry
        self.solution: Dict[str, str] = {}  # plugin_name -> version

    def resolve(self, root_deps: List[Dependency]) -> Dict[str, str]:
        """
        解析依赖树，返回 {plugin_name: version} 映射

        算法步骤：
        1. 构建依赖图
        2. 检测循环依赖
        3. 拓扑排序
        4. 版本约束求解
        5. 冲突检测和回溯
        """
        # 初始化待解析队列
        queue = root_deps.copy()
        visited: Set[str] = set()

        while queue:
            dep = queue.pop(0)

            if dep.name in visited:
                continue

            # 查找满足约束的版本
            available = self.registry.get_versions(dep.name)
            selected = VersionManager.latest_compatible(available, dep.constraint)

            if not selected:
                if dep.optional:
                    continue
                raise DependencyError(
                    f"No version of {dep.name} satisfies {dep.constraint}"
                )

            # 检查冲突
            if dep.name in self.solution:
                existing = self.solution[dep.name]
                if existing != selected:
                    # 尝试找到兼容版本
                    selected = self._resolve_conflict(dep.name, existing, selected)

            self.solution[dep.name] = selected
            visited.add(dep.name)

            # 递归解析依赖的依赖
            pkg = self.registry.get_package(dep.name, selected)
            queue.extend(pkg.dependencies)

        return self.solution

    def _resolve_conflict(self, name: str, v1: str, v2: str) -> str:
        """解决版本冲突"""
        # 尝试找到同时满足两个约束的版本
        # 如果无法解决，抛出 ConflictError
        pass

    def detect_cycles(self, deps: List[Dependency]) -> List[str]:
        """检测循环依赖"""
        graph = self._build_graph(deps)
        visited = set()
        rec_stack = set()
        cycle = []

        def dfs(node):
            visited.add(node)
            rec_stack.add(node)

            for neighbor in graph.get(node, []):
                if neighbor not in visited:
                    if dfs(neighbor):
                        cycle.append(neighbor)
                        return True
                elif neighbor in rec_stack:
                    cycle.append(neighbor)
                    return True

            rec_stack.remove(node)
            return False

        for node in graph:
            if node not in visited:
                if dfs(node):
                    return cycle

        return []
```

### 3.3 冲突处理

```python
class ConflictResolver:
    def resolve(self, conflicts: List[Conflict]) -> Resolution:
        """
        冲突解决策略：
        1. 尝试升级到兼容版本
        2. 降级到共同兼容版本
        3. 提示用户手动选择
        4. 标记为不兼容
        """
        for conflict in conflicts:
            # 策略 1: 找到满足所有约束的版本
            compatible = self._find_compatible_version(conflict)
            if compatible:
                return Resolution(version=compatible, strategy="upgrade")

            # 策略 2: 降级
            downgrade = self._find_downgrade_version(conflict)
            if downgrade:
                return Resolution(version=downgrade, strategy="downgrade")

            # 策略 3: 用户选择
            return Resolution(
                strategy="manual",
                options=conflict.candidates,
                message=f"Cannot auto-resolve conflict for {conflict.plugin}"
            )
```

---

## 4. 插件安装流程

### 4.1 安装命令

```bash
# CLI 命令
netkitx plugin install <name>[@version]
netkitx plugin install advanced-scanner@2.1.0
netkitx plugin install advanced-scanner  # 安装最新版本

# 批量安装
netkitx plugin install -r requirements.txt

# 强制重装
netkitx plugin install --force advanced-scanner

# 仅下载不安装
netkitx plugin download advanced-scanner
```

### 4.2 安装流程

```python
class PluginInstaller:
    async def install(
        self,
        plugin_name: str,
        version: str | None = None,
        force: bool = False
    ) -> InstallResult:
        """
        安装插件流程：
        1. 查询市场元数据
        2. 解析依赖
        3. 下载所有包
        4. 验证签名和哈希
        5. 按依赖顺序安装
        6. 更新本地注册表
        """
        # 1. 查询元数据
        metadata = await self.marketplace.get_plugin(plugin_name)
        if not metadata:
            raise PluginNotFoundError(f"Plugin {plugin_name} not found")

        # 2. 选择版本
        if not version:
            version = metadata.latest_version
        elif version not in metadata.versions:
            raise VersionNotFoundError(f"Version {version} not found")

        # 3. 检查已安装
        if not force and self.is_installed(plugin_name, version):
            return InstallResult(status="already_installed")

        # 4. 解析依赖
        resolver = DependencyResolver(self.marketplace)
        deps = await self.marketplace.get_dependencies(plugin_name, version)
        resolution = resolver.resolve(deps)

        # 5. 下载所有包
        packages = []
        for name, ver in resolution.items():
            pkg = await self.download_package(name, ver)
            packages.append(pkg)

        # 6. 验证
        for pkg in packages:
            if not self.verify_package(pkg):
                raise SecurityError(f"Package {pkg.name} verification failed")

        # 7. 安装（按依赖顺序）
        install_order = self._topological_sort(resolution)
        for name in install_order:
            ver = resolution[name]
            pkg = next(p for p in packages if p.name == name)
            await self._install_package(pkg)

        # 8. 更新记录
        await self.db.record_installation(plugin_name, version)

        return InstallResult(
            status="success",
            installed=[f"{n}@{v}" for n, v in resolution.items()]
        )

    async def download_package(self, name: str, version: str) -> Package:
        """从市场下载插件包"""
        url = await self.marketplace.get_download_url(name, version)

        # 下载到临时目录
        temp_file = f"/tmp/{name}-{version}.zip"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                with open(temp_file, 'wb') as f:
                    async for chunk in resp.content.iter_chunked(8192):
                        f.write(chunk)

        return Package(name=name, version=version, path=temp_file)

    def verify_package(self, pkg: Package) -> bool:
        """验证包完整性和签名"""
        # 1. 验证 SHA256 哈希
        expected_hash = self.marketplace.get_hash(pkg.name, pkg.version)
        actual_hash = self._compute_hash(pkg.path)
        if expected_hash != actual_hash:
            return False

        # 2. 验证 GPG 签名（如果有）
        if self.marketplace.has_signature(pkg.name, pkg.version):
            signature = self.marketplace.get_signature(pkg.name, pkg.version)
            if not self._verify_signature(pkg.path, signature):
                return False

        return True
```

---

## 5. 市场 API

### 5.1 后端 API

```python
# backend/app/api/v1/marketplace.py

@router.get("/marketplace/plugins")
async def list_marketplace_plugins(
    category: str | None = None,
    tags: list[str] = Query(None),
    search: str | None = None,
    sort: str = "downloads",  # downloads | rating | updated
    page: int = 1,
    limit: int = 20,
):
    """列出市场插件"""
    pass

@router.get("/marketplace/plugins/{name}")
async def get_marketplace_plugin(name: str):
    """获取插件详情"""
    pass

@router.get("/marketplace/plugins/{name}/versions")
async def list_plugin_versions(name: str):
    """列出插件所有版本"""
    pass

@router.get("/marketplace/plugins/{name}/versions/{version}")
async def get_plugin_version(name: str, version: str):
    """获取特定版本详情"""
    pass

@router.post("/marketplace/plugins/{name}/install")
async def install_from_marketplace(
    name: str,
    version: str | None = None,
    current_user: User = Depends(get_current_user)
):
    """从市场安装插件"""
    pass

@router.get("/marketplace/plugins/{name}/dependencies")
async def get_plugin_dependencies(name: str, version: str):
    """获取依赖树"""
    pass

@router.post("/marketplace/plugins/{name}/review")
async def create_review(
    name: str,
    rating: int,
    comment: str,
    current_user: User = Depends(get_current_user)
):
    """提交评价"""
    pass

# 发布者 API
@router.post("/marketplace/publish")
async def publish_plugin(
    file: UploadFile,
    metadata: PluginMetadata,
    current_user: User = Depends(get_current_user)
):
    """发布插件到市场"""
    pass

@router.delete("/marketplace/plugins/{name}/versions/{version}")
async def yank_version(
    name: str,
    version: str,
    current_user: User = Depends(get_current_user)
):
    """撤回版本（不删除，标记为 yanked）"""
    pass
```

### 5.2 前端 UI

```typescript
// frontend/src/app/marketplace/page.tsx

export default function MarketplacePage() {
  return (
    <div>
      {/* 搜索和筛选 */}
      <SearchBar />
      <Filters categories={categories} tags={tags} />

      {/* 插件列表 */}
      <PluginGrid>
        {plugins.map(plugin => (
          <PluginCard
            key={plugin.name}
            name={plugin.name}
            description={plugin.description}
            downloads={plugin.downloads}
            rating={plugin.rating}
            verified={plugin.verified}
            onInstall={() => installPlugin(plugin.name)}
          />
        ))}
      </PluginGrid>
    </div>
  )
}

// frontend/src/app/marketplace/[name]/page.tsx

export default function PluginDetailPage({ params }) {
  return (
    <div>
      {/* 插件信息 */}
      <PluginHeader plugin={plugin} />

      {/* 版本选择 */}
      <VersionSelector
        versions={versions}
        selected={selectedVersion}
        onChange={setSelectedVersion}
      />

      {/* 依赖树 */}
      <DependencyTree dependencies={dependencies} />

      {/* README */}
      <Markdown content={plugin.readme} />

      {/* 评价 */}
      <Reviews reviews={reviews} />

      {/* 安装按钮 */}
      <InstallButton
        plugin={plugin.name}
        version={selectedVersion}
        onInstall={handleInstall}
      />
    </div>
  )
}
```

---

## 6. 存储方案

### 6.1 对象存储 (S3/MinIO)

```
s3://netkitx-marketplace/
├── packages/
│   ├── plugin-a/
│   │   ├── 1.0.0.zip
│   │   ├── 1.0.0.zip.sha256
│   │   ├── 1.0.0.zip.sig
│   │   ├── 1.1.0.zip
│   │   └── ...
│   └── plugin-b/
│       └── ...
├── metadata/
│   ├── index.json
│   └── plugins/
│       ├── plugin-a.json
│       └── plugin-b.json
└── assets/
    ├── icons/
    └── screenshots/
```

### 6.2 CDN 加速

```python
class CDNManager:
    def get_download_url(self, plugin: str, version: str) -> str:
        """生成 CDN 加速下载链接"""
        # 1. 检查 CDN 缓存
        cdn_url = f"https://cdn.netkitx.com/packages/{plugin}/{version}.zip"

        # 2. 生成签名 URL（防盗链）
        expires = int(time.time()) + 3600  # 1小时有效
        signature = self._sign_url(cdn_url, expires)

        return f"{cdn_url}?expires={expires}&signature={signature}"
```

---

## 7. 安全机制

### 7.1 包签名

```python
import gnupg

class PackageSigner:
    def __init__(self, gpg_home: str):
        self.gpg = gnupg.GPG(gnupghome=gpg_home)

    def sign_package(self, package_path: str, key_id: str) -> str:
        """使用 GPG 签名包"""
        with open(package_path, 'rb') as f:
            signed = self.gpg.sign_file(f, keyid=key_id, detach=True)
        return str(signed)

    def verify_signature(self, package_path: str, signature: str) -> bool:
        """验证签名"""
        with open(package_path, 'rb') as f:
            verified = self.gpg.verify_file(f, signature)
        return verified.valid
```

### 7.2 沙箱扫描

```python
class SecurityScanner:
    async def scan_package(self, package_path: str) -> ScanResult:
        """扫描插件包安全性"""
        results = []

        # 1. 静态代码分析
        results.append(await self._bandit_scan(package_path))

        # 2. 依赖漏洞扫描
        results.append(await self._safety_check(package_path))

        # 3. 恶意代码检测
        results.append(await self._malware_scan(package_path))

        # 4. 许可证检查
        results.append(await self._license_check(package_path))

        return ScanResult(
            passed=all(r.passed for r in results),
            issues=[issue for r in results for issue in r.issues]
        )
```

### 7.3 权限声明

```yaml
# plugin.yaml
name: network-scanner
version: 1.0.0

# 权限声明
permissions:
  - network:outbound  # 允许外部网络访问
  - filesystem:read   # 允许读取文件
  - subprocess:exec   # 允许执行子进程

# 敏感操作需要用户确认
dangerous_permissions:
  - filesystem:write
  - database:write
```

---

## 8. 实施路线图

### Phase 1: 基础设施 (2 weeks)
- [ ] 数据库表结构
- [ ] S3/MinIO 存储配置
- [ ] 基础 API 端点
- [ ] 版本管理器

### Phase 2: 依赖解析 (2 weeks)
- [ ] 依赖解析算法
- [ ] 冲突检测
- [ ] 循环依赖检测
- [ ] 单元测试

### Phase 3: 安装器 (2 weeks)
- [ ] 下载管理器
- [ ] 包验证
- [ ] 安装流程
- [ ] 回滚机制

### Phase 4: 前端 UI (2 weeks)
- [ ] 市场列表页
- [ ] 插件详情页
- [ ] 搜索和筛选
- [ ] 安装进度显示

### Phase 5: 发布流程 (1 week)
- [ ] 发布 API
- [ ] CLI 发布工具
- [ ] 自动化测试
- [ ] 文档生成

### Phase 6: 安全和审核 (1 week)
- [ ] 包签名
- [ ] 安全扫描
- [ ] 人工审核流程
- [ ] 举报机制

---

## 9. 配置示例

### 9.1 requirements.txt

```
# NetKitX Plugin Requirements
# 类似 Python pip requirements.txt

base-scanner>=1.0.0
network-utils~=2.3.0
geo-ip==1.5.2  # 精确版本
advanced-recon>=3.0.0,<4.0.0

# 可选依赖
# visualization-tools>=1.0.0  # optional
```

### 9.2 lock 文件

```json
// netkitx-lock.json
// 类似 package-lock.json，锁定精确版本
{
  "version": "1.0",
  "plugins": {
    "base-scanner": {
      "version": "1.2.3",
      "resolved": "https://marketplace.netkitx.com/packages/base-scanner/1.2.3.zip",
      "integrity": "sha256-abc123...",
      "dependencies": {}
    },
    "network-utils": {
      "version": "2.3.5",
      "resolved": "https://marketplace.netkitx.com/packages/network-utils/2.3.5.zip",
      "integrity": "sha256-def456...",
      "dependencies": {
        "ip-parser": "^1.0.0"
      }
    }
  }
}
```

---

## 10. 参考实现

- **npm** — Node.js 包管理器（依赖解析）
- **pip** — Python 包管理器（版本约束）
- **cargo** — Rust 包管理器（lock 文件）
- **apt** — Debian 包管理器（依赖树）
- **VS Code Marketplace** — 插件市场 UI

---

## 总结

插件市场的核心是：

1. **版本管理** — SemVer + 约束求解
2. **依赖解析** — PubGrub 算法 + 冲突处理
3. **安全机制** — 签名验证 + 沙箱扫描
4. **用户体验** — 一键安装 + 自动更新

实现优先级：Phase 1-3 是核心功能，Phase 4-6 是增强功能。
