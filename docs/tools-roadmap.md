# NetKitX 安全工具规划

> 本文档规划 NetKitX 平台将集成的安全工具，按类别组织，标注优先级和实现方式。

## 现有工具

| 工具 | 引擎 | 类别 | 功能 |
|------|------|------|------|
| port-scan | Go | recon | TCP/SYN 端口扫描，支持并发 |
| dir-scan | Go | recon | 目录字典爆破（类 dirsearch） |
| sql-inject | Python | sqli | 10 种注入类型，Cookie/UA/Referer 注入位置 |
| http-request | Python | http | 自定义 HTTP 请求工具 |
| webshell | Python | exploit | Webshell 管理与连接 |
| file-upload | Python | exploit | 文件上传绕过测试 |
| weak-pass | Python | brute | 多协议弱口令检测 |
| subdomain | Python | recon | 子域名枚举 |
| whois | Python | recon | 域名/IP 注册信息查询 |
| dns-lookup | Python | recon | DNS 全量记录查询 |
| ssl-check | Python | recon | SSL/TLS 证书与配置检测 |
| git-leak | Python | leak | .git 泄露检测与恢复 |
| svn-leak | Python | leak | .svn 泄露检测 |
| backup-scan | Python | leak | 备份文件探测 |
| cms-detect | Python | recon | CMS/框架指纹识别 |
| banner-grab | Go | recon | 服务 Banner 抓取 |

---

## 一、信息收集（Recon）

### 1.1 子域名枚举
- **功能**: DNS 字典爆破 + 搜索引擎被动收集
- **引擎**: Python
- **输入**: 目标域名、字典选择、线程数
- **输出**: 子域名、IP、状态码、标题
- **优先级**: P0

### 1.2 DNS 记录查询
- **功能**: 查询 A/AAAA/MX/CNAME/TXT/NS/SOA 全量记录
- **引擎**: Python (dnspython)
- **输入**: 域名、记录类型（可多选）
- **输出**: 记录类型、值、TTL
- **优先级**: P0

### 1.3 Whois 查询
- **功能**: 域名/IP 注册信息查询
- **引擎**: Python (python-whois)
- **输入**: 域名或 IP
- **输出**: 注册商、注册时间、过期时间、联系人、NS 服务器
- **优先级**: P1

### 1.4 HTTP 指纹识别
- **功能**: 识别 Web 框架、CMS、服务器版本、编程语言
- **引擎**: Python
- **输入**: 目标 URL
- **输出**: 服务器、框架、CMS、版本、技术栈
- **参考**: Wappalyzer 规则库
- **优先级**: P1

### 1.5 Banner 抓取
- **功能**: 连接端口读取服务 banner 信息
- **引擎**: Go
- **输入**: 目标 IP、端口列表
- **输出**: 端口、协议、banner 内容
- **优先级**: P1

### 1.6 SSL/TLS 检测
- **功能**: 证书信息、协议版本、加密套件、弱配置检测
- **引擎**: Python (ssl/cryptography)
- **输入**: 目标域名/IP
- **输出**: 证书主体、颁发者、有效期、协议版本、弱加密告警
- **优先级**: P2

---

## 二、信息泄露检测（Leak）

### 2.1 Git 泄露检测
- **功能**: 探测 `.git/` 目录泄露，尝试恢复源码
- **引擎**: Python
- **输入**: 目标 URL
- **输出**: 是否存在泄露、可恢复文件列表、敏感文件内容
- **优先级**: P0

### 2.2 SVN 泄露检测
- **功能**: 探测 `.svn/entries` / `.svn/wc.db` 泄露
- **引擎**: Python
- **输入**: 目标 URL
- **输出**: 是否存在泄露、文件列表
- **优先级**: P0

### 2.3 HG 泄露检测
- **功能**: 探测 `.hg/` 目录泄露
- **引擎**: Python
- **输入**: 目标 URL
- **输出**: 是否存在泄露、仓库信息
- **优先级**: P1

