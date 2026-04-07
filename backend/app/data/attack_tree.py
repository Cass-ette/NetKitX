"""Attack tree data: kill chain phases and per-phase plugin/command mappings."""

KILL_CHAIN_PHASES = [
    "reconnaissance",
    "initial_access",
    "execution",
    "persistence",
    "privilege_escalation",
    "lateral_movement",
    "exfiltration",
]

ATTACK_TREE: dict[str, dict] = {
    "reconnaissance": {
        "plugins": [
            "port-scan",
            "dir-scan",
            "subdomain-enum",
            "dns-lookup",
            "ssl-check",
            "http-request",
        ],
        "shell_patterns": ["curl", "nmap", "dig", "whois", "wget"],
        "description": "信息收集阶段：扫描端口、目录、子域名、DNS记录等",
    },
    "initial_access": {
        "plugins": [
            "sql-inject",
            "file-upload",
            "brute-force",
            "backup-scan",
            "git-leak",
        ],
        "shell_patterns": ["curl", "sqlmap", "hydra", "nikto"],
        "description": "初始入侵阶段：利用漏洞获取初始访问权限",
    },
    "execution": {
        "plugins": ["webshell"],
        "shell_patterns": ["curl", "python", "php", "nc"],
        "description": "执行阶段：在目标上执行代码或命令",
    },
    "persistence": {
        "plugins": [],
        "shell_patterns": ["curl", "wget", "crontab", "ssh"],
        "description": "持久化阶段：建立持久访问后门",
    },
    "privilege_escalation": {
        "plugins": [],
        "shell_patterns": ["sudo", "find", "cat", "python"],
        "description": "提权阶段：从普通用户提升到root/admin",
    },
    "lateral_movement": {
        "plugins": ["port-scan", "dns-lookup"],
        "shell_patterns": ["ssh", "curl", "nmap", "scp"],
        "description": "横向移动阶段：从一台机器扩展到其他机器",
    },
    "exfiltration": {
        "plugins": [],
        "shell_patterns": ["curl", "wget", "base64", "cat"],
        "description": "数据窃取阶段：提取敏感数据",
    },
}

# Dangerous commands that are ALWAYS blocked regardless of phase
DANGEROUS_COMMAND_PATTERNS = [
    (r"\brm\s+-rf\s+/(?!\w)", "Destructive: rm -rf /"),
    (r"\bmkfs\b", "Destructive: format filesystem"),
    (r"\bdd\s+if=", "Destructive: dd overwrite"),
    (r":\(\)\{.*:\|:&\}", "Destructive: fork bomb"),
    (r"\bshutdown\b", "System: shutdown"),
    (r"\breboot\b", "System: reboot"),
    (r"\bpoweroff\b", "System: poweroff"),
    (r"\binit\s+[06]\b", "System: init shutdown/reboot"),
]
