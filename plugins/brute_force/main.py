import asyncio
import hashlib
import socket
import struct
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
        """Test MySQL login via native authentication handshake."""
        try:
            sock = socket.create_connection((host, port), timeout=5)

            # Read greeting packet
            header = self._recv_exact(sock, 4)
            if not header:
                sock.close()
                return False
            pkt_len = struct.unpack("<I", header[:3] + b"\x00")[0]
            seq = header[3]
            payload = self._recv_exact(sock, pkt_len)
            if not payload or payload[0] != 10:  # protocol v10
                sock.close()
                return False

            # Parse server greeting
            nul = payload.index(0, 1)
            off = nul + 1 + 4  # skip version string + thread_id
            scramble1 = payload[off : off + 8]
            off += 8 + 1  # skip filler
            off += 2  # cap_lower
            off += 1 + 2  # charset + status
            off += 2  # cap_upper
            auth_data_len = payload[off]
            off += 1 + 10  # skip reserved
            s2_len = max(13, auth_data_len - 8)
            scramble2 = payload[off : off + s2_len]
            if scramble2 and scramble2[-1] == 0:
                scramble2 = scramble2[:-1]
            scramble = scramble1 + scramble2

            # Scramble password
            if pwd:
                sha1 = hashlib.sha1
                h1 = sha1(pwd.encode()).digest()
                h2 = sha1(h1).digest()
                h3 = sha1(scramble + h2).digest()
                auth_data = bytes(a ^ b for a, b in zip(h1, h3))
            else:
                auth_data = b""

            # Build auth response
            cap = 0x00000200 | 0x00008000 | 0x00080000  # PROTOCOL_41 | SECURE_CONN | PLUGIN_AUTH
            auth_pkt = struct.pack("<I", cap)
            auth_pkt += struct.pack("<I", 16 * 1024 * 1024)
            auth_pkt += b"\x21" + b"\x00" * 23  # charset utf8 + reserved
            auth_pkt += user.encode() + b"\x00"
            auth_pkt += bytes([len(auth_data)]) + auth_data
            auth_pkt += b"mysql_native_password\x00"

            pkt_hdr = struct.pack("<I", len(auth_pkt))[:3] + bytes([seq + 1])
            sock.sendall(pkt_hdr + auth_pkt)

            # Read response
            resp_hdr = self._recv_exact(sock, 4)
            if not resp_hdr:
                sock.close()
                return False
            resp_len = struct.unpack("<I", resp_hdr[:3] + b"\x00")[0]
            resp = self._recv_exact(sock, resp_len)
            sock.close()
            return bool(resp and resp[0] == 0x00)  # OK packet
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
        """Test PostgreSQL login via wire protocol."""
        try:
            sock = socket.create_connection((host, port), timeout=5)

            # Send StartupMessage (protocol 3.0)
            params = f"user\x00{user}\x00\x00".encode()
            msg = struct.pack("!II", 4 + 4 + len(params), 196608) + params
            sock.sendall(msg)

            # Read authentication request
            msg_type = sock.recv(1)
            if not msg_type or msg_type != b"R":
                sock.close()
                return False
            msg_len = struct.unpack("!I", self._recv_exact(sock, 4))[0]
            msg_data = self._recv_exact(sock, msg_len - 4)
            auth_type = struct.unpack("!I", msg_data[:4])[0]

            if auth_type == 0:  # trust auth
                sock.close()
                return True
            elif auth_type == 3:  # cleartext
                pwd_msg = b"p" + struct.pack("!I", 4 + len(pwd) + 1) + pwd.encode() + b"\x00"
                sock.sendall(pwd_msg)
            elif auth_type == 5:  # MD5
                salt = msg_data[4:8]
                inner = hashlib.md5(pwd.encode() + user.encode()).hexdigest()
                outer = "md5" + hashlib.md5(inner.encode() + salt).hexdigest()
                pwd_msg = b"p" + struct.pack("!I", 4 + len(outer) + 1) + outer.encode() + b"\x00"
                sock.sendall(pwd_msg)
            else:  # SCRAM or unsupported
                sock.close()
                return False

            # Read auth result
            resp_type = sock.recv(1)
            if not resp_type:
                sock.close()
                return False
            resp_len = struct.unpack("!I", self._recv_exact(sock, 4))[0]
            resp_data = self._recv_exact(sock, resp_len - 4)
            sock.close()
            return resp_type == b"R" and struct.unpack("!I", resp_data[:4])[0] == 0
        except Exception:
            return False

    def _recv_exact(self, sock: socket.socket, n: int) -> bytes | None:
        """Receive exactly n bytes from socket."""
        data = b""
        while len(data) < n:
            chunk = sock.recv(n - len(data))
            if not chunk:
                return None
            data += chunk
        return data