### 2.4 备份文件探测
- **功能**: 扫描常见备份文件（.bak, .zip, .sql, .tar.gz, .rar, ~, .swp, .old）
- **引擎**: Python
- **输入**: 目标 URL、自定义字典（可选）
- **输出**: 发现的备份文件 URL、状态码、文件大小
- **优先级**: P0

### 2.5 PHPINFO 探测
- **功能**: 检测 phpinfo() 页面泄露
- **引擎**: Python
- **输入**: 目标 URL
- **输出**: 是否存在、PHP 版本、关键配置（disable_functions, open_basedir 等）
- **优先级**: P1

### 2.6 目录扫描
- **功能**: 常见路径字典爆破（类似 dirsearch）
- **引擎**: Go（高并发）
- **输入**: 目标 URL、字典选择、线程数、状态码过滤
- **输出**: 路径、状态码、大小、标题
- **优先级**: P0

---

## 三、HTTP 调试（HTTP）

### 3.1 HTTP 请求工具
- **功能**: 自定义 HTTP 请求，查看完整请求/响应
- **引擎**: Python (httpx)
- **输入**: URL、方法（GET/POST/PUT/DELETE/HEAD/OPTIONS）、自定义 Header、Cookie、Body、是否跟随跳转
- **输出**: 状态码、响应头、响应体、跳转链（302 全链路追踪）、耗时
- **说明**: 覆盖 HTTP 协议基础训练场景（请求方式、302 跳转、Cookie、基础认证、响应包源代码）
- **优先级**: P0

---

## 四、密码口令（Brute）

### 4.1 弱口令检测
- **功能**: 测试常见服务的默认/弱密码
- **引擎**: Python
- **支持服务**: SSH, FTP, MySQL, Redis, PostgreSQL, MongoDB, Telnet, SMTP
- **输入**: 目标 IP、端口、服务类型、用户名列表、密码字典
- **输出**: 成功的用户名/密码组合
- **优先级**: P0

### 4.2 Web 登录爆破
- **功能**: HTTP 表单登录爆破
- **引擎**: Python
- **输入**: 登录 URL、用户名字段、密码字段、成功/失败标识、字典
- **输出**: 成功的凭证
- **优先级**: P1

### 4.3 默认口令库查询
- **功能**: 根据设备/服务名查询已知默认口令
- **引擎**: Python（内置数据库）
- **输入**: 设备/服务名称（如 Tomcat, Cisco, TP-Link）
- **输出**: 默认用户名/密码列表
- **优先级**: P2

---

## 五、SQL 注入（SQLi）

### 5.1 SQL 注入检测
- **功能**: 自动检测 SQL 注入点
- **引擎**: Python
- **检测类型**:
  - 整数型注入
  - 字符型注入
  - 报错注入（extractvalue, updatexml, floor）
  - 布尔盲注
  - 时间盲注
- **注入位置**:
  - GET/POST 参数
  - Cookie
  - User-Agent
  - Referer
- **输入**: 目标 URL、参数标记、注入类型（可自动检测）
- **输出**: 注入点、注入类型、payload、数据库类型
- **优先级**: P0

### 5.2 SQL 注入利用
- **功能**: 对已确认的注入点进行数据提取
- **引擎**: Python
- **功能**: 获取数据库名、表名、列名、数据内容
- **支持**: MySQL 结构查询（information_schema）
- **输入**: 目标 URL、注入点、注入类型
- **输出**: 数据库结构树、提取的数据
- **优先级**: P1

---

## 六、XSS 检测与利用

