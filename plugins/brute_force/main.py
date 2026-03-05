import asyncio
import socket
from pathlib import Path
from typing import Any, AsyncIterator

from app.plugins.base import PluginBase, PluginEvent, PluginMeta

PASS_PATH = Path(__file__).resolve().parent.parent.parent / "backend" / "data" / "dicts" / "password" / "common.txt"

DEFAULT_PORTS = {"ssh": 22, "ftp": 21, "mysql": 3306, "redis": 6379, "postgresql": 5432}


class BruteForce(PluginBase):
    meta = PluginMeta(
        name="brute-force",
        version="1.0.0",
        description="弱口令检测",
        category="vuln",
        engine="python",
    )

    async def execute(self, params: dict[str, Any]) -> AsyncIterator[PluginEvent]:
        host = params["host"].strip()
        service = params["service"].strip().lower()
        port = int(params.get("port") or DEFAULT_PORTS.get(service, 0))
        usernames = [u.strip() for u in params.get("username", "root").split(",") if u.strip()]
        concurrency = int(params.get("concurrency", 5))

        if PASS_PATH.exists():
            passwords = [p.strip() for p in PASS_PATH.read_text().splitlines() if p.strip()]
        else:
            passwords = ["123456", "password", "admin", "root", "test", "admin123"]

        total = len(usernames) * len(passwords)
        yield PluginEvent(type="log", data={"msg": f"Brute forcing {service}://{host}:{port} ({total} combinations)"})
        yield PluginEvent(type="progress", data={"percent": 0, "msg": f"Testing {total} combinations..."})

        found = 0
        done = 0
        sem = asyncio.Semaphore(concurrency)

        for ui, username in enumerate(usernames):
            for pi, password in enumerate(passwords):
                async with sem:
                    success = await self._try_login(service, host, port, username, password)
                    done += 1

                    if success:
                        found += 1
                        yield PluginEvent(
                            type="result",
                            data={
                                "host": host,
                                "service": service,
                                "port": port,
                                "username": username,
                                "password": password,
                                "status": "SUCCESS",
                            },
                        )
                        yield PluginEvent(type="log", data={"msg": f"  [HIT] {username}:{password}"})

                    if done % 20 == 0 or done == total:
                        pct = min(done * 100 // total, 99)
                        yield PluginEvent(type="progress", data={"percent": pct, "msg": f"Tested {done}/{total}, found {found}"})

        summary = f"Complete: {found} valid credentials found"
        yield PluginEvent(type="log", data={"msg": summary})
        yield PluginEvent(type="progress", data={"percent": 100, "msg": summary})

    async def _try_login(self, service: str, host: str, port: int, user: str, pwd: str) -> bool:
        loop = asyncio.get_event_loop()
        try:
            if service == "ssh":
                return await self._try_ssh(host, port, user, pwd)
            elif service == "ftp":
                return await loop.run_in_executor(None, self._try_ftp_sync, host, port, user, pwd)
            elif service == "mysql":
                return await loop.run_in_executor(None, self._try_mysql_sync, host, port, user, pwd)
            elif service == "redis":
                return await loop.run_in_executor(None, self._try_redis_sync, host, port, pwd)
            elif service == "postgresql":
                return await loop.run_in_executor(None, self._try_pg_sync, host, port, user, pwd)
        except Exception:
            return False
        return False

    async def _try_ssh(self, host: str, port: int, user: str, pwd: str) -> bool:
        try:
            import asyncssh
            async with asyncssh.connect(
                host, port=port, username=user, password=pwd,
                known_hosts=None, login_timeout=5,
            ):
                return True
        except Exception:
            return False

    def _try_ftp_sync(self, host: str, port: int, user: str, pwd: str) -> bool:
        import ftplib
        try:
            ftp = ftplib.FTP()
            ftp.connect(host, port, timeout=5)
            ftp.login(user, pwd)
            ftp.quit()
            return True
        except Exception:
            return False

    def _try_mysql_sync(self, host: str, port: int, user: str, pwd: str) -> bool:
        """Test MySQL login using raw socket protocol."""
        try:
            sock = socket.create_connection((host, port), timeout=5)
            # Read greeting packet
            data = sock.recv(4096)
            if not data:
                sock.close()
                return False
            sock.close()
            # For a real implementation, we'd need mysql protocol handshake
            # For now, use subprocess mysql client if available
            import subprocess
            result = subprocess.run(
                ["mysql", f"-h{host}", f"-P{port}", f"-u{user}", f"-p{pwd}", "-e", "SELECT 1"],
                capture_output=True, timeout=5,
            )
            return result.returncode == 0
        except Exception:
            return False

    def _try_redis_sync(self, host: str, port: int, pwd: str) -> bool:
        try:
            sock = socket.create_connection((host, port), timeout=5)
            sock.sendall(f"AUTH {pwd}\r\n".encode())
            resp = sock.recv(1024).decode()
            sock.close()
            return resp.startswith("+OK")
        except Exception:
            return False

    def _try_pg_sync(self, host: str, port: int, user: str, pwd: str) -> bool:
        try:
            import subprocess
            env = {"PGPASSWORD": pwd}
            result = subprocess.run(
                ["psql", f"-h{host}", f"-p{port}", f"-U{user}", "-c", "SELECT 1"],
                capture_output=True, timeout=5, env={**__import__("os").environ, **env},
            )
            return result.returncode == 0
        except Exception:
            return False