> 参考项目: [BlueLotus_XSSReceiver](https://github.com/firesunCN/BlueLotus_XSSReceiver) — XSS 平台 CTF 工具

### 6.1 XSS 漏洞检测
- **功能**: 自动检测反射型/DOM 型 XSS
- **引擎**: Python
- **检测类型**:
  - 反射型 XSS
  - DOM 反射
  - DOM 跳转（location/href 篡改）
- **绕过测试**: 过滤空格、过滤关键词
- **输入**: 目标 URL、参数
- **输出**: 漏洞类型、注入点、有效 payload
- **优先级**: P1

### 6.2 XSS Payload 管理
- **功能**: 内置 payload 库 + 自定义 payload 模板
- **引擎**: Python
- **内置分类**:
  - 基础弹窗（alert/confirm/prompt）
  - Cookie 窃取
  - 键盘记录
  - 页面劫持
  - 绕过类（大小写、编码、拼接）
- **输入**: 选择模板、自定义参数（回连地址等）
- **输出**: 生成的 payload 代码
- **优先级**: P1

### 6.3 XSS 接收平台
- **功能**: 类 BlueLotus 的 XSS 回连接收器
- **引擎**: Python（独立服务）
- **功能**:
  - 生成带唯一标识的 payload
  - 接收并记录回连数据（Cookie、URL、UA、截图）
  - 实时 WebSocket 通知新回连
  - 历史记录查看
- **参考**: BlueLotus_XSSReceiver 的 JS payload 生成 + 数据接收模型
- **优先级**: P2

---

## 七、文件上传测试（Upload）

### 7.1 上传绕过 Payload 生成
- **功能**: 生成各种文件上传绕过测试文件
- **引擎**: Python
- **绕过类型**:
  - MIME 类型伪造
  - 00 截断
  - 后缀大小写绕过（.PhP）
  - 点绕过（shell.php.）
  - 空格绕过（shell.php ）
  - 双写后缀（shell.pphphp）
  - .htaccess 上传
  - 文件头伪造（GIF89a）
  - 突破 getimagesize()
  - 突破 exif_imagetype()
  - 二次渲染绕过
- **输入**: 绕过类型、shell 内容、目标文件名
- **输出**: 生成的测试文件（可下载）
- **优先级**: P1

### 7.2 上传点检测
- **功能**: 对上传接口进行自动化绕过测试
- **引擎**: Python
- **输入**: 上传 URL、表单字段名、允许的扩展名
- **输出**: 成功绕过的方法、上传后的文件 URL
- **优先级**: P2

---

## 实施优先级

### P0 — 第一批（核心工具）
| 工具 | 类别 | 说明 |
|------|------|------|
| DNS 记录查询 | recon | 简单实用，入门级 |
| 子域名枚举 | recon | 渗透第一步 |
| 目录扫描 | leak | Go 高并发，实战必备 |
| Git/SVN 泄露检测 | leak | CTF 高频考点 |
| 备份文件探测 | leak | 信息泄露必查 |
| HTTP 请求工具 | http | 覆盖 HTTP 协议训练全场景 |
| 弱口令检测 | brute | 多服务支持 |
| SQL 注入检测 | sqli | 覆盖主要注入类型 |

### P1 — 第二批（进阶工具）
| 工具 | 类别 | 说明 |
|------|------|------|
| Whois 查询 | recon | |
| HTTP 指纹识别 | recon | |
| Banner 抓取 | recon | |
| HG 泄露检测 | leak | |
| PHPINFO 探测 | leak | |
| Web 登录爆破 | brute | |
| SQL 注入利用 | sqli | 数据提取 |
| XSS 检测 | xss | |
| XSS Payload 管理 | xss | |
| 上传绕过 Payload 生成 | upload | |

### P2 — 第三批（高级功能）
| 工具 | 类别 | 说明 |
|------|------|------|
| SSL/TLS 检测 | recon | |
| 默认口令库查询 | brute | |
| XSS 接收平台 | xss | 参考 BlueLotus |
| 上传点自动检测 | upload | |

---

## 技术说明

### 字典资源
工具所需的字典文件（子域名、目录、密码、备份文件后缀等）统一放置在 `backend/data/dicts/` 目录，按类别组织：
```
backend/data/dicts/
├── subdomain/       # 子域名字典
├── directory/       # 目录字典
├── password/        # 密码字典
├── backup/          # 备份文件后缀
├── useragent/       # UA 字典
└── default-creds/   # 默认口令库
```

### 插件实现规范
- 每个工具一个独立插件目录
- 使用 `PluginEvent(type="log")` 输出实时日志到终端面板
- 使用 `PluginEvent(type="result")` 输出结构化结果到表格
- 扫描类工具结果包含 `host` 字段以支持拓扑图生成
- 所有网络请求设置合理超时和并发限制
